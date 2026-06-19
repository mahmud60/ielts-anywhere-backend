"""add last_activity_at to sessions

Revision ID: d2e3f4a5b6c7
Revises: c1a2b3d4e5f6
Create Date: 2026-05-19
"""
from alembic import op
import sqlalchemy as sa

revision = 'd2e3f4a5b6c7'
down_revision = 'c1a2b3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'test_sessions',
        sa.Column('last_activity_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_column('test_sessions', 'last_activity_at')