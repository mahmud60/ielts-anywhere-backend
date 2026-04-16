from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.user import User
from app.models.test import TestAttempt, ModuleType, GradingStatus
from app.models.reading import ReadingTest, ReadingQuestion, ReadingPassage, ReadingQuestionGroup
from app.models.ielts_test import IeltsTest, TestSession
from app.schemas.reading import (
    ReadingTestOut, SubmitReadingRequest,
    ReadingResultOut, QuestionResult, PassageResult,
)
from app.api.routes.auth import get_current_user
from app.services.reading_scorer import score_answer, calculate_band, generate_tips

router = APIRouter(prefix="/reading", tags=["reading"])


def _load_options():
    """
    Eager-load chain: test → passages → question_groups → questions.
    The scorer needs question.group.question_type, so groups must
    be loaded whenever questions are loaded.
    """
    return selectinload(ReadingTest.passages).selectinload(
        ReadingTest.passages.property.mapper.class_.question_groups
    ).selectinload(
        ReadingPassage.question_groups
    )


def _load_options_simple():
    """Alternative using string-based relationship names."""
    return selectinload("passages").selectinload(
        "question_groups"
    ).selectinload("questions")


@router.get("/for-session/{session_id}", response_model=ReadingTestOut)
async def get_test_for_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Frontend calls this instead of fetching a test by ID directly.
    Walks: session → IeltsTest → reading_test_id → ReadingTest.
    Answer keys are never included in the response.
    """
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
        .options(
            selectinload(ReadingTest.passages)
            .selectinload(ReadingPassage.question_groups)
            .selectinload(ReadingQuestionGroup.questions)
        )
    )).scalar_one_or_none()
    if not test:
        raise HTTPException(404, "Reading test not found")
    return test


@router.post("/submit", response_model=ReadingResultOut, status_code=201)
async def submit_reading(
    body: SubmitReadingRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Scores all answers server-side and saves the attempt.
    The question.group relationship is loaded so the scorer
    can access question_type without extra queries.
    """
    test = (await db.execute(
        select(ReadingTest)
        .where(ReadingTest.id == body.test_id)
        .options(
            selectinload(ReadingTest.passages)
            .selectinload(ReadingPassage.question_groups)
            .selectinload(ReadingQuestionGroup.questions)
        )
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
                # Manually attach group so scorer can access question_type
                # without an extra DB hit (already in memory from selectinload)
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
        subscores={
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
    result = await db.execute(
        select(TestAttempt)
        .where(
            TestAttempt.user_id == current_user.id,
            TestAttempt.module == ModuleType.reading,
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