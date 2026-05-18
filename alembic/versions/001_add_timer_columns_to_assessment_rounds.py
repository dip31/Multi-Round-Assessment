"""add_timer_columns_to_assessment_rounds

Revision ID: 001_timer_columns
Revises: 
Create Date: 2026-03-07 09:06:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = '001_timer_columns'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Add time_limit_minutes column
    op.add_column('assessment_rounds',
        sa.Column('time_limit_minutes', sa.Integer(), nullable=True))
    
    # Add end_time column
    op.add_column('assessment_rounds',
        sa.Column('end_time', sa.DateTime(), nullable=True))


def downgrade():
    # Remove columns in reverse order
    op.drop_column('assessment_rounds', 'end_time')
    op.drop_column('assessment_rounds', 'time_limit_minutes')
