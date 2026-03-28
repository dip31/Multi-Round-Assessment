"""Rebuild interview pipeline: add final_score, intent, parent_turn_id to interview_turns; seed new rl_state fields

Revision ID: rebuild_interview_pipeline
Revises: add_followup_columns
Create Date: 2026-03-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'rebuild_interview_pipeline'
down_revision: Union[str, None] = 'add_followup_columns'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1 — Ensure rl_state column is JSONB (no-op if already JSONB)
    op.execute(
        "ALTER TABLE interview_sessions "
        "ALTER COLUMN rl_state TYPE JSONB USING rl_state::JSONB"
    )

    # Step 2 — Add missing columns to interview_turns
    op.add_column(
        'interview_turns',
        sa.Column('final_score', sa.Float(), nullable=True)
    )
    op.add_column(
        'interview_turns',
        sa.Column('intent', sa.String(10), nullable=True)
    )
    op.add_column(
        'interview_turns',
        sa.Column(
            'parent_turn_id',
            sa.Integer(),
            sa.ForeignKey('interview_turns.id'),
            nullable=True,
        )
    )

    # Step 3 — Seed new rl_state fields for existing sessions
    op.execute("""
        UPDATE interview_sessions
        SET rl_state = rl_state || '{
            "negative_count": 0,
            "current_question_id": null,
            "conversation_history": []
        }'::jsonb
        WHERE rl_state IS NOT NULL
          AND NOT rl_state ? 'negative_count'
    """)


def downgrade() -> None:
    op.drop_column('interview_turns', 'parent_turn_id')
    op.drop_column('interview_turns', 'intent')
    op.drop_column('interview_turns', 'final_score')
