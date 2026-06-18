from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "IELTS ANYWHERE"
    DEBUG: bool = False

    DATABASE_URL: str
    ANTHROPIC_API_KEY: str
    REDIS_URL: str

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