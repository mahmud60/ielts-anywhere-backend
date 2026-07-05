"""Sentry error monitoring.

Initialized once per process (the FastAPI API and the Celery worker each call
``init_sentry()`` at startup). The FastAPI/Starlette and Celery integrations
auto-enable when those packages are present, so unhandled request errors and
failed tasks are captured automatically.

No-ops without ``SENTRY_DSN``. The ``sentry_sdk`` import is lazy so the package
is only required when a DSN is actually configured, and init/capture never raise
into the caller.
"""

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

_initialized = False


def init_sentry() -> None:
    """Initialize Sentry once per process. Safe to call repeatedly."""
    global _initialized
    if _initialized or not settings.SENTRY_DSN:
        return
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.SENTRY_ENVIRONMENT,
            traces_sample_rate=0.0,   # errors only — no performance-sampling cost
            send_default_pii=False,
        )
        _initialized = True
    except Exception:
        logger.warning("Sentry init failed; error monitoring disabled", exc_info=True)


def capture_exception(exc) -> None:
    """Explicitly report an exception (no-op if Sentry isn't initialized)."""
    if not _initialized:
        return
    try:
        import sentry_sdk

        sentry_sdk.capture_exception(exc)
    except Exception:
        pass


def capture_message(message: str, level: str = "error") -> None:
    """Explicitly report a message event (no-op if Sentry isn't initialized).
    Used for conditions worth alerting on that aren't exceptions — e.g. the
    watchdog having to fail out attempts that got stuck."""
    if not _initialized:
        return
    try:
        import sentry_sdk

        sentry_sdk.capture_message(message, level=level)
    except Exception:
        pass
