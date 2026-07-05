"""Shared test setup.

Provides dummy settings so importing app.* modules works in CI without real
secrets — the writing grader, for example, builds an Anthropic client at import
time from settings. The listening/reading scorers don't need these, but setting
them is harmless and keeps every import path working.
"""
import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/test")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
