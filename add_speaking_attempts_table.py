"""Migration: create speaking_attempts table for the ElevenLabs speaking flow."""
import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

raw_url = os.environ["DATABASE_URL"]
url = (
    raw_url
    .replace("postgresql+asyncpg://", "postgresql://")
    .replace("postgresql+psycopg2://", "postgresql://")
)

conn = psycopg2.connect(url)
conn.autocommit = True
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS speaking_attempts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         TEXT NOT NULL,
    status          TEXT DEFAULT 'in_progress',
    transcript      JSONB,
    overall_band                NUMERIC(2,1),
    fluency_coherence_band      NUMERIC(2,1),
    fluency_coherence_feedback  TEXT,
    lexical_resource_band       NUMERIC(2,1),
    lexical_resource_feedback   TEXT,
    grammatical_range_band      NUMERIC(2,1),
    grammatical_range_feedback  TEXT,
    pronunciation_band          NUMERIC(2,1),
    pronunciation_feedback      TEXT,
    examiner_summary            TEXT,
    elevenlabs_session_id       TEXT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    completed_at    TIMESTAMPTZ
);
""")

print("speaking_attempts table ready.")
cur.close()
conn.close()