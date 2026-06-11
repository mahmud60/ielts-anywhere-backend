from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from app.core.config import settings
from app.api.routes import auth, listening, reading, writing, speaking, sessions, admin, payments, dashboard, learn
from app.api.routes import affiliates
import asyncio
import traceback
from datetime import datetime, timezone, timedelta


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
        except Exception:
            print("Session cleanup error:", traceback.format_exc())


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_cleanup_expired_sessions())
    yield
    task.cancel()


app = FastAPI(title=settings.APP_NAME, docs_url="/docs", lifespan=lifespan)

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    print("UNHANDLED EXCEPTION:", traceback.format_exc())
    return JSONResponse(status_code=500, content={"detail": str(exc), "type": type(exc).__name__})

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://ielts-anywhere-frontend.vercel.app",
        "https://www.ieltsanywhere.com/"
    ],
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