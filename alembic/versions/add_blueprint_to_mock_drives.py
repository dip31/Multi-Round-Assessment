"""Phase 4C Part 1: Add blueprint_id and blueprint_version to mock_drives table

Revision ID: add_blueprint_mock_drive_4c
Revises: add_company_blueprint_4b
Create Date: 2026-10-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "add_blueprint_mock_drive_4c"
down_revision: Union[str, None] = "add_company_blueprint_4b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("mock_drives", sa.Column("blueprint_id", sa.Integer(), nullable=True))
    op.add_column("mock_drives", sa.Column("blueprint_version", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_mock_drives_blueprint_id",
        "mock_drives",
        "company_blueprints",
        ["blueprint_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("idx_mock_drives_blueprint_id", "mock_drives", ["blueprint_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_mock_drives_blueprint_id", table_name="mock_drives")
    op.drop_constraint("fk_mock_drives_blueprint_id", "mock_drives", type_="foreignkey")
    op.drop_column("mock_drives", "blueprint_version")
    op.drop_column("mock_drives", "blueprint_id")
