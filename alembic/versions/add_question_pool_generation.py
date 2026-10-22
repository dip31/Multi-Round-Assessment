"""Pre-candidate generated question pool registry + generated-content provenance columns.

Additive migration: adds blueprint-scoped provenance columns to aptitude_questions
and coding_problems (NULL for all seeded rows, so existing behavior is untouched)
and the generated_question_pools registry table used to gate publishing and to
scope Phase 4C to generated pools only when they are complete.

Revision ID: add_question_pool_generation_4e
Revises: mock_drive_round_configs_4d
Create Date: 2026-10-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "add_question_pool_generation_4e"
down_revision: Union[str, Sequence[str], None] = "mock_drive_round_configs_4d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_GENERATED_COLUMNS = [
    sa.Column("source", sa.String(length=30), nullable=True),
    sa.Column("source_batch", sa.String(length=64), nullable=True),
    sa.Column("company_name", sa.String(length=200), nullable=True),
    sa.Column("target_role", sa.String(length=150), nullable=True),
    sa.Column(
        "blueprint_id",
        sa.Integer(),
        sa.ForeignKey("company_blueprints.id", ondelete="SET NULL"),
        nullable=True,
    ),
    sa.Column("blueprint_version", sa.Integer(), nullable=True),
]


def upgrade() -> None:
    for table in ("aptitude_questions", "coding_problems"):
        for column in _GENERATED_COLUMNS:
            op.add_column(table, column)
        op.create_index(
            f"ix_{table}_blueprint_id", table, ["blueprint_id"]
        )

    op.create_table(
        "generated_question_pools",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "blueprint_id",
            sa.Integer(),
            sa.ForeignKey("company_blueprints.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("blueprint_version", sa.Integer(), nullable=False),
        sa.Column("company_name", sa.String(length=200), nullable=False),
        sa.Column("target_role", sa.String(length=150), nullable=False),
        sa.Column("round_type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("batch_id", sa.String(length=64), nullable=True),
        sa.Column("required_count", sa.Integer(), nullable=False),
        sa.Column("validated_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("generation_error", sa.Text(), nullable=True),
        sa.Column(
            "content",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "created_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "blueprint_id",
            "blueprint_version",
            "round_type",
            name="uq_generated_pool_blueprint_version_round",
        ),
    )
    op.create_index("ix_generated_question_pools_id", "generated_question_pools", ["id"])
    op.create_index(
        "ix_generated_question_pools_blueprint_id",
        "generated_question_pools",
        ["blueprint_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_generated_question_pools_blueprint_id", table_name="generated_question_pools")
    op.drop_index("ix_generated_question_pools_id", table_name="generated_question_pools")
    op.drop_table("generated_question_pools")
    for table in ("coding_problems", "aptitude_questions"):
        op.drop_index(f"ix_{table}_blueprint_id", table_name=table)
        for column in reversed(_GENERATED_COLUMNS):
            op.drop_column(table, column.name)
