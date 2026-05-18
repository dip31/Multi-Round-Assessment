"""add_marked_for_review_to_session_problems

Revision ID: 003_marked_for_review
Revises: 002_session_problems
Create Date: 2026-03-07 09:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003_marked_for_review'
down_revision = '002_session_problems'
branch_labels = None
depends_on = None


def upgrade():
    # Add marked_for_review column to session_problems
    op.add_column('session_problems',
        sa.Column('marked_for_review', sa.Boolean(),
                  server_default=sa.text('false'), nullable=False))


def downgrade():
    op.drop_column('session_problems', 'marked_for_review')
