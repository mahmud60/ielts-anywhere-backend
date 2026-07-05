"""add created_at to speaking_attempts

speaking_attempts was the only attempt table without a timestamp, which blocked
the stuck-attempt watchdog (sweep_stuck_attempts) from age-guarding speaking
grades. Backfills existing rows with now() via server_default.

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-07-04
"""
from alembic import op
import sqlalchemy as sa

revision = "c5d6e7f8a9b0"
down_revision = "b4c5d6e7f8a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "speaking_attempts",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("speaking_attempts", "created_at")
