"""merge heads

Revision ID: becbadd33c98
Revises: 20260924_baseline, add_interviewer_id_001
Create Date: 2026-10-01 00:37:54.816957

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'becbadd33c98'
down_revision: Union[str, None] = ('20260924_baseline', 'add_interviewer_id_001')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
