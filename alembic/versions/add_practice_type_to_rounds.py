"""add practice_type to assessment_rounds

Revision ID: add_practice_type_rounds
Revises: 545b4e6f20d4
Create Date: 2026-09-24 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_practice_type_rounds'
down_revision = '545b4e6f20d4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add practice_type column to assessment_rounds
    # Stores the specific practice variant: mcq, technical, combined, coding, interview
    # NULL for non-practice rounds (portfolio, mock_drive, etc.)
    op.add_column(
        'assessment_rounds',
        sa.Column('practice_type', sa.String(length=20), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('assessment_rounds', 'practice_type')
