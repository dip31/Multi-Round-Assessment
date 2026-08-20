"""
Add session_problems table for coding round problem assignments

Revision ID: add_session_problems
Revises: rebuild_interview_pipeline
Create Date: 2026-05-22
"""
from alembic import op
import sqlalchemy as sa
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = 'add_session_problems'
down_revision: Union[str, Sequence[str], None] = 'rebuild_interview_pipeline'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'session_problems',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('round_id', sa.Integer(), sa.ForeignKey('assessment_rounds.id', ondelete='CASCADE'), nullable=False),
        sa.Column('problem_id', sa.Integer(), sa.ForeignKey('coding_problems.id', ondelete='CASCADE'), nullable=False),
        sa.Column('problem_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('marked_for_review', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('assigned_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index('idx_session_problems_round', 'session_problems', ['round_id'])


def downgrade() -> None:
    op.drop_index('idx_session_problems_round', table_name='session_problems')
    op.drop_table('session_problems')
