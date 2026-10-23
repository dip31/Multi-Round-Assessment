"""add_portfolio_sharing_fields

Revision ID: 47555f247a64
Revises: b861c736eef4
Create Date: 2026-10-22 15:35:14.489950

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '47555f247a64'
down_revision: Union[str, None] = 'b861c736eef4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add share_token and is_public columns to student_profiles
    op.add_column('student_profiles', sa.Column('share_token', sa.String(64), nullable=True, unique=True))
    op.add_column('student_profiles', sa.Column('is_public', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    # Create index on share_token for fast lookups
    op.create_index('ix_student_profiles_share_token', 'student_profiles', ['share_token'], unique=True)


def downgrade() -> None:
    # Drop index first
    op.drop_index('ix_student_profiles_share_token', table_name='student_profiles')
    # Drop columns
    op.drop_column('student_profiles', 'is_public')
    op.drop_column('student_profiles', 'share_token')
