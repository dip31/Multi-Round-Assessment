"""Persist the pinned aptitude question set for each assessment round.

Revision ID: aptitude_round_assignments_4c
Revises: add_blueprint_snapshots_4c
Create Date: 2026-10-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "aptitude_round_assignments_4c"
down_revision: Union[str, None] = "add_blueprint_snapshots_4c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "aptitude_round_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("round_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("question_order", sa.Integer(), nullable=False),
        sa.Column(
            "assigned_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["round_id"], ["assessment_rounds.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["question_id"], ["aptitude_questions.id"]),
        sa.UniqueConstraint(
            "round_id", "question_id", name="uq_aptitude_round_question"
        ),
        sa.UniqueConstraint(
            "round_id", "question_order", name="uq_aptitude_round_question_order"
        ),
    )
    op.create_index(
        "ix_aptitude_round_questions_id", "aptitude_round_questions", ["id"]
    )


def downgrade() -> None:
    op.drop_index("ix_aptitude_round_questions_id", table_name="aptitude_round_questions")
    op.drop_table("aptitude_round_questions")
