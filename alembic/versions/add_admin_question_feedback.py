"""Add admin_question_feedback table for question review actions

Revision ID: add_admin_question_feedback
Revises: rebuild_interview_pipeline
Create Date: 2026-04-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_admin_question_feedback'
down_revision: Union[str, None] = 'rebuild_interview_pipeline'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'admin_question_feedback',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('question_id', sa.Integer(), nullable=False),
        sa.Column('admin_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=20), nullable=False),
        sa.Column('suggestion', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['question_id'], ['aptitude_questions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['admin_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_admin_question_feedback_id', 'admin_question_feedback', ['id'], unique=False)
    op.create_index('ix_admin_question_feedback_question_id', 'admin_question_feedback', ['question_id'], unique=False)
    op.create_index('ix_admin_question_feedback_admin_id', 'admin_question_feedback', ['admin_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_admin_question_feedback_admin_id', table_name='admin_question_feedback')
    op.drop_index('ix_admin_question_feedback_question_id', table_name='admin_question_feedback')
    op.drop_index('ix_admin_question_feedback_id', table_name='admin_question_feedback')
    op.drop_table('admin_question_feedback')
