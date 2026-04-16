from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.user import User
from app.models.test import TestAttempt, ModuleType, GradingStatus
from app.models.speaking import SpeakingTest
from app.models.ielts_test import IeltsTest, TestSession
from app.schemas.speaking import (
    SpeakingTestOut, SubmitSpeakingRequest,
    SpeakingResultOut, PartScore,
)
from app.api.routes.auth import get_current_user
from app.tasks.grading import grade_speaking_task

router = APIRouter(prefix="/speaking", tags=["speaking"])


@router.get("/for-session/{session_id}", response_model=SpeakingTestOut)
async def get_test_for_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns the speaking test linked to this session.
    Same session → IeltsTest → speaking_test_id pattern.
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
    if not ielts or not ielts.speaking_test_id:
        raise HTTPException(404, "No speaking test linked to this IELTS test")

    test = (await db.execute(
        select(SpeakingTest)
        .where(SpeakingTest.id == ielts.speaking_test_id)
        .options(selectinload(SpeakingTest.parts))
    )).scalar_one_or_none()
    if not test:
        raise HTTPException(404, "Speaking test not found")
    return test


@router.post("/submit", response_model=SpeakingResultOut, status_code=202)
async def submit_speaking(
    body: SubmitSpeakingRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Accepts the student's full speaking transcript and queues AI grading.
    Returns immediately with status="pending".
    Frontend polls GET /speaking/attempts/{id} until status=="complete".
    """
    # Validate test exists
    test = (await db.execute(
        select(SpeakingTest).where(SpeakingTest.id == body.test_id)
    )).scalar_one_or_none()
    if not test:
        raise HTTPException(404, "Test not found")

    if len(body.part_responses) != 3:
        raise HTTPException(400, "All three parts must be submitted together")

    # Build raw answers for storage
    raw_answers = {
        f"part{pr.part_number}": {
            "part_number": pr.part_number,
            "exchanges": pr.exchanges,
        }
        for pr in body.part_responses
    }

    attempt = TestAttempt(
        user_id=current_user.id,
        module=ModuleType.speaking,
        status=GradingStatus.pending,
        raw_answers=raw_answers,
    )
    db.add(attempt)
    await db.flush()

    # Queue Celery grading task
    part_responses_data = [
        {
            "part_number": pr.part_number,
            "exchanges": pr.exchanges,
        }
        for pr in body.part_responses
    ]
    grade_speaking_task.delay(str(attempt.id), part_responses_data)

    return SpeakingResultOut(
        attempt_id=attempt.id,
        status=GradingStatus.pending,
    )


@router.get("/attempts/{attempt_id}", response_model=SpeakingResultOut)
async def get_attempt(
    attempt_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns current grading state. Frontend polls this every 2s
    after submission until status == "complete" or "failed".
    """
    attempt = (await db.execute(
        select(TestAttempt).where(
            TestAttempt.id == attempt_id,
            TestAttempt.user_id == current_user.id,
        )
    )).scalar_one_or_none()
    if not attempt:
        raise HTTPException(404, "Attempt not found")

    if attempt.status != GradingStatus.complete or not attempt.subscores:
        # Include transcript from raw_answers so frontend can show it
        transcript = None
        if attempt.raw_answers:
            transcript = []
            for part_key in ["part1", "part2", "part3"]:
                part_data = attempt.raw_answers.get(part_key)
                if part_data:
                    for ex in part_data.get("exchanges", []):
                        transcript.append({
                            "part": part_data["part_number"],
                            "question": ex["question"],
                            "answer": ex["answer"],
                        })
        return SpeakingResultOut(
            attempt_id=attempt.id,
            status=attempt.status,
            transcript=transcript,
        )

    # Build PartScore list from subscores
    s = attempt.subscores
    part_scores = []
    for part_key, part_num, part_type in [
        ("part1", 1, "part1"),
        ("part2", 2, "part2"),
        ("part3", 3, "part3"),
    ]:
        if part_key in s:
            p = s[part_key]
            part_scores.append(PartScore(
                part_number=part_num,
                part_type=part_type,
                fluency_coherence=p["fluency_coherence"],
                lexical_resource=p["lexical_resource"],
                grammatical_range=p["grammatical_range"],
                pronunciation=p["pronunciation"],
                band=p["band"],
                feedback=p["feedback"],
                examiner_notes=p.get("examiner_notes"),
            ))

    # Rebuild transcript from raw_answers
    transcript = []
    if attempt.raw_answers:
        for part_key in ["part1", "part2", "part3"]:
            part_data = attempt.raw_answers.get(part_key)
            if part_data:
                for ex in part_data.get("exchanges", []):
                    transcript.append({
                        "part": part_data["part_number"],
                        "question": ex["question"],
                        "answer": ex["answer"],
                    })

    return SpeakingResultOut(
        attempt_id=attempt.id,
        status=attempt.status,
        overall_band=attempt.overall_band,
        part_scores=part_scores,
        improvement_tips=attempt.improvement_tips,
        transcript=transcript,
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
            TestAttempt.module == ModuleType.speaking,
        )
        .order_by(TestAttempt.created_at.desc())
        .limit(20)
    )
    return [
        {
            "id": str(a.id),
            "status": a.status,
            "overall_band": a.overall_band,
            "improvement_tips": a.improvement_tips,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in result.scalars().all()
    ]