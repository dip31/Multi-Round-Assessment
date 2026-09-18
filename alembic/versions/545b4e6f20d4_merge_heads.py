"""merge heads

Revision ID: 545b4e6f20d4
Revises: add_interview_completion, merge_sp_violations
Create Date: 2026-08-17 14:05:48.973901

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '545b4e6f20d4'
down_revision: Union[str, None] = ('add_interview_completion', 'merge_sp_violations')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
