"""add missing foreign keys for ai_usage + session attempt ids

These columns referenced other tables by id but had no FK constraint, so nothing
prevented orphan rows and deletes didn't cascade. Added with ON DELETE SET NULL
(all nullable) and NOT VALID so the constraint is enforced on new/updated rows
without scanning existing data — i.e. it cannot fail the migration on any
pre-existing orphan. (Run VALIDATE CONSTRAINT later if you want to verify history.)

Note: speaking_attempts.user_id is intentionally left out — it's stored as TEXT
(not UUID), so adding that FK needs a column type migration first.

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-06-28
"""
from alembic import op

revision = "a3b4c5d6e7f8"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None

# (table, column, ref_table, constraint_name)
_FKS = [
    ("ai_usage", "user_id", "users", "fk_ai_usage_user_id"),
    ("test_sessions", "listening_attempt_id", "test_attempts", "fk_test_sessions_listening_attempt"),
    ("test_sessions", "reading_attempt_id", "test_attempts", "fk_test_sessions_reading_attempt"),
    ("test_sessions", "writing_attempt_id", "test_attempts", "fk_test_sessions_writing_attempt"),
    ("test_sessions", "speaking_attempt_id", "test_attempts", "fk_test_sessions_speaking_attempt"),
]


def upgrade() -> None:
    for table, col, ref, name in _FKS:
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {name} "
            f"FOREIGN KEY ({col}) REFERENCES {ref}(id) ON DELETE SET NULL NOT VALID;"
        )


def downgrade() -> None:
    for table, _col, _ref, name in _FKS:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name};")
