from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.user import User
from app.models.test import TestAttempt, ModuleType, GradingStatus
from app.models.writing import WritingTest, WritingTask
from app.models.ielts_test import IeltsTest, TestSession
from app.schemas.writing import (
    WritingTestOut, SubmitWritingRequest,
    WritingResultOut, TaskScore,
)
from app.api.routes.auth import get_current_user
from app.tasks.grading import grade_writing_task

router = APIRouter(prefix="/writing", tags=["writing"])


@router.get("/for-session/{session_id}", response_model=WritingTestOut)
async def get_test_for_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns the writing test linked to this session.
    Same pattern as listening and reading — frontend never needs
    to know which writing test ID belongs to which IELTS test.
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
    if not ielts or not ielts.writing_test_id:
        raise HTTPException(404, "No writing test linked to this IELTS test")

    test = (await db.execute(
        select(WritingTest)
        .where(WritingTest.id == ielts.writing_test_id)
        .options(selectinload(WritingTest.tasks))
    )).scalar_one_or_none()
    if not test:
        raise HTTPException(404, "Writing test not found")
    return test


@router.post("/submit", response_model=WritingResultOut, status_code=202)
async def submit_writing(
    body: SubmitWritingRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Accepts the student's written responses and queues AI grading.

    Returns immediately with status="pending" — the frontend polls
    GET /writing/attempts/{attempt_id} until status becomes "complete".

    Why async? Claude Haiku takes 3-8 seconds per grading call.
    Making the student wait for an HTTP response that long is bad UX
    and risks connection timeouts.
    """
    # Load the test to get task prompts for the grading prompt
    test = (await db.execute(
        select(WritingTest)
        .where(WritingTest.id == body.test_id)
        .options(selectinload(WritingTest.tasks))
    )).scalar_one_or_none()
    if not test:
        raise HTTPException(404, "Test not found")

    # Validate responses are present for both tasks
    tasks_by_id = {str(t.id): t for t in test.tasks}
    task1 = next((t for t in test.tasks if t.task_number == 1), None)
    task2 = next((t for t in test.tasks if t.task_number == 2), None)
    if not task1 or not task2:
        raise HTTPException(400, "Writing test must have exactly 2 tasks")

    task1_response = body.responses.get(str(task1.id), "").strip()
    task2_response = body.responses.get(str(task2.id), "").strip()

    if not task1_response:
        raise HTTPException(400, "Task 1 response is required")
    if not task2_response:
        raise HTTPException(400, "Task 2 response is required")

    # Save the attempt immediately with status=pending
    attempt = TestAttempt(
        user_id=current_user.id,
        module=ModuleType.writing,
        status=GradingStatus.pending,
        raw_answers={
            str(task1.id): task1_response,
            str(task2.id): task2_response,
        },
    )
    db.add(attempt)
    await db.flush()

    # Queue the Celery grading task — non-blocking, returns immediately
    grade_writing_task.delay(
        str(attempt.id),
        {
            "task1_prompt": task1.prompt,
            "task1_response": task1_response,
            "task1_type": task1.task_type.value,
            "task2_prompt": task2.prompt,
            "task2_response": task2_response,
        },
    )

    return WritingResultOut(
        attempt_id=attempt.id,
        status=GradingStatus.pending,
    )


@router.get("/attempts/{attempt_id}", response_model=WritingResultOut)
async def get_attempt(
    attempt_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns the current state of a writing attempt.
    Frontend polls this every 2 seconds after submission until
    status == "complete" or "failed".
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
        return WritingResultOut(
            attempt_id=attempt.id,
            status=attempt.status,
        )

    # Build structured task scores from stored subscores
    s = attempt.subscores
    task_scores = []
    for task_key, task_num, task_type in [
        ("task1", 1, "task1_academic"),
        ("task2", 2, "task2"),
    ]:
        if task_key in s:
            t = s[task_key]
            task_scores.append(TaskScore(
                task_number=task_num,
                task_type=task_type,
                task_achievement=t["task_achievement"],
                coherence_cohesion=t["coherence_cohesion"],
                lexical_resource=t["lexical_resource"],
                grammatical_range=t["grammatical_range"],
                band=t["band"],
                feedback=t["feedback"],
                word_count=t.get("word_count", 0),
            ))

    return WritingResultOut(
        attempt_id=attempt.id,
        status=attempt.status,
        overall_band=attempt.overall_band,
        task_scores=task_scores,
        improvement_tips=attempt.improvement_tips,
    )


@router.get("/attempts")
async def get_attempts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """User's writing attempt history."""
    result = await db.execute(
        select(TestAttempt)
        .where(
            TestAttempt.user_id == current_user.id,
            TestAttempt.module == ModuleType.writing,
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