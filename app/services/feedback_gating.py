from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select


BAND_DELTA_THRESHOLD = 0.5
ATTEMPTS_THRESHOLD = 5


async def should_generate_llm_feedback(
    db: AsyncSession,
    user_id,
    module: str,
    current_band: float,
) -> bool:
    """
    Returns True if an LLM feedback call should be made for this attempt.

    Rules (any one triggers):
    - First ever attempt for this module
    - Band score changed by >= 0.5 since last LLM feedback
    - 5+ attempts have passed since last LLM feedback
    """
    from app.models.test import TestAttempt
    from app.models.user import User

    user = (await db.execute(
        select(User).where(User.id == user_id)
    )).scalar_one_or_none()

    if not user:
        return False

    state = (user.feedback_state or {}).get(module)

    if state is None:
        return True  # first attempt for this module

    count = (await db.execute(
        select(func.count()).where(
            TestAttempt.user_id == user_id,
            TestAttempt.module == module,
        )
    )).scalar() or 0

    band_delta = abs(current_band - (state.get("last_band") or 0))
    attempts_since = count - (state.get("last_attempt_number") or 0)

    return band_delta >= BAND_DELTA_THRESHOLD or attempts_since >= ATTEMPTS_THRESHOLD