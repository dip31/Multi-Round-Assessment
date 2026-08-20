"""
Merge heads: attach `add_session_problems` branch to main chain

Revision ID: merge_sp_violations
Revises: add_proctoring_violations, add_session_problems
Create Date: 2026-05-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'merge_sp_violations'
down_revision: Union[str, Sequence[str], None] = ('add_proctoring_violations', 'add_session_problems')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # This is a no-op merge revision to resolve multiple heads.
    pass


def downgrade() -> None:
    # Downgrade would be a no-op for the merge marker.
    pass
