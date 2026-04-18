from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.routes import auth, listening, reading, writing, speaking, sessions, admin, payments, dashboard, learn

app = FastAPI(title=settings.APP_NAME, docs_url="/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
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