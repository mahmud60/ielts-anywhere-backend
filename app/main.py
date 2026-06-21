from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.sentry import init_sentry, capture_exception
from app.api.routes import auth, listening, reading, writing, speaking, sessions, admin, payments, dashboard, learn
from app.api.routes import affiliates
import asyncio
import traceback
from datetime import datetime, timezone, timedelta

init_sentry()


async def _cleanup_expired_sessions():
    """Delete in-progress sessions with no activity for 12+ hours. Runs every hour."""
    from sqlalchemy import delete
    from app.models.ielts_test import TestSession, SessionStatus
    from app.db.session import AsyncSessionLocal
    while True:
        await asyncio.sleep(3600)
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=12)
            async with AsyncSessionLocal() as db:
                await db.execute(
                    delete(TestSession).where(
                        TestSession.status == SessionStatus.in_progress,
                        TestSession.last_activity_at < cutoff,
                    )
                )
                await db.commit()
        except Exception as exc:
            capture_exception(exc)
            print("Session cleanup error:", traceback.format_exc())


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_cleanup_expired_sessions())
    yield
    task.cancel()


app = FastAPI(title=settings.APP_NAME, docs_url="/docs", lifespan=lifespan)

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    capture_exception(exc)
    print("UNHANDLED EXCEPTION:", traceback.format_exc())
    # Don't leak internal error details (DB messages, stack info) to clients in
    # production — the full exception is in the logs and Sentry.
    detail = str(exc) if settings.DEBUG else "Internal server error"
    return JSONResponse(status_code=500, content={"detail": detail})

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(listening.router)
app.include_router(reading.router)
app.include_router(writing.router)
app.include_router(speaking.router)
app.include_router(sessions.router)
app.include_router(admin.router)
app.include_router(payments.router)
app.include_router(dashboard.router)
app.include_router(learn.router)
app.include_router(affiliates.router)

@app.get("/health")
async def health():
    return {"status": "ok"}