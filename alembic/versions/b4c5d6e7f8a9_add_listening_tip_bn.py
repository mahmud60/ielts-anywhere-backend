"""add wrong_answer_tip_bn to listening_questions

Stores the pre-translated Bengali version of each question's wrong_answer_tip so
the listening report's EN/BN toggle can be served straight from the DB, with no
per-read LLM translation call. Populated by the tip-generation / backfill tasks.

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-06-29
"""
from alembic import op
import sqlalchemy as sa

revision = "b4c5d6e7f8a9"
down_revision = "a3b4c5d6e7f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "listening_questions",
        sa.Column("wrong_answer_tip_bn", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("listening_questions", "wrong_answer_tip_bn")
