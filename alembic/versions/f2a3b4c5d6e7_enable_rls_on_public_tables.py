"""enable row level security on all public tables

Closes the Supabase "rls_disabled_in_public" warning: without RLS, every table is
readable/writable through the auto-exposed anonymous PostgREST API. Enabling RLS
(with no policies) denies that anonymous access.

The FastAPI backend connects as Supabase's `postgres` service role, which has
BYPASSRLS, so the app is completely unaffected — this only locks down the public
REST API. (If you later need PostgREST access, add explicit policies.)

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-06-28
"""
from alembic import op

revision = "f2a3b4c5d6e7"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
DO $$
DECLARE t text;
BEGIN
  FOR t IN
    SELECT tablename FROM pg_tables
    WHERE schemaname = 'public' AND tablename <> 'alembic_version'
  LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY;', t);
  END LOOP;
END $$;
""")


def downgrade() -> None:
    op.execute("""
DO $$
DECLARE t text;
BEGIN
  FOR t IN
    SELECT tablename FROM pg_tables
    WHERE schemaname = 'public' AND tablename <> 'alembic_version'
  LOOP
    EXECUTE format('ALTER TABLE public.%I DISABLE ROW LEVEL SECURITY;', t);
  END LOOP;
END $$;
""")
