"""add vocabulary_words table

Revision ID: c9d0e1f2a3b4
Revises: 07f44f6a391a
Create Date: 2026-06-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'c9d0e1f2a3b4'
down_revision = '07f44f6a391a'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'vocabulary_words',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('word', sa.String(100), nullable=False),
        sa.Column('module', sa.String(20), nullable=False),
        sa.Column('topic', sa.String(100), nullable=False),
        sa.Column('band', sa.String(10), nullable=False),
        sa.Column('part_of_speech', sa.String(30), nullable=True),
        sa.Column('definition', sa.Text(), nullable=True),
        sa.Column('example', sa.Text(), nullable=True),
        sa.Column('mnemonic', sa.Text(), nullable=True),
        sa.Column('collocations', JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('word'),
    )
    op.create_index('ix_vocabulary_words_id', 'vocabulary_words', ['id'])
    op.create_index('ix_vocabulary_words_word', 'vocabulary_words', ['word'])
    op.create_index('ix_vocabulary_words_module', 'vocabulary_words', ['module'])
    op.create_index('ix_vocabulary_words_topic', 'vocabulary_words', ['topic'])


def downgrade():
    op.drop_index('ix_vocabulary_words_topic', table_name='vocabulary_words')
    op.drop_index('ix_vocabulary_words_module', table_name='vocabulary_words')
    op.drop_index('ix_vocabulary_words_word', table_name='vocabulary_words')
    op.drop_index('ix_vocabulary_words_id', table_name='vocabulary_words')
    op.drop_table('vocabulary_words')
