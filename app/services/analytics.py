"""Server-side PostHog events.

Captures authoritative business events (subscription activation, referral
conversion) that the browser SDK can't see or could be blocked from sending.
Use the user's Firebase UID as ``distinct_id`` so these stitch together with
the frontend's identified person.

No-ops silently when ``POSTHOG_API_KEY`` is unset, and never raises into the
caller — analytics must not break a webhook or a request.
"""

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

_client = None
_init_attempted = False


def _get_client():
    global _client, _init_attempted
    if _init_attempted:
        return _client
    _init_attempted = True
    if not settings.POSTHOG_API_KEY:
        return None
    try:
        from posthog import Posthog

        _client = Posthog(
            settings.POSTHOG_API_KEY,
            host=settings.POSTHOG_HOST or "https://us.i.posthog.com",
        )
    except Exception:
        logger.warning("PostHog init failed; server-side analytics disabled", exc_info=True)
        _client = None
    return _client


def capture(distinct_id: str, event: str, properties: dict | None = None) -> None:
    """Fire-and-forget server-side event. Safe to call unconditionally."""
    client = _get_client()
    if client is None or not distinct_id:
        return
    try:
        client.capture(distinct_id=distinct_id, event=event, properties=properties or {})
    except Exception:
        logger.warning("PostHog capture failed for event '%s'", event, exc_info=True)


def track_test_completed(distinct_id: str, module: str, band, **props) -> None:
    """Emit the standard ``test_completed`` event with a consistent ``module`` +
    ``band`` base. Callers pass any module-specific fields as keyword args."""
    capture(distinct_id, "test_completed", {"module": module, "band": band, **props})
