"""Add mock_drives table for TPO-managed mock placement drives

Revision ID: add_mock_drive_001
Revises: fix_role_check_001
Create Date: 2026-09-27

Creates the mock_drives table that stores TPO-configured practice
placement drives (company, role, eligibility, selected rounds).
Assessment execution integration is deferred to a later phase.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "add_mock_drive_001"
down_revision: Union[str, None] = "fix_role_check_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mock_drives",
        sa.Column("id", sa.Integer(), nullable=False),
        # Drive identity
        sa.Column("company_name", sa.String(length=200), nullable=False),
        sa.Column("target_role", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        # Status: draft | published | active | completed
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="draft",
        ),
        # Drive-specific eligibility
        sa.Column(
            "minimum_cgpa",
            sa.Float(),
            nullable=False,
            server_default="6.0",
        ),
        sa.Column(
            "maximum_backlogs",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "eligible_branches",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        # Selected assessment rounds (dict of round_name → bool)
        sa.Column(
            "selected_rounds",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        # Ownership
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'active', 'completed')",
            name="mock_drives_status_check",
        ),
        sa.CheckConstraint(
            "minimum_cgpa >= 0.0 AND minimum_cgpa <= 10.0",
            name="mock_drives_cgpa_check",
        ),
        sa.CheckConstraint(
            "maximum_backlogs >= 0",
            name="mock_drives_backlogs_check",
        ),
    )
    op.create_index("idx_mock_drives_status", "mock_drives", ["status"], unique=False)
    op.create_index(
        "idx_mock_drives_created_by", "mock_drives", ["created_by_id"], unique=False
    )
    op.create_index(
        "idx_mock_drives_created_at", "mock_drives", ["created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("idx_mock_drives_created_at", table_name="mock_drives")
    op.drop_index("idx_mock_drives_created_by", table_name="mock_drives")
    op.drop_index("idx_mock_drives_status", table_name="mock_drives")
    op.drop_table("mock_drives")
