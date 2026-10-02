"""Link interview sessions to their assessment round.

Revision ID: link_interview_rounds
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "link_interview_rounds"
down_revision: Union[str, None] = "fix_role_check_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "interview_sessions",
        sa.Column(
            "round_id",
            sa.Integer(),
            sa.ForeignKey("assessment_rounds.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_interview_sessions_round_id",
        "interview_sessions",
        ["round_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_interview_sessions_round_id", table_name="interview_sessions")
    op.drop_column("interview_sessions", "round_id")
