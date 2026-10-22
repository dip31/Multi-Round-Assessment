"""Add mock_drive_id FK to assessment_contexts for Phase 3 linking

Revision ID: add_mock_drive_ctx_001
Revises: add_mock_drive_001
Create Date: 2026-09-27
"""

from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "add_mock_drive_ctx_001"
down_revision: Union[str, None] = "add_mock_drive_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("assessment_contexts")}
    if "mock_drive_id" not in cols:
        op.add_column(
            "assessment_contexts",
            sa.Column("mock_drive_id", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            "fk_assessment_contexts_mock_drive_id",
            "assessment_contexts",
            "mock_drives",
            ["mock_drive_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(
            "idx_assessment_contexts_mock_drive_id",
            "assessment_contexts",
            ["mock_drive_id"],
        )


def downgrade() -> None:
    op.drop_index("idx_assessment_contexts_mock_drive_id",
                  table_name="assessment_contexts")
    op.drop_constraint("fk_assessment_contexts_mock_drive_id",
                       "assessment_contexts", type_="foreignkey")
    op.drop_column("assessment_contexts", "mock_drive_id")
