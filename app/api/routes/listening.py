from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.user import User
from app.models.test import TestAttempt, ModuleType, GradingStatus
from app.models.listening import ListeningTest, ListeningSection, ListeningSubsection
from app.models.ielts_test import IeltsTest, TestSession
from app.schemas.listening import (
    SectionOut,
    SubmitListeningRequest,
    ListeningResultOut, QuestionResult,
)
from app.api.routes.auth import get_current_user
from app.services.listening_scorer import score_answer, calculate_band, generate_tips

router = APIRouter(prefix="/listening", tags=["listening"])


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

                question_results.append(QuestionResult(
                    question_id=qid,
                    question_type=question.question_type,
                    text=question.stem,
                    user_answer=user_answer,
                    correct_answer=question.answer_key,
                    is_correct=is_correct,
                    tip=question.wrong_answer_tip if not is_correct else None,
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
        subscores={"sections": section_scores, "correct": total_correct, "total": total_questions},
        raw_answers=body.answers,
        improvement_tips=tips,
    )
    db.add(attempt)
    await db.flush()

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
    result = await db.execute(
        select(TestAttempt)
        .where(
            TestAttempt.user_id == current_user.id,
            TestAttempt.module == ModuleType.listening,
        )
        .order_by(TestAttempt.created_at.desc())
        .limit(20)
    )
    return [
        {
            "id": str(a.id),
            "overall_band": a.overall_band,
            "subscores": a.subscores,
            "improvement_tips": a.improvement_tips,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in result.scalars().all()
    ]
