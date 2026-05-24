from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.user import User
from app.models.test import TestAttempt, ModuleType, GradingStatus
from app.models.reading import ReadingTest, ReadingPassage, ReadingQuestionGroup, ReadingQuestion
from app.models.ielts_test import IeltsTest, TestSession
from app.schemas.reading import (
    SubmitReadingRequest,
    ReadingResultOut, QuestionResult, PassageResult,
)
from app.api.routes.auth import get_current_user
from app.services.reading_scorer import score_answer, calculate_band, generate_tips

router = APIRouter(prefix="/reading", tags=["reading"])


def _load_options():
    """Eager-load chain: test → passages → question_groups → questions."""
    return (
        selectinload(ReadingTest.passages)
        .selectinload(ReadingPassage.question_groups)
        .selectinload(ReadingQuestionGroup.questions)
    )


def _serialize_test(test: ReadingTest) -> dict:
    return {
        "id": str(test.id),
        "title": test.title,
        "test_type": test.test_type,
        "passages": [
            {
                "id": str(p.id),
                "passage_number": p.passage_number,
                "title": p.title,
                "body": p.body,
                "paragraphs": p.paragraphs,
                "question_groups": [
                    {
                        "id": str(g.id),
                        "order_index": g.order_index,
                        "question_type": g.question_type.value,
                        "instruction": g.instruction,
                        "heading_options": g.heading_options,
                        "paragraph_labels": g.paragraph_labels,
                        "word_limit": g.word_limit,
                        "subsection_type": g.subsection_type,
                        "title": g.title,
                        "questions": [
                            {
                                "id": str(q.id),
                                "order_index": q.order_index,
                                "question_text": q.question_text,
                                "options": q.options,
                                "group_label": q.group_label,
                                "max_selected_options": q.max_selected_options,
                                # answer_key intentionally absent
                            }
                            for q in g.questions
                        ],
                    }
                    for g in p.question_groups
                ],
            }
            for p in test.passages
        ],
    }


@router.get("/tests")
async def list_reading_tests(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ReadingTest)
        .where(ReadingTest.is_active == True)
        .options(_load_options())
        .order_by(ReadingTest.test_order)
    )
    tests = result.scalars().all()
    return [
        {
            "id": str(t.id),
            "title": t.title,
            "test_type": t.test_type,
            "passage_count": len(t.passages),
            "question_count": sum(
                len(q.questions)
                for p in t.passages
                for q in p.question_groups
            ),
        }
        for t in tests
    ]


@router.get("/tests/{test_id}")
async def get_reading_test(
    test_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    test = (await db.execute(
        select(ReadingTest)
        .where(ReadingTest.id == test_id, ReadingTest.is_active == True)
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
    session = (await db.execute(
        select(TestSession).where(
            TestSession.id == session_id,
            TestSession.user_id == current_user.id,
        )
    )).scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    ielts = (await db.execute(
        select(IeltsTest).where(IeltsTest.id == session.ielts_test_id)
    )).scalar_one_or_none()
    if not ielts or not ielts.reading_test_id:
        raise HTTPException(404, "No reading test linked to this IELTS test")

    test = (await db.execute(
        select(ReadingTest)
        .where(ReadingTest.id == ielts.reading_test_id)
        .options(_load_options())
    )).scalar_one_or_none()
    if not test:
        raise HTTPException(404, "Reading test not found")

    return {"status": 200, "ok": True, "data": _serialize_test(test)}


@router.post("/submit", response_model=ReadingResultOut, status_code=201)
async def submit_reading(
    body: SubmitReadingRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    test = (await db.execute(
        select(ReadingTest)
        .where(ReadingTest.id == body.test_id)
        .options(_load_options())
    )).scalar_one_or_none()
    if not test:
        raise HTTPException(404, "Test not found")

    passage_results: list[PassageResult] = []
    question_results: list[QuestionResult] = []
    wrong_questions: list[ReadingQuestion] = []

    for passage in test.passages:
        p_correct = 0
        p_total = 0

        for group in passage.question_groups:
            for question in group.questions:
                question.group = group

                qid = str(question.id)
                user_answer = body.answers.get(qid)
                is_correct = score_answer(question, user_answer)

                if is_correct:
                    p_correct += 1
                else:
                    wrong_questions.append(question)
                p_total += 1

                question_results.append(QuestionResult(
                    question_id=qid,
                    question_type=group.question_type.value,
                    question_text=question.question_text,
                    user_answer=user_answer,
                    correct_answer=question.answer_key,
                    is_correct=is_correct,
                    tip=question.wrong_answer_tip if not is_correct else None,
                ))

        passage_results.append(PassageResult(
            passage_number=passage.passage_number,
            passage_title=passage.title,
            correct=p_correct,
            total=p_total,
            band=calculate_band(p_correct, p_total),
        ))

    total_correct = sum(p.correct for p in passage_results)
    total_questions = sum(p.total for p in passage_results)
    overall_band = calculate_band(total_correct, total_questions)
    tips = generate_tips(wrong_questions)

    attempt = TestAttempt(
        user_id=current_user.id,
        module=ModuleType.reading,
        status=GradingStatus.complete,
        overall_band=overall_band,
        test_id=str(body.test_id),
        subscores={
            "test_title": test.title,
            "passages": [
                {
                    "passage_number": p.passage_number,
                    "title": p.passage_title,
                    "correct": p.correct,
                    "total": p.total,
                    "band": p.band,
                }
                for p in passage_results
            ],
            "correct": total_correct,
            "total": total_questions,
        },
        raw_answers=body.answers,
        improvement_tips=tips,
        question_results=[qr.model_dump() for qr in question_results],
    )
    db.add(attempt)
    await db.flush()

    return ReadingResultOut(
        attempt_id=attempt.id,
        correct=total_correct,
        total=total_questions,
        overall_band=overall_band,
        passage_results=passage_results,
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
            TestAttempt.module == ModuleType.reading,
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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    attempt = (await db.execute(
        select(TestAttempt).where(
            TestAttempt.id == attempt_id,
            TestAttempt.user_id == current_user.id,
            TestAttempt.module == ModuleType.reading,
        )
    )).scalar_one_or_none()
    if not attempt:
        raise HTTPException(404, "Attempt not found")
    sc = attempt.subscores or {}
    return {
        "attempt_id": str(attempt.id),
        "test_id": attempt.test_id,
        "test_title": sc.get("test_title"),
        "correct": sc.get("correct", 0),
        "total": sc.get("total", 0),
        "overall_band": attempt.overall_band,
        "passage_results": sc.get("passages", []),
        "question_results": attempt.question_results or [],
        "improvement_tips": attempt.improvement_tips or [],
        "created_at": attempt.created_at.isoformat() if attempt.created_at else None,
    }