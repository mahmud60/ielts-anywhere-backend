from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.api.routes import auth, listening, reading, writing, speaking, sessions, admin, payments, dashboard, learn
import traceback

app = FastAPI(title=settings.APP_NAME, docs_url="/docs")

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    print("UNHANDLED EXCEPTION:", traceback.format_exc())
    return JSONResponse(status_code=500, content={"detail": str(exc), "type": type(exc).__name__})

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://ielts-anywhere-frontend.vercel.app"
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

@app.get("/health")
async def health():
    return {"status": "ok"}