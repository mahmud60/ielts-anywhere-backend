"""restructure listening for new format

Revision ID: c1a2b3d4e5f6
Revises: b3cd5c984904
Create Date: 2026-05-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c1a2b3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'b3cd5c984904'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop old listening tables (dependent first)
    op.drop_table('listening_questions')
    op.drop_table('listening_sections')

    # Drop old questiontype enum if it exists
    op.execute("DROP TYPE IF EXISTS questiontype")

    # Add new columns to listening_tests
    op.add_column('listening_tests', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('listening_tests', sa.Column('task', sa.String(), nullable=True))
    op.add_column('listening_tests', sa.Column('type', sa.String(), nullable=True))
    op.add_column('listening_tests', sa.Column('order', sa.Integer(), nullable=True))
    op.add_column('listening_tests', sa.Column('is_recommended', sa.Boolean(), nullable=True))
    op.add_column('listening_tests', sa.Column('mock_test_order', sa.Integer(), nullable=True))

    # Create new listening_sections (Integer PK, part, audio)
    op.create_table(
        'listening_sections',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('test_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('listening_tests.id'), nullable=True),
        sa.Column('part', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(), nullable=True),
        sa.Column('audio', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Create new listening_subsections
    op.create_table(
        'listening_subsections',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('section_id', sa.Integer(), sa.ForeignKey('listening_sections.id'), nullable=True),
        sa.Column('order', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(), nullable=True),
        sa.Column('subsection_type', sa.String(), nullable=False, server_default='regular'),
        sa.Column('text', sa.Text(), nullable=True),
        sa.Column('visual', sa.JSON(), nullable=True),
        sa.Column('grid_headers', sa.JSON(), nullable=True),
        sa.Column('grid_cells', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Create new listening_questions (Integer PK, subsection FK)
    op.create_table(
        'listening_questions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('subsection_id', sa.Integer(), sa.ForeignKey('listening_subsections.id'), nullable=True),
        sa.Column('order', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(), nullable=True),
        sa.Column('question_type', sa.String(), nullable=False),
        sa.Column('ielts_question_type', sa.String(), nullable=True),
        sa.Column('text', sa.Text(), nullable=False, server_default=''),
        sa.Column('max_selected_options', sa.Integer(), nullable=True),
        sa.Column('options', sa.JSON(), nullable=True),
        sa.Column('answer_key', sa.JSON(), nullable=False),
        sa.Column('wrong_answer_tip', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('listening_questions')
    op.drop_table('listening_subsections')
    op.drop_table('listening_sections')

    op.drop_column('listening_tests', 'mock_test_order')
    op.drop_column('listening_tests', 'is_recommended')
    op.drop_column('listening_tests', 'order')
    op.drop_column('listening_tests', 'type')
    op.drop_column('listening_tests', 'task')
    op.drop_column('listening_tests', 'description')

    op.execute("CREATE TYPE questiontype AS ENUM ('mcq', 'fill', 'tfng', 'matching')")

    op.create_table(
        'listening_sections',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('test_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('listening_tests.id'), nullable=True),
        sa.Column('section_number', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(), nullable=True),
        sa.Column('context', sa.Text(), nullable=True),
        sa.Column('audio_url', sa.String(), nullable=True),
        sa.Column('audio_duration_seconds', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        'listening_questions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('section_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('listening_sections.id'), nullable=True),
        sa.Column('order_index', sa.Integer(), nullable=False),
        sa.Column('question_type', sa.Enum('mcq', 'fill', 'tfng', 'matching', name='questiontype'), nullable=False),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('options', sa.JSON(), nullable=True),
        sa.Column('matching_pool', sa.JSON(), nullable=True),
        sa.Column('answer_key', sa.JSON(), nullable=False),
        sa.Column('wrong_answer_tip', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )
