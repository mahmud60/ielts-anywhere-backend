"""add affiliate discount_code

Revision ID: d1e2f3a4b5c6
Revises: c9d0e1f2a3b4
Create Date: 2026-06-15

"""
from alembic import op
import sqlalchemy as sa

revision = 'd1e2f3a4b5c6'
down_revision = 'c9d0e1f2a3b4'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('affiliates', sa.Column('discount_code', sa.String(100), nullable=True))


def downgrade():
    op.drop_column('affiliates', 'discount_code')
