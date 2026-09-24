"""merge practice_type and context_policy

Revision ID: b78ed14a3c15
Revises: add_context_policy_m2e, add_practice_type_rounds
Create Date: 2026-09-24 00:17:27.205621

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b78ed14a3c15'
down_revision: Union[str, None] = ('add_context_policy_m2e', 'add_practice_type_rounds')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
