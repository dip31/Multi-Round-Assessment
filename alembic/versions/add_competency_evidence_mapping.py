"""Additive evidence-to-competency mapping table (Phase 4C Part 4, Stage 2).

Stores only the explicit relationship between a raw assessment evidence record
and a competency configured on the pinned blueprint snapshot. No competency
score is stored. Nullable for legacy data: no existing rows are touched.

Revision ID: add_competency_evidence_map_4f
Revises: add_question_pool_generation_4e
Create Date: 2026-10-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "add_competency_evidence_map_4f"
down_revision: Union[str, Sequence[str], None] = "add_question_pool_generation_4e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "competency_evidence_mappings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "candidate_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "context_id",
            sa.Integer(),
            sa.ForeignKey("assessment_contexts.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("assessment_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "round_id",
            sa.Integer(),
            sa.ForeignKey("assessment_rounds.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("evidence_type", sa.String(length=40), nullable=False),
        sa.Column("evidence_id", sa.Integer(), nullable=False),
        sa.Column("competency_id", sa.String(length=120), nullable=False),
        sa.Column("competency_name", sa.String(length=200), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("blueprint_version", sa.Integer(), nullable=True),
        sa.Column(
            "raw_metric",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "evidence_type",
            "evidence_id",
            "competency_id",
            name="uq_competency_evidence_mapping",
        ),
    )
    for column in ("id", "candidate_id", "context_id", "session_id", "round_id"):
        op.create_index(
            f"ix_competency_evidence_mappings_{column}",
            "competency_evidence_mappings",
            [column],
        )


def downgrade() -> None:
    for column in ("round_id", "session_id", "context_id", "candidate_id", "id"):
        op.drop_index(
            f"ix_competency_evidence_mappings_{column}",
            table_name="competency_evidence_mappings",
        )
    op.drop_table("competency_evidence_mappings")
