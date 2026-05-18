"""create_session_problems_table

Revision ID: 002_session_problems
Revises: 001_timer_columns
Create Date: 2026-03-07 09:08:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = '002_session_problems'
down_revision = '001_timer_columns'
branch_labels = None
depends_on = None


def upgrade():
    # Create session_problems table
    op.create_table('session_problems',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('round_id', sa.Integer(),
                  sa.ForeignKey('assessment_rounds.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('problem_id', sa.Integer(),
                  sa.ForeignKey('coding_problems.id'),
                  nullable=False),
        sa.Column('problem_order', sa.Integer(), server_default='0'),
        sa.Column('assigned_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.UniqueConstraint('round_id', 'problem_id', name='uq_session_problem')
    )
    
    # Create index
    op.create_index('idx_session_problems_round', 'session_problems', ['round_id'])


def downgrade():
    # Drop index first
    op.drop_index('idx_session_problems_round')
    
    # Drop table
    op.drop_table('session_problems')
