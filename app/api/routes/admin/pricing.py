from fastapi import APIRouter, Depends

from app.models.user import User
from app.core.config import settings
from .deps import require_admin

router = APIRouter()


@router.get("/pricing")
async def get_pricing(
    _: User = Depends(require_admin),
):
    """
    Returns current pricing config from environment.
    In a real system this would be stored in DB for live editing.
    """
    return {
        # No payment gateway is wired up right now — LemonSqueezy was removed
        # pending its replacement, so there is no variant/price ID to report.
        "gateway": None,
        "currency": "USD",
        "plans": [
            {
                "name": "Free",
                "tier": "free",
                "price": 0,
                "features": [
                    "1 demo test",
                    "Listening + Reading only",
                    "No AI grading",
                ],
            },
            {
                "name": "Pro",
                "tier": "pro",
                "price": 19,
                "billing": "monthly",
                "features": [
                    "Unlimited full tests",
                    "All 4 modules",
                    "AI writing + speaking grading",
                    "Progress tracking",
                    "Improvement tips",
                ],
            },
        ],
    }


@router.get("/time-limits")
async def get_time_limits(_: User = Depends(require_admin)):
    """Returns current time limits for each module."""
    return {
        "listening": settings.LISTENING_TIME_LIMIT,
        "reading": settings.READING_TIME_LIMIT,
        "writing": settings.WRITING_TIME_LIMIT,
        "speaking": settings.SPEAKING_TIME_LIMIT,
    }
