"""Add composite indexes for production query patterns

Revision ID: add_production_indexes
Revises: add_interview_completion
Create Date: 2026-08-16

These composite indexes are justified by existing query patterns found in
the codebase audit (Stage 1, PHASE 3):

1. assessment_rounds(session_id, round_type, status)
   – used by session_service.get_user_active_round (every round lookup)
   – used by report_router completion-rate counts

2. coding_submissions(round_id, problem_id)
   – used by coding_service.finalize_coding_round best-score-per-problem query

3. interview_turns(interview_id, is_followup)
   – used by every interview report query to split main vs followup turns

4. advanced_proctoring_events(session_id, event_type)
   – used by advanced_proctoring_service.get_session_proctoring_summary

Individual FK columns already have index=True on the models; these composites
cover multi-column WHERE clauses that the single-column indexes cannot serve
efficiently.
"""
from alembic import op


revision = 'add_production_indexes'
down_revision = 'add_interview_completion'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        'ix_assessment_rounds_session_type_status',
        'assessment_rounds',
        ['session_id', 'round_type', 'status'],
        unique=False,
    )
    op.create_index(
        'ix_coding_submissions_round_problem',
        'coding_submissions',
        ['round_id', 'problem_id'],
        unique=False,
    )
    op.create_index(
        'ix_interview_turns_interview_followup',
        'interview_turns',
        ['interview_id', 'is_followup'],
        unique=False,
    )
    op.create_index(
        'ix_adv_proctoring_events_session_type',
        'advanced_proctoring_events',
        ['session_id', 'event_type'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_adv_proctoring_events_session_type', table_name='advanced_proctoring_events')
    op.drop_index('ix_interview_turns_interview_followup', table_name='interview_turns')
    op.drop_index('ix_coding_submissions_round_problem', table_name='coding_submissions')
    op.drop_index('ix_assessment_rounds_session_type_status', table_name='assessment_rounds')
