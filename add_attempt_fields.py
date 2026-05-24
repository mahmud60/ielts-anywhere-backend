"""
Add test_id and question_results columns to test_attempts.
Safe to run multiple times (uses IF NOT EXISTS).
"""
import os, psycopg2

db_url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
conn = psycopg2.connect(db_url)
cur = conn.cursor()
cur.execute("ALTER TABLE test_attempts ADD COLUMN IF NOT EXISTS test_id TEXT;")
cur.execute("ALTER TABLE test_attempts ADD COLUMN IF NOT EXISTS question_results JSONB;")
conn.commit()
cur.close()
conn.close()
print("Migration complete.")