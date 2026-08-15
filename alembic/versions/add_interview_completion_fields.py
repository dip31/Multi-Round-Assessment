"""add interview completion fields

Revision ID: add_interview_completion
Revises: rebuild_interview_pipeline
Create Date: 2026-08-06 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_interview_completion'
down_revision = 'rebuild_interview_pipeline'
branch_labels = None
depends_on = None


def upgrade():
    # Add status column with default 'ACTIVE'
    op.add_column('interview_sessions', 
        sa.Column('status', sa.String(length=20), server_default='ACTIVE', nullable=False))
    
    # Add completion_reason column (nullable)
    op.add_column('interview_sessions',
        sa.Column('completion_reason', sa.String(length=30), nullable=True))
    
    # Add completed_at column (nullable)
    op.add_column('interview_sessions',
        sa.Column('completed_at', sa.DateTime(timezone=False), nullable=True))


def downgrade():
    op.drop_column('interview_sessions', 'completed_at')
    op.drop_column('interview_sessions', 'completion_reason')
    op.drop_column('interview_sessions', 'status')
