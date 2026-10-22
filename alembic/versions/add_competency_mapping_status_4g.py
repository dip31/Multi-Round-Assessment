"""Add competency evidence mapping lifecycle status to assessment contexts.

Durable, per-assessment-context tracking of the competency evidence mapping
lifecycle (Phase 4C reliability). Nullable so legacy/non-Mock-Drive contexts are
untouched: NULL means "not tracked". No scores are stored.

Revision ID: add_competency_mapping_status_4g
Revises: add_competency_evidence_map_4f
Create Date: 2026-10-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "add_competency_mapping_status_4g"
down_revision: Union[str, Sequence[str], None] = "add_competency_evidence_map_4f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "assessment_contexts",
        sa.Column("competency_mapping_status", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "assessment_contexts",
        sa.Column("competency_mapping_error", sa.Text(), nullable=True),
    )
    op.add_column(
        "assessment_contexts",
        sa.Column("competency_mapping_attempted_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "assessment_contexts",
        sa.Column("competency_mapping_completed_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("assessment_contexts", "competency_mapping_completed_at")
    op.drop_column("assessment_contexts", "competency_mapping_attempted_at")
    op.drop_column("assessment_contexts", "competency_mapping_error")
    op.drop_column("assessment_contexts", "competency_mapping_status")
