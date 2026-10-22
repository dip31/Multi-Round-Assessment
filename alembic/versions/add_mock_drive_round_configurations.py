"""Persist per-round Mock Drive settings for blueprint generation.

Revision ID: mock_drive_round_configs_4d
Revises: add_blueprint_snapshots_4c
Create Date: 2026-10-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "mock_drive_round_configs_4d"
down_revision: Union[str, tuple[str, str], None] = (
    "add_blueprint_snapshots_4c",
    "aptitude_round_assignments_4c",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "mock_drives",
        sa.Column(
            "round_configurations",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("mock_drives", "round_configurations")
