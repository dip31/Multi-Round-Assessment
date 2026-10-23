"""merge_dual_heads

Revision ID: b861c736eef4
Revises: f1ded62ef3b4, pg_functions_triggers
Create Date: 2026-10-22 15:34:45.659790

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b861c736eef4'
down_revision: Union[str, None] = ('f1ded62ef3b4', 'pg_functions_triggers')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
