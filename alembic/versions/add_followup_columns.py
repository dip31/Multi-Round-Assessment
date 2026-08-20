"""add followup columns to interview_turns

Revision ID: add_followup_columns
Revises: add_interview_tables
Create Date: 2026-03-25

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_followup_columns'
down_revision = 'add_interview_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add is_followup and followup_number columns to interview_turns."""
    op.add_column(
        'interview_turns',
        sa.Column('is_followup', sa.Boolean(), server_default=sa.text('false'), nullable=False)
    )
    op.add_column(
        'interview_turns',
        sa.Column('followup_number', sa.Integer(), server_default=sa.text('0'), nullable=False)
    )


def downgrade() -> None:
    """Remove followup columns."""
    op.drop_column('interview_turns', 'followup_number')
    op.drop_column('interview_turns', 'is_followup')
