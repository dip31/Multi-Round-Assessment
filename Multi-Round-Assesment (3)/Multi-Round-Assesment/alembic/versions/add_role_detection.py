"""Add detected_role column to approved_question_pools.

Revision ID: add_role_detection
Revises: rebuild_interview_pipeline
Create Date: 2026-05-02
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_role_detection'
down_revision: Union[str, None] = 'add_admin_question_feedback'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'approved_question_pools',
        sa.Column('detected_role', sa.String(length=50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('approved_question_pools', 'detected_role')
