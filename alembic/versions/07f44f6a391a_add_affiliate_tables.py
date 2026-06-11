"""add_affiliate_tables

Revision ID: 07f44f6a391a
Revises: a1b2c3d4e5f6
Create Date: 2026-06-11 12:43:03.651652

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '07f44f6a391a'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('affiliates',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('code', sa.String(length=50), nullable=False),
    sa.Column('commission_rate', sa.Numeric(precision=5, scale=4), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id')
    )
    op.create_index(op.f('ix_affiliates_code'), 'affiliates', ['code'], unique=True)
    op.create_table('affiliate_referrals',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('affiliate_id', sa.UUID(), nullable=False),
    sa.Column('referred_user_id', sa.UUID(), nullable=True),
    sa.Column('order_id', sa.String(length=100), nullable=True),
    sa.Column('order_amount', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('commission_amount', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('status', sa.Enum('pending', 'confirmed', 'paid', name='referralstatus'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['affiliate_id'], ['affiliates.id'], ),
    sa.ForeignKeyConstraint(['referred_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('order_id')
    )
    op.create_index(op.f('ix_affiliate_referrals_affiliate_id'), 'affiliate_referrals', ['affiliate_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_affiliate_referrals_affiliate_id'), table_name='affiliate_referrals')
    op.drop_table('affiliate_referrals')
    op.drop_index(op.f('ix_affiliates_code'), table_name='affiliates')
    op.drop_table('affiliates')
    op.execute("DROP TYPE IF EXISTS referralstatus")
