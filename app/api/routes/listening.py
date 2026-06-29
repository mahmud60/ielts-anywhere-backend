import json
import logging
import re
import anthropic

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.user import User
from app.models.test import TestAttempt, ModuleType, GradingStatus
from app.models.listening import ListeningTest, ListeningSection, ListeningSubsection
from app.models.ielts_test import IeltsTest, TestSession
from app.services import analytics
from app.schemas.listening import (
    SectionOut,
    SubmitListeningRequest,
    ListeningResultOut, QuestionResult,
)
from app.api.routes.auth import get_current_user
from app.services.listening_scorer import score_answer, calculate_band, generate_tips
from app.models.user import SubscriptionTier
from app.core.config import settings

router = APIRouter(prefix="/listening", tags=["listening"])

logger = logging.getLogger(__name__)


def _clean_json(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


async def _translate_tips(tips: list[str]) -> list[str]:
    """Translate a flat list of tips to Bengali. Falls back to originals on error."""
    if not tips:
        return tips
    numbered = "\n".join(f"{i+1}. {tip}" for i, tip in enumerate(tips))
    prompt = (
        "Translate the following IELTS improvement tips into Bengali (বাংলা).\n"
        "Keep IELTS-specific terms (band scores, module names Writing/Speaking/Reading/Listening, "
        "grammatical terms) in English.\n"
        "Reply ONLY with a JSON array of translated strings in the same order, no markdown:\n\n"
        f"{numbered}"
    )
    try:
        ai = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        resp = await ai.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        translated = json.loads(_clean_json(resp.content[0].text))
        if isinstance(translated, list) and len(translated) == len(tips):
            return translated
    except Exception:
        logger.warning("Tip translation failed; returning original tips", exc_info=True)
    return tips


def _load_options():
    """Eager-load chain: test → sections → subsections → questions."""
    return (
        selectinload(ListeningTest.sections)
        .selectinload(ListeningSection.subsections)
        .selectinload(ListeningSubsection.questions)
    )


def _serialize_test(test: ListeningTest) -> dict:
    return {
        "qid": f"QN{test.id}",
        "id": str(test.id),  # retained for submit
        "question": test.description or test.title,
        "title": test.title,
        "description": test.description,
        "task": test.task or "ielts_listening",
        "type": test.type or "text",
        "order": test.test_order or 1,
        "is_active": test.is_active,
        "is_recommended": bool(test.is_recommended),
        "mock_test_order": test.mock_test_order,
        "created_at": test.created_at.isoformat() if test.created_at else None,
        "updated_at": test.updated_at.isoformat() if test.updated_at else None,
        "sections": [SectionOut.model_validate(s).model_dump() for s in test.sections],
    }


@router.get("/tests")
async def list_listening_tests(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ListeningTest)
        .where(ListeningTest.is_active == True)
        .options(
            selectinload(ListeningTest.sections)
            .selectinload(ListeningSection.subsections)
            .selectinload(ListeningSubsection.questions)
        )
        .order_by(ListeningTest.test_order)
    )
    tests = result.scalars().all()

    # Best band per test for this user, so the list arrives already showing the
    # completed/band state — no separate attempts request from the client.
    band_rows = await db.execute(
        select(TestAttempt.test_id, func.max(TestAttempt.overall_band))
        .where(
            TestAttempt.user_id == current_user.id,
            TestAttempt.module == ModuleType.listening,
            TestAttempt.status == GradingStatus.complete,
        )
        .group_by(TestAttempt.test_id)
    )
    best_bands = {row[0]: row[1] for row in band_rows.all()}

    return [
        {
            "id": str(t.id),
            "title": t.title,
            "description": t.description,
            "question_count": sum(
                len(sub.questions)
                for s in t.sections
                for sub in s.subsections
            ),
            "section_count": len(t.sections),
            "best_band": best_bands.get(str(t.id)),
        }
        for t in tests
    ]


