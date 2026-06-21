"""Per-user rate limiting for expensive (AI-cost) endpoints.

A small fixed-window counter in Redis, exposed as a FastAPI dependency:

    @router.post("/submit", dependencies=[Depends(rate_limit("writing_submit", 30))])

It is deliberately **fail-open** — if Redis is unreachable the request is allowed
through, since a limiter outage must never take down the API. Limits are sized
generously so real users never hit them; they exist to cap runaway/abusive use
that would otherwise rack up Anthropic/OpenAI spend.
"""

import logging
import ssl

from fastapi import Depends, HTTPException

from app.core.config import settings
from app.models.user import User
from app.api.routes.auth import get_current_user

logger = logging.getLogger(__name__)

_redis = None


def _get_client():
    global _redis
    if _redis is None:
        import redis.asyncio as redis_async

        kwargs = {
            "decode_responses": True,
            # Fail fast so a Redis outage can't hang a submit — the limiter is
            # fail-open, so a quick error just means the request is allowed.
            "socket_connect_timeout": 2,
            "socket_timeout": 2,
            "retry_on_timeout": False,
        }
        if settings.REDIS_URL.startswith("rediss://"):
            kwargs["ssl_cert_reqs"] = ssl.CERT_NONE
        _redis = redis_async.from_url(settings.REDIS_URL, **kwargs)
    return _redis


def rate_limit(scope: str, limit: int, window_seconds: int = 3600):
    """Return a dependency that allows at most `limit` calls per user per window."""

    async def _dependency(current_user: User = Depends(get_current_user)) -> None:
        try:
            client = _get_client()
            key = f"ratelimit:{scope}:{current_user.id}"
            count = await client.incr(key)
            if count == 1:
                await client.expire(key, window_seconds)
        except Exception:
            logger.warning("Rate limit check failed for %s; allowing request", scope, exc_info=True)
            return

        if count > limit:
            raise HTTPException(
                status_code=429,
                detail="You're doing that a lot — please wait a bit and try again.",
            )

    return _dependency
