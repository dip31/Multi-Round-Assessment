"""Add personalization fields to interview_sessions and interview_turns

Revision ID: add_personalization_001
Revises: b78ed14a3c15
Create Date: 2026-10-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'add_personalization_001'
down_revision: Union[str, None] = 'b78ed14a3c15'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # ── interview_sessions: add 6 personalization metadata columns ────
    is_cols = {col['name'] for col in inspector.get_columns('interview_sessions')}
    for col_name, col_def in [
        ('extraction_confidence',        sa.Column('extraction_confidence', sa.String(length=10), nullable=True)),
        ('retrieval_success_rate',       sa.Column('retrieval_success_rate', sa.Float(), nullable=True)),
        ('question_personalization_rate',sa.Column('question_personalization_rate', sa.Float(), nullable=True)),
        ('personalization_metadata',     sa.Column('personalization_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True)),
        ('follow_up_quality_score',      sa.Column('follow_up_quality_score', sa.Float(), nullable=True)),
        ('personalization_warnings',     sa.Column('personalization_warnings', postgresql.JSONB(astext_type=sa.Text()), nullable=True)),
    ]:
        if col_name not in is_cols:
            op.add_column('interview_sessions', col_def)

    # ── interview_turns: add 5 personalization metadata columns ───────
    it_cols = {col['name'] for col in inspector.get_columns('interview_turns')}
    for col_name, col_def in [
        ('personalization_source',           sa.Column('personalization_source', sa.String(length=200), nullable=True)),
        ('question_grounding_confidence',    sa.Column('question_grounding_confidence', sa.Float(), nullable=True)),
        ('answer_classification',            sa.Column('answer_classification', postgresql.JSONB(astext_type=sa.Text()), nullable=True)),
        ('followup_grounding_score',         sa.Column('followup_grounding_score', sa.Float(), nullable=True)),
        ('followup_targeted_aspect',         sa.Column('followup_targeted_aspect', sa.String(length=200), nullable=True)),
    ]:
        if col_name not in it_cols:
            op.add_column('interview_turns', col_def)


def downgrade() -> None:
    # ── interview_turns: drop 5 personalization metadata columns ──────
    op.drop_column('interview_turns', 'followup_targeted_aspect')
    op.drop_column('interview_turns', 'followup_grounding_score')
    op.drop_column('interview_turns', 'answer_classification')
    op.drop_column('interview_turns', 'question_grounding_confidence')
    op.drop_column('interview_turns', 'personalization_source')

    # ── interview_sessions: drop 6 personalization metadata columns ───
    op.drop_column('interview_sessions', 'personalization_warnings')
    op.drop_column('interview_sessions', 'follow_up_quality_score')
    op.drop_column('interview_sessions', 'personalization_metadata')
    op.drop_column('interview_sessions', 'question_personalization_rate')
    op.drop_column('interview_sessions', 'retrieval_success_rate')
    op.drop_column('interview_sessions', 'extraction_confidence')
