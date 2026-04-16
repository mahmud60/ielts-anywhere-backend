from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.user import User
from app.models.test import TestAttempt, ModuleType, GradingStatus
from app.models.listening import ListeningTest, ListeningSection
from app.models.ielts_test import IeltsTest, TestSession
from app.schemas.listening import (
    ListeningTestOut, SubmitListeningRequest,
    ListeningResultOut, QuestionResult, 
)
from app.api.routes.auth import get_current_user
from app.services.listening_scorer import score_answer, calculate_band, generate_tips

router = APIRouter(prefix="/listening", tags=["listening"])


def _load_test_options():
    """SQLAlchemy eager-load chain: test → sections → questions."""
    return selectinload(ListeningTest.sections).selectinload(
        ListeningSection.questions
    )


@router.get("/for-session/{session_id}", response_model=ListeningTestOut)
async def get_test_for_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    The frontend calls this instead of /listening/tests.
    Given a session ID, it finds the correct listening test by
    walking: session → IeltsTest → listening_test_id → ListeningTest.

    This is the key link — the frontend never needs to know
    which listening test ID belongs to which IELTS test.
    """
    # Verify session belongs to this user
    sess_result = await db.execute(
        select(TestSession).where(
            TestSession.id == session_id,
            TestSession.user_id == current_user.id,
        )
    )
    session = sess_result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    # Walk to the IeltsTest to get the listening_test_id
    ielts_result = await db.execute(
        select(IeltsTest).where(IeltsTest.id == session.ielts_test_id)
    )
    ielts_test = ielts_result.scalar_one_or_none()
    if not ielts_test or not ielts_test.listening_test_id:
        raise HTTPException(404, "No listening test linked to this IELTS test")

    # Load the full listening test with all sections and questions
    test_result = await db.execute(
        select(ListeningTest)
        .where(ListeningTest.id == ielts_test.listening_test_id)
        .options(_load_test_options())
    )
    test = test_result.scalar_one_or_none()
    if not test:
        raise HTTPException(404, "Listening test not found")
    return test


@router.post("/submit", response_model=ListeningResultOut, status_code=201)
async def submit_listening(
    body: SubmitListeningRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Scores all answers server-side and saves the attempt.
    Answer keys are loaded here — they never leave the backend.
    """
    test_result = await db.execute(
        select(ListeningTest)
        .where(ListeningTest.id == body.test_id)
        .options(_load_test_options())
    )
    test = test_result.scalar_one_or_none()
    if not test:
        raise HTTPException(404, "Test not found")

    question_results = []
    wrong_questions = []
    section_scores = {}

    for section in test.sections:
        sec_correct = 0
        for question in section.questions:
            qid = str(question.id)
            user_answer = body.answers.get(qid)
            is_correct = score_answer(question, user_answer)

            if is_correct:
                sec_correct += 1
            else:
                wrong_questions.append(question)

            question_results.append(QuestionResult(
                question_id=qid,
                question_type=question.question_type.value,
                question_text=question.question_text,
                user_answer=user_answer,
                correct_answer=question.answer_key,
                is_correct=is_correct,
                tip=question.wrong_answer_tip if not is_correct else None,
            ))

        sec_total = len(section.questions)
        section_scores[section.section_number] = {
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
    """User's full listening attempt history."""
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