from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "IELTS ANYWHERE"
    DEBUG: bool = False

    DATABASE_URL: str
    ANTHROPIC_API_KEY: str
    REDIS_URL: str

    # Comma-separated list of allowed CORS origins (frontend domains).
    ALLOWED_ORIGINS: str = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "https://ielts-anywhere-frontend.vercel.app,https://ieltsanywhere.com"
    )

    # DB connection pool per process — keep bounded so Cloud Run scaling does not
    # exhaust the Postgres connection limit (use the Supabase pooler for headroom).
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 5

    FIREBASE_SERVICE_ACCOUNT_PATH: str = 'firebase-service-account.json'

    # LemonSqueezy
    LEMONSQUEEZY_API_KEY: str = ""
    LEMONSQUEEZY_WEBHOOK_SECRET: str = ""
    LEMONSQUEEZY_PRO_VARIANT_ID: str = ""   # the variant ID of your Pro plan

    # Cloudflare R2
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = ""
    R2_PUBLIC_URL: str = ""   # e.g. https://pub-xxx.r2.dev

    # OpenAI (TTS in speaking agent)
    OPENAI_API_KEY: str = ""

    # LiveKit (WebRTC transport for speaking agent)
    LIVEKIT_API_KEY: str = ""
    LIVEKIT_API_SECRET: str = ""
    LIVEKIT_URL: str = ""          # e.g. wss://your-app.livekit.cloud

    # Deepgram (STT in speaking agent)
    DEEPGRAM_API_KEY: str = ""

    # Google AI (Gemini LLM in speaking agent) — env var read by livekit-plugins-google
    GOOGLE_API_KEY: str = ""

    # Email (Resend — https://resend.com)
    RESEND_API_KEY: str = ""
    FROM_EMAIL: str = "noreply@ieltsanywhere.app"

    # PostHog (product analytics — server-side events). Use the project's
    # write-only API key; same key the frontend uses.
    POSTHOG_API_KEY: str = ""
    POSTHOG_HOST: str = "https://us.i.posthog.com"

    # Sentry (error monitoring). Blank disables it (no-op).
    SENTRY_DSN: str = ""
    SENTRY_ENVIRONMENT: str = "production"

    # Time limits per module in seconds
    # Real IELTS: Listening 30min, Reading 60min, Writing 60min, Speaking 15min
    LISTENING_TIME_LIMIT: int = 1800   # 30 minutes
    READING_TIME_LIMIT: int = 3600     # 60 minutes
    WRITING_TIME_LIMIT: int = 3600     # 60 minutes
    SPEAKING_TIME_LIMIT: int = 900     # 15 minutes

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()