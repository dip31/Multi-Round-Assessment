"""Add interview_sessions, approved_question_pools, and interview_turns tables

Revision ID: add_interview_tables
Revises: add_advanced_proctoring_events
Create Date: 2026-03-21 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'add_interview_tables'
down_revision: Union[str, None] = 'add_advanced_proctoring_events'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create interview_sessions table
    op.create_table('interview_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('phase', sa.String(length=20), server_default='HR', nullable=False),
        sa.Column('current_turn', sa.Integer(), server_default='0', nullable=False),
        sa.Column('total_turns', sa.Integer(), server_default='10', nullable=False),
        sa.Column('rl_state', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['assessment_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('idx_interview_session'), 'interview_sessions', ['session_id'], unique=False)

    # Create approved_question_pools table
    op.create_table('approved_question_pools',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('extracted_skills', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
        sa.Column('extracted_projects', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('question_pool', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('admin_approved', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('approved_by', sa.Integer(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['assessment_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('idx_approved_pool_session'), 'approved_question_pools', ['session_id'], unique=False)
    op.create_index(op.f('idx_approved_pool_approved'), 'approved_question_pools', ['admin_approved'], unique=False)

    # Create interview_turns table
    op.create_table('interview_turns',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('interview_id', sa.Integer(), nullable=False),
        sa.Column('turn_number', sa.Integer(), nullable=False),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('question_difficulty', sa.String(length=10), nullable=True),
        sa.Column('candidate_response', sa.Text(), nullable=True),
        sa.Column('response_time_sec', sa.Float(), nullable=True),
        sa.Column('content_score', sa.Float(), nullable=True),
        sa.Column('behavioral_snapshot', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('rl_reward', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
        sa.ForeignKeyConstraint(['interview_id'], ['interview_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('idx_interview_turns_interview'), 'interview_turns', ['interview_id'], unique=False)
    op.create_index(op.f('idx_interview_turns_turn'), 'interview_turns', ['interview_id', 'turn_number'], unique=False)


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index(op.f('idx_interview_turns_turn'), table_name='interview_turns')
    op.drop_index(op.f('idx_interview_turns_interview'), table_name='interview_turns')
    op.drop_table('interview_turns')

    op.drop_index(op.f('idx_approved_pool_approved'), table_name='approved_question_pools')
    op.drop_index(op.f('idx_approved_pool_session'), table_name='approved_question_pools')
    op.drop_table('approved_question_pools')

    op.drop_index(op.f('idx_interview_session'), table_name='interview_sessions')
    op.drop_table('interview_sessions')
