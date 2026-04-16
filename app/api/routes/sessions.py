from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone

from app.db.session import get_db
from app.models.user import User
from app.models.test import TestAttempt, ModuleType
from app.models.ielts_test import IeltsTest, TestSession, SessionStatus
from app.schemas.ielts_test import (
    IeltsTestOut, TestSessionOut, StartSessionRequest
)
from app.api.routes.auth import get_current_user
from app.core.config import settings
from app.models.user import SubscriptionTier

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _current_module(session: TestSession) -> str:

    if not session.listening_attempt_id:
        return "listening"
    if not session.reading_attempt_id:
        return "reading"
    if not session.writing_attempt_id:
        return "writing"
    if not session.speaking_attempt_id:
        return "speaking"
    return "complete"


def _to_out(session: TestSession) -> TestSessionOut:
    current_mod = _current_module(session)
    limits = {
        "listening": settings.LISTENING_TIME_LIMIT,
        "reading": settings.READING_TIME_LIMIT,
        "writing": settings.WRITING_TIME_LIMIT,
        "speaking": settings.SPEAKING_TIME_LIMIT,
    }
    return TestSessionOut(
        id=session.id,
        ielts_test_id=session.ielts_test_id,
        status=session.status,
        listening_attempt_id=session.listening_attempt_id,
        reading_attempt_id=session.reading_attempt_id,
        writing_attempt_id=session.writing_attempt_id,
        speaking_attempt_id=session.speaking_attempt_id,
        module_bands=session.module_bands or {},
        current_module=_current_module(session),
        time_limit_seconds=limits.get(current_mod, 3600),
    )


@router.get("/tests", response_model=list[IeltsTestOut])
async def list_tests(db: AsyncSession = Depends(get_db)):
    """
    Public — no auth needed.
    Returns all active IELTS tests for the selection screen.
    """
    result = await db.execute(
        select(IeltsTest).where(IeltsTest.is_active == True)
    )
    return result.scalars().all()

