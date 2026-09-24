"""Fix users role check constraint to include faculty and tpo

Revision ID: fix_role_check_001
Revises: add_personalization_001
Create Date: 2026-09-24 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'fix_role_check_001'
down_revision: Union[str, None] = 'add_personalization_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop old constraint that only allowed student/admin
    op.drop_constraint('users_role_check', 'users', type_='check')
    # Add new constraint that includes all valid roles
    op.create_check_constraint(
        'users_role_check',
        'users',
        "role IN ('student', 'admin', 'faculty', 'tpo')",
    )


def downgrade() -> None:
    op.drop_constraint('users_role_check', 'users', type_='check')
    op.create_check_constraint(
        'users_role_check',
        'users',
        "role IN ('student', 'admin')",
    )
