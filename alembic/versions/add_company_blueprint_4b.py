"""Phase 4B: Add company_blueprints table

Revision ID: add_company_blueprint_4b
Revises: add_company_data_4a
Create Date: 2026-10-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "add_company_blueprint_4b"
down_revision: Union[str, None] = "add_company_data_4a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "company_blueprints",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_name", sa.String(200), nullable=False),
        sa.Column("target_role", sa.String(150), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "blueprint_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("confidence_level", sa.String(50), nullable=False, server_default="medium"),
        sa.Column("evidence_sources_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("reviewed_by_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "status IN ('draft','approved','needs_revision')",
            name="chk_blueprint_status",
        ),
    )
    op.create_index("idx_blueprint_company", "company_blueprints", ["company_name"])
    op.create_index("idx_blueprint_role", "company_blueprints", ["target_role"])
    op.create_index("idx_blueprint_status", "company_blueprints", ["status"])
    op.create_index(
        "idx_blueprint_company_role",
        "company_blueprints",
        ["company_name", "target_role"],
    )


def downgrade() -> None:
    op.drop_index("idx_blueprint_company_role", table_name="company_blueprints")
    op.drop_index("idx_blueprint_status", table_name="company_blueprints")
    op.drop_index("idx_blueprint_role", table_name="company_blueprints")
    op.drop_index("idx_blueprint_company", table_name="company_blueprints")
    op.drop_table("company_blueprints")