@router.post("/{session_id}/start-module", response_model=TestSessionOut)
async def start_module(
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

    current_mod = _current_module(session)
    if current_mod == "complete":
        return _to_out(session)

    started = dict(session.module_started_at or {})
    if current_mod not in started:
        started[current_mod] = datetime.now(timezone.utc).isoformat()
        session.module_started_at = started
        await db.flush()

    return _to_out(session)


@router.get("/{session_id}/time-remaining")
async def get_time_remaining(
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

    current_mod = _current_module(session)
    if current_mod == "complete":
        return {"module": "complete", "seconds_remaining": 0, "limit": 0, "expired": False}

    limits = {
        "listening": settings.LISTENING_TIME_LIMIT,
        "reading":   settings.READING_TIME_LIMIT,
        "writing":   settings.WRITING_TIME_LIMIT,
        "speaking":  settings.SPEAKING_TIME_LIMIT,
    }
    limit = limits.get(current_mod, 3600)
    started_at_str = (session.module_started_at or {}).get(current_mod)

    # Module hasn't been started yet — return full limit
    if not started_at_str:
        return {
            "module": current_mod,
            "seconds_remaining": limit,
            "limit": limit,
            "expired": False,
        }

    started_at = datetime.fromisoformat(started_at_str.replace("Z", "+00:00"))
    elapsed = int((datetime.now(timezone.utc) - started_at).total_seconds())
    remaining = max(0, limit - elapsed)

    return {
        "module": current_mod,
        "seconds_remaining": remaining,
        "limit": limit,
        "expired": remaining == 0,
    }

@router.post("/start", response_model=TestSessionOut, status_code=201)
async def start_session(
    body: StartSessionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Creates a new session — or returns the existing in-progress
    session for this user + test so refreshing never loses progress.
    """
    # Return existing in-progress session if one exists
    existing = (await db.execute(
        select(TestSession).where(
            TestSession.user_id == current_user.id,
            TestSession.ielts_test_id == body.ielts_test_id,
            TestSession.status == SessionStatus.in_progress,
        )
    )).scalar_one_or_none()
    if existing:
        return _to_out(existing)

    # Verify the test exists
    ielts_test = (await db.execute(
        select(IeltsTest).where(IeltsTest.id == body.ielts_test_id)
    )).scalar_one_or_none()
    if not ielts_test.is_demo and current_user.subscription == SubscriptionTier.free:
        raise HTTPException(
            403,
            "This test requires a Pro subscription. "
            "Upgrade at /pricing to access all tests."
        )
    if not ielts_test:
        raise HTTPException(404, "Test not found")

    session = TestSession(
        user_id=current_user.id,
        ielts_test_id=body.ielts_test_id,
        module_bands={"listening": None, "reading": None, "writing": None, "speaking": None},
    )
    db.add(session)
    await db.flush()
    return _to_out(session)


@router.get("/my", response_model=list[TestSessionOut])
async def get_my_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """All sessions for the current user, newest first."""
    result = await db.execute(
        select(TestSession)
        .where(TestSession.user_id == current_user.id)
        .order_by(TestSession.created_at.desc())
        .limit(20)
    )
    return [_to_out(s) for s in result.scalars().all()]


@router.get("/{session_id}", response_model=TestSessionOut)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns current session state. Frontend polls this to know which module is next."""
    session = (await db.execute(
        select(TestSession).where(
            TestSession.id == session_id,
            TestSession.user_id == current_user.id,
        )
    )).scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")
    return _to_out(session)


@router.post("/{session_id}/complete-module", response_model=TestSessionOut)
async def complete_module(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Called by the frontend immediately after a module is submitted.

    Finds the most recent completed TestAttempt for the current module,
    links it to the session, caches the band score, and returns the
    updated session — which now has the next module as current_module.

    This keeps the module submit routes completely independent of sessions.
    The session just hooks in after the fact.
    """
    session = (await db.execute(
        select(TestSession).where(
            TestSession.id == session_id,
            TestSession.user_id == current_user.id,
        )
    )).scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    current_mod = _current_module(session)
    if current_mod == "complete":
        return _to_out(session)

    # Find the most recent completed attempt for this module
    attempt = (await db.execute(
        select(TestAttempt)
        .where(
            TestAttempt.user_id == current_user.id,
            TestAttempt.module == ModuleType(current_mod),
        )
        .order_by(TestAttempt.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()

    if not attempt:
        raise HTTPException(400, f"No completed {current_mod} attempt found. Submit the module first.")

    # Link to session and cache band score
    setattr(session, f"{current_mod}_attempt_id", attempt.id)
    bands = dict(session.module_bands or {})
    bands[current_mod] = attempt.overall_band
    session.module_bands = bands

    # Mark complete if all done
    if _current_module(session) == "complete":
        session.status = SessionStatus.completed
        session.completed_at = datetime.now(timezone.utc)

    await db.flush()
    return _to_out(session)


@router.get("/{session_id}/results")
async def get_results(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Full results for a completed session — all band scores and tips."""
    session = (await db.execute(
        select(TestSession).where(
            TestSession.id == session_id,
            TestSession.user_id == current_user.id,
        )
    )).scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    bands = session.module_bands or {}
    done = [v for v in bands.values() if v is not None]
    overall = round(sum(done) / len(done) * 2) / 2 if done else None

    tips = {}
    for mod in ["listening", "reading", "writing", "speaking"]:
        attempt_id = getattr(session, f"{mod}_attempt_id")
        if attempt_id:
            att = (await db.execute(
                select(TestAttempt).where(TestAttempt.id == attempt_id)
            )).scalar_one_or_none()
            if att:
                tips[mod] = att.improvement_tips or []

    return {
        "session_id": str(session.id),
        "status": session.status,
        "overall_band": overall,
        "module_bands": bands,
        "improvement_tips": tips,
    }