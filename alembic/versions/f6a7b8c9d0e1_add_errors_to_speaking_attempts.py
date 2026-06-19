"""add errors to speaking_attempts

Revision ID: f6a7b8c9d0e1
Revises: d2e3f4a5b6c7
Create Date: 2026-05-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'f6a7b8c9d0e1'
down_revision = 'd2e3f4a5b6c7'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'speaking_attempts',
        sa.Column('errors', JSONB, nullable=True),
    )


def downgrade():
    op.drop_column('speaking_attempts', 'errors')