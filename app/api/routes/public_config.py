"""
Public, unauthenticated client configuration.

Exists so the frontend can read values that are otherwise only knowable by
hardcoding them. Everything exposed here must be safe for anonymous callers —
no secrets, no per-user data.

Named public_config to avoid confusion with app.core.config (the settings
object), which is a different thing entirely.
"""

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/time-limits")
async def get_time_limits():
    """
    Per-module time limits, in seconds.

    Public because standalone practice tests (/listening/[testId] and friends)
    need a countdown but have no session to ask. The session flow does NOT use
    this: it calls GET /sessions/{id}/time-remaining, which is authoritative
    because the server records when the module actually started. This endpoint
    reports the configured DURATION only — it knows nothing about elapsed time.

    The admin equivalent (GET /admin/time-limits) returns the same values but is
    admin-gated, so it cannot serve the practice pages.
    """
    return {
        "listening": settings.LISTENING_TIME_LIMIT,
        "reading": settings.READING_TIME_LIMIT,
        "writing": settings.WRITING_TIME_LIMIT,
        "speaking": settings.SPEAKING_TIME_LIMIT,
    }
