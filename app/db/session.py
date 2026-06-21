from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,                      # drop dead connections before using them
    pool_size=settings.DB_POOL_SIZE,         # bounded so Cloud Run scaling doesn't
    max_overflow=settings.DB_MAX_OVERFLOW,   # exhaust the Postgres connection limit
    pool_recycle=1800,                       # recycle every 30 min (Supabase idle timeout)
    pool_timeout=30,
    echo=settings.DEBUG,
    connect_args={"statement_cache_size": 0},
)

AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise