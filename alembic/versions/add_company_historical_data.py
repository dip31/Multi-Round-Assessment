"""Phase 4A: Add company_historical_data and company_patterns tables

Revision ID: add_company_data_4a
Revises: add_mock_drive_ctx_001
Create Date: 2026-09-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "add_company_data_4a"
down_revision: Union[str, None] = "add_mock_drive_ctx_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── company_historical_data ───────────────────────────────────────
    op.create_table(
        "company_historical_data",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_name", sa.String(200), nullable=False),
        sa.Column("target_role", sa.String(150), nullable=False),
        sa.Column("source_type", sa.String(30), nullable=False, server_default="manual"),
        sa.Column("label", sa.String(200), nullable=False, server_default="Historical Drive"),
        sa.Column("file_name", sa.String(255), nullable=True),
        sa.Column("file_path", sa.String(500), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column(
            "raw_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "source_type IN ('manual','file_upload','pre_seeded')",
            name="chk_historical_source_type",
        ),
    )
    op.create_index("idx_hist_company", "company_historical_data", ["company_name"])
    op.create_index("idx_hist_role", "company_historical_data", ["target_role"])
    op.create_index("idx_hist_created_by", "company_historical_data", ["created_by_id"])
    op.create_index(
        "idx_hist_company_role",
        "company_historical_data",
        ["company_name", "target_role"],
    )

    # ── company_patterns ─────────────────────────────────────────────
    op.create_table(
        "company_patterns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_name", sa.String(200), nullable=False),
        sa.Column("target_role", sa.String(150), nullable=False),
        sa.Column(
            "pattern_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("source_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("company_name", "target_role", name="uq_company_pattern"),
    )
    op.create_index("idx_pattern_company", "company_patterns", ["company_name"])
    op.create_index("idx_pattern_role", "company_patterns", ["target_role"])


def downgrade() -> None:
    op.drop_index("idx_pattern_role", table_name="company_patterns")
    op.drop_index("idx_pattern_company", table_name="company_patterns")
    op.drop_table("company_patterns")

    op.drop_index("idx_hist_company_role", table_name="company_historical_data")
    op.drop_index("idx_hist_created_by", table_name="company_historical_data")
    op.drop_index("idx_hist_role", table_name="company_historical_data")
    op.drop_index("idx_hist_company", table_name="company_historical_data")
    op.drop_table("company_historical_data")
