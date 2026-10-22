"""Persist blueprint configuration snapshots for Mock Drive assessments.

Revision ID: add_blueprint_snapshots_4c
Revises: add_blueprint_mock_drive_4c
Create Date: 2026-10-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "add_blueprint_snapshots_4c"
down_revision: Union[str, None] = "add_blueprint_mock_drive_4c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "mock_drives",
        sa.Column(
            "blueprint_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "assessment_contexts",
        sa.Column(
            "blueprint_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("assessment_contexts", "blueprint_snapshot")
    op.drop_column("mock_drives", "blueprint_snapshot")