@router.get("/tests/{test_id}")
async def get_listening_test(
    test_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    test = (await db.execute(
        select(ListeningTest)
        .where(ListeningTest.id == test_id, ListeningTest.is_active == True)
        .options(_load_options())
    )).scalar_one_or_none()
    if not test:
        raise HTTPException(404, "Test not found")
    return {"status": 200, "ok": True, "data": _serialize_test(test)}


@router.get("/for-session/{session_id}")
async def get_test_for_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sess_result = await db.execute(
        select(TestSession).where(
            TestSession.id == session_id,
            TestSession.user_id == current_user.id,
        )
    )
    session = sess_result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    ielts_result = await db.execute(
        select(IeltsTest).where(IeltsTest.id == session.ielts_test_id)
    )
    ielts_test = ielts_result.scalar_one_or_none()
    if not ielts_test or not ielts_test.listening_test_id:
        raise HTTPException(404, "No listening test linked to this IELTS test")

    test_result = await db.execute(
        select(ListeningTest)
        .where(ListeningTest.id == ielts_test.listening_test_id)
        .options(_load_options())
    )
    test = test_result.scalar_one_or_none()
    if not test:
        raise HTTPException(404, "Listening test not found")

    return {"status": 200, "ok": True, "data": _serialize_test(test)}


@router.post("/submit", response_model=ListeningResultOut, status_code=201)
async def submit_listening(
    body: SubmitListeningRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    test_result = await db.execute(
        select(ListeningTest)
        .where(ListeningTest.id == body.test_id)
        .options(_load_options())
    )
    test = test_result.scalar_one_or_none()
    if not test:
        raise HTTPException(404, "Test not found")

    question_results = []
    wrong_questions = []
    section_scores = {}

    is_pro = current_user.subscription == SubscriptionTier.pro

    for section in test.sections:
        sec_correct = 0
        sec_total = 0
        for subsection in section.subsections:
            for question in subsection.questions:
                qid = str(question.id)
                user_answer = body.answers.get(qid)
                is_correct = score_answer(question, user_answer)
                sec_total += 1

                if is_correct:
                    sec_correct += 1
                else:
                    wrong_questions.append(question)

                has_tip = bool(not is_correct and question.wrong_answer_tip)
                question_results.append(QuestionResult(
                    question_id=qid,
                    question_type=question.question_type,
                    text=question.stem,
                    user_answer=user_answer,
                    correct_answer=question.answer_key,
                    is_correct=is_correct,
                    tip=(question.wrong_answer_tip if (is_pro and not is_correct) else None),
                    has_tip=has_tip,
                ))

        section_scores[section.part] = {
            "correct": sec_correct,
            "total": sec_total,
            "band": calculate_band(sec_correct, sec_total),
        }

    total_correct = sum(s["correct"] for s in section_scores.values())
    total_questions = sum(s["total"] for s in section_scores.values())
    overall_band = calculate_band(total_correct, total_questions)
    tips = generate_tips(wrong_questions)

    attempt = TestAttempt(
        user_id=current_user.id,
        module=ModuleType.listening,
        status=GradingStatus.complete,
        overall_band=overall_band,
        test_id=str(body.test_id),
        subscores={
            "test_title": test.title,
            "sections": section_scores,
            "correct": total_correct,
            "total": total_questions,
        },
        raw_answers=body.answers,
        improvement_tips=tips,
        question_results=[qr.model_dump() for qr in question_results],
    )
    db.add(attempt)
    await db.flush()

    analytics.capture(current_user.firebase_uid, "test_completed", {
        "module": "listening",
        "test_id": str(body.test_id),
        "test_title": test.title,
        "band": overall_band,
        "correct": total_correct,
        "total": total_questions,
    })

    # No post-submission LLM call for listening. improvement_tips above already
    # come from generate_tips(), which uses each question's pre-generated
    # wrong_answer_tip from the DB (admin "generate tips" step) with generic
    # per-type fallbacks — and those same per-question tips are shown inline on
    # wrong answers in the report. Listening submit is fully deterministic, with
    # no Celery/Redis/LLM dependency.

    return ListeningResultOut(
        attempt_id=attempt.id,
        correct=total_correct,
        total=total_questions,
        overall_band=overall_band,
        section_scores=section_scores,
        question_results=question_results,
        improvement_tips=tips,
    )


@router.get("/attempts")
async def get_attempts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(TestAttempt)
        .where(
            TestAttempt.user_id == current_user.id,
            TestAttempt.module == ModuleType.listening,
            TestAttempt.status == GradingStatus.complete,
            TestAttempt.test_id.isnot(None),
        )
        .order_by(TestAttempt.created_at.desc())
        .limit(20)
    )).scalars().all()
    return [
        {
            "id": str(a.id),
            "test_id": a.test_id,
            "test_title": (a.subscores or {}).get("test_title"),
            "overall_band": a.overall_band,
            "correct": (a.subscores or {}).get("correct", 0),
            "total": (a.subscores or {}).get("total", 0),
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in rows
    ]


@router.get("/attempts/{attempt_id}")
async def get_attempt(
    attempt_id: str,
    lang: str = Query("en"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    attempt = (await db.execute(
        select(TestAttempt).where(
            TestAttempt.id == attempt_id,
            TestAttempt.user_id == current_user.id,
            TestAttempt.module == ModuleType.listening,
        )
    )).scalar_one_or_none()
    if not attempt:
        raise HTTPException(404, "Attempt not found")
    sc = attempt.subscores or {}
    is_pro = current_user.subscription == SubscriptionTier.pro

    # Reload current tips from DB so upgrades and newly generated tips are reflected
    stored_results = attempt.question_results or []
    wrong_qids = [int(qr["question_id"]) for qr in stored_results if not qr.get("is_correct") if qr.get("question_id")]
    tip_map: dict[str, str] = {}
    if wrong_qids:
        from app.models.listening import ListeningQuestion
        rows = (await db.execute(
            select(ListeningQuestion.id, ListeningQuestion.wrong_answer_tip)
            .where(ListeningQuestion.id.in_(wrong_qids))
        )).all()
        tip_map = {str(r.id): r.wrong_answer_tip for r in rows if r.wrong_answer_tip}

    enriched_results = [
        {
            **qr,
            "tip": (tip_map.get(str(qr.get("question_id"))) if is_pro else None),
            "has_tip": bool(tip_map.get(str(qr.get("question_id")))),
        }
        for qr in stored_results
    ]

    raw_tips = attempt.improvement_tips or []
    tips = await _translate_tips(raw_tips) if lang == "bn" else raw_tips

    return {
        "attempt_id": str(attempt.id),
        "test_id": attempt.test_id,
        "test_title": sc.get("test_title"),
        "correct": sc.get("correct", 0),
        "total": sc.get("total", 0),
        "overall_band": attempt.overall_band,
        "section_scores": sc.get("sections", {}),
        "question_results": enriched_results,
        "improvement_tips": tips,
        "created_at": attempt.created_at.isoformat() if attempt.created_at else None,
    }
