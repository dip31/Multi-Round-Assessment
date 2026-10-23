"""Post-baseline consolidation: add missing tables and final schema fixes

Revision ID: post_baseline_consolidated
Revises: 20260924_baseline
Create Date: 2026-10-21

This migration consolidates all schema changes introduced after the baseline
migration (20260924_baseline), including:
- ac810655180b: student_competencies, interview_conversations, interview_messages,
  interview_question_analysis, competency_evidence, question_id on interview_turns
- f4e2a1b8c3d5: unique constraint on student_competencies(user_id, skill)
- f1ded62ef3b4: transcript finalization fields on interview_sessions
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'post_baseline_consolidated'
down_revision: Union[str, None] = '20260924_baseline'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============================================
    # STUDENT COMPETENCIES
    # ============================================
    op.create_table(
        'student_competencies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('skill', sa.String(length=100), nullable=False),
        sa.Column('score', sa.Float(), server_default=sa.text('0.0'), nullable=False),
        sa.Column('confidence', sa.Float(), server_default=sa.text('0.5'), nullable=False),
        sa.Column('last_verified_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('freshness', sa.String(length=20), server_default=sa.text("'high'"), nullable=False),
        sa.Column('evidence_source', sa.String(length=50), nullable=True),
        sa.Column('evidence_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_student_competencies_id'), 'student_competencies', ['id'], unique=False)
    op.create_index(op.f('ix_student_competencies_skill'), 'student_competencies', ['skill'], unique=False)
    op.create_index(op.f('ix_student_competencies_user_id'), 'student_competencies', ['user_id'], unique=False)

    # ============================================
    # INTERVIEW CONVERSATIONS
    # ============================================
    op.create_table(
        'interview_conversations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('interview_id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('total_messages', sa.Integer(), nullable=False),
        sa.Column('ai_message_count', sa.Integer(), nullable=False),
        sa.Column('candidate_message_count', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['interview_id'], ['interview_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['session_id'], ['assessment_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_interview_conversations_id'), 'interview_conversations', ['id'], unique=False)
    op.create_index(op.f('ix_interview_conversations_interview_id'), 'interview_conversations', ['interview_id'], unique=True)
    op.create_index(op.f('ix_interview_conversations_session_id'), 'interview_conversations', ['session_id'], unique=False)

    # ============================================
    # INTERVIEW MESSAGES
    # ============================================
    op.create_table(
        'interview_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=False),
        sa.Column('sequence_number', sa.Integer(), nullable=False),
        sa.Column('speaker', sa.String(length=20), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('message_type', sa.String(length=20), nullable=False),
        sa.Column('turn_id', sa.Integer(), nullable=True),
        sa.Column('parent_message_id', sa.Integer(), nullable=True),
        sa.Column('retell_utterance_id', sa.String(length=100), nullable=True),
        sa.Column('is_final', sa.Boolean(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['interview_conversations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_message_id'], ['interview_messages.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['turn_id'], ['interview_turns.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_interview_messages_conversation_id'), 'interview_messages', ['conversation_id'], unique=False)
    op.create_index(op.f('ix_interview_messages_id'), 'interview_messages', ['id'], unique=False)
    op.create_index(op.f('ix_interview_messages_turn_id'), 'interview_messages', ['turn_id'], unique=False)

    # ============================================
    # INTERVIEW QUESTION ANALYSIS
    # ============================================
    op.create_table(
        'interview_question_analysis',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('interview_id', sa.Integer(), nullable=False),
        sa.Column('turn_id', sa.Integer(), nullable=False),
        sa.Column('question_id', sa.String(length=50), nullable=True),
        sa.Column('question_number', sa.Integer(), nullable=False),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('question_type', sa.String(length=20), nullable=False),
        sa.Column('candidate_answer', sa.Text(), nullable=True),
        sa.Column('expected_concepts', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'"), nullable=False),
        sa.Column('covered_concepts', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'"), nullable=False),
        sa.Column('missing_concepts', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'"), nullable=False),
        sa.Column('incorrect_concepts', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'"), nullable=False),
        sa.Column('partial_concepts', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'"), nullable=False),
        sa.Column('evidence', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'"), nullable=False),
        sa.Column('strengths', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'"), nullable=False),
        sa.Column('gaps', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'"), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('max_score', sa.Float(), server_default=sa.text('10.0'), nullable=False),
        sa.Column('depth_level', sa.String(length=20), server_default=sa.text("'Basic'"), nullable=False),
        sa.Column('confidence', sa.Float(), server_default=sa.text('0.8'), nullable=False),
        sa.Column('interview_type', sa.String(length=20), nullable=True),
        sa.Column('analyzed_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['interview_id'], ['interview_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['turn_id'], ['interview_turns.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_interview_question_analysis_id'), 'interview_question_analysis', ['id'], unique=False)
    op.create_index(op.f('ix_interview_question_analysis_interview_id'), 'interview_question_analysis', ['interview_id'], unique=False)
    op.create_index(op.f('ix_interview_question_analysis_turn_id'), 'interview_question_analysis', ['turn_id'], unique=False)

    # ============================================
    # COMPETENCY EVIDENCE
    # ============================================
    op.create_table(
        'competency_evidence',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('skill', sa.String(length=100), nullable=False),
        sa.Column('previous_score', sa.Float(), nullable=False),
        sa.Column('new_score', sa.Float(), nullable=False),
        sa.Column('score_delta', sa.Float(), nullable=False),
        sa.Column('previous_confidence', sa.Float(), nullable=False),
        sa.Column('new_confidence', sa.Float(), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('question_analysis_id', sa.Integer(), nullable=True),
        sa.Column('demonstrated_concepts', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'"), nullable=False),
        sa.Column('missing_concepts', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'"), nullable=False),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['question_analysis_id'], ['interview_question_analysis.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_competency_evidence_id'), 'competency_evidence', ['id'], unique=False)
    op.create_index(op.f('ix_competency_evidence_skill'), 'competency_evidence', ['skill'], unique=False)
    op.create_index(op.f('ix_competency_evidence_user_id'), 'competency_evidence', ['user_id'], unique=False)

    # ============================================
    # QUESTION_ID ON INTERVIEW_TURNS
    # ============================================
    op.add_column('interview_turns', sa.Column('question_id', sa.String(length=50), nullable=True))
    op.create_index(op.f('ix_interview_turns_question_id'), 'interview_turns', ['question_id'], unique=False)

    # ============================================
    # DYNAMIC INTERVIEWERS
    # ============================================
    op.create_table(
        'dynamic_interviewers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('slug', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('tagline', sa.String(length=500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('personality', sa.Text(), nullable=False),
        sa.Column('speaking_style', sa.Text(), nullable=False),
        sa.Column('greeting', sa.Text(), nullable=False),
        sa.Column('avatar_initials', sa.String(length=10), nullable=False),
        sa.Column('accent', sa.String(length=20), nullable=False),
        sa.Column('avatar_url', sa.String(length=500), nullable=True),
        sa.Column('voice_id', sa.String(length=100), nullable=False),
        sa.Column('voice_model', sa.String(length=100), nullable=True),
        sa.Column('voice_provider', sa.String(length=50), nullable=False, server_default='retell'),
        sa.Column('language_code', sa.String(length=10), nullable=False, server_default='en-US'),
        sa.Column('pace', sa.Float(), nullable=False, server_default='0.95'),
        sa.Column('retell_llm_id', sa.String(length=100), nullable=True),
        sa.Column('retell_agent_id', sa.String(length=100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=False), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=False), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug'),
    )
    op.create_index('ix_dynamic_interviewers_id', 'dynamic_interviewers', ['id'], unique=False)
    op.create_index('ix_dynamic_interviewers_slug', 'dynamic_interviewers', ['slug'], unique=True)
    op.create_index('ix_dynamic_interviewers_retell_agent_id', 'dynamic_interviewers', ['retell_agent_id'], unique=False)

    # ============================================
    # MISSING COLUMNS ON INTERVIEW_SESSIONS (from incremental migrations)
    # ============================================
    # round_id (from link_interviews_to_assessment_rounds)
    op.add_column(
        'interview_sessions',
        sa.Column(
            'round_id',
            sa.Integer(),
            sa.ForeignKey('assessment_rounds.id', ondelete='CASCADE'),
            nullable=True,
        ),
    )
    op.create_index('ix_interview_sessions_round_id', 'interview_sessions', ['round_id'])

    # interviewer_id (from add_interviewer_id_to_interview_sessions)
    op.add_column(
        'interview_sessions',
        sa.Column('interviewer_id', sa.String(length=50), nullable=True)
    )

    # Retell integration fields
    op.add_column(
        'interview_sessions',
        sa.Column('retell_call_id', sa.String(length=100), nullable=True)
    )
    op.add_column(
        'interview_sessions',
        sa.Column('retell_agent_id', sa.String(length=100), nullable=True)
    )
    op.create_index('ix_interview_sessions_retell_call_id', 'interview_sessions', ['retell_call_id'])

    # Personalization fields (from add_personalization_001)
    op.add_column(
        'interview_sessions',
        sa.Column('extraction_confidence', sa.String(length=10), nullable=True)
    )
    op.add_column(
        'interview_sessions',
        sa.Column('retrieval_success_rate', sa.Float(), nullable=True)
    )
    op.add_column(
        'interview_sessions',
        sa.Column('question_personalization_rate', sa.Float(), nullable=True)
    )
    op.add_column(
        'interview_sessions',
        sa.Column('personalization_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )
    op.add_column(
        'interview_sessions',
        sa.Column('follow_up_quality_score', sa.Float(), nullable=True)
    )
    op.add_column(
        'interview_sessions',
        sa.Column('personalization_warnings', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )

    # Fix rl_state type: JSON -> JSONB (from rebuild_interview_pipeline)
    op.execute(
        "ALTER TABLE interview_sessions "
        "ALTER COLUMN rl_state TYPE JSONB USING rl_state::JSONB"
    )
    # Fix rl_state default to JSONB
    op.execute(
        "ALTER TABLE interview_sessions "
        "ALTER COLUMN rl_state SET DEFAULT '{}'::JSONB"
    )

    # ============================================
    # MISSING COLUMNS ON INTERVIEW_TURNS (from incremental migrations)
    # ============================================
    # Personalization fields (from add_personalization_001) - NOT in baseline
    op.add_column(
        'interview_turns',
        sa.Column('personalization_source', sa.String(length=200), nullable=True)
    )
    op.add_column(
        'interview_turns',
        sa.Column('question_grounding_confidence', sa.Float(), nullable=True)
    )
    op.add_column(
        'interview_turns',
        sa.Column('answer_classification', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )
    op.add_column(
        'interview_turns',
        sa.Column('followup_grounding_score', sa.Float(), nullable=True)
    )
    op.add_column(
        'interview_turns',
        sa.Column('followup_targeted_aspect', sa.String(length=200), nullable=True)
    )

    # ============================================
    # UNIQUE CONSTRAINT ON STUDENT_COMPETENCIES
    # ============================================
    # Remove any duplicates first (keep latest by id)
    op.execute("""
        DELETE FROM student_competencies
        WHERE id NOT IN (
            SELECT MAX(id) FROM student_competencies
            GROUP BY user_id, skill
        )
    """)

    op.create_unique_constraint(
        'uq_student_competency_user_skill',
        'student_competencies',
        ['user_id', 'skill']
    )

    # ============================================
    # TRANSCRIPT FINALIZATION FIELDS
    # ============================================
    op.add_column(
        'interview_sessions',
        sa.Column(
            'transcript_status',
            sa.String(length=20),
            server_default='pending',
            nullable=False,
        ),
    )
    op.add_column(
        'interview_sessions',
        sa.Column(
            'transcript_finalized_at',
            sa.DateTime(timezone=False),
            nullable=True,
        ),
    )
    op.add_column(
        'interview_sessions',
        sa.Column(
            'transcript_finalization_error',
            sa.Text(),
            nullable=True,
        ),
    )
    op.add_column(
        'interview_sessions',
        sa.Column(
            'transcript_source',
            sa.String(length=20),
            nullable=True,
        ),
    )
    # Create index for filtering by transcript status
    op.create_index(
        op.f('ix_interview_sessions_transcript_status'),
        'interview_sessions',
        ['transcript_status'],
        unique=False,
    )


def downgrade() -> None:
    # Transcript columns
    op.drop_index(
        op.f('ix_interview_sessions_transcript_status'),
        table_name='interview_sessions',
    )
    op.drop_column('interview_sessions', 'transcript_source')
    op.drop_column('interview_sessions', 'transcript_finalization_error')
    op.drop_column('interview_sessions', 'transcript_finalized_at')
    op.drop_column('interview_sessions', 'transcript_status')

    # Interview turns personalization columns
    op.drop_column('interview_turns', 'followup_targeted_aspect')
    op.drop_column('interview_turns', 'followup_grounding_score')
    op.drop_column('interview_turns', 'answer_classification')
    op.drop_column('interview_turns', 'question_grounding_confidence')
    op.drop_column('interview_turns', 'personalization_source')

    # Interview turns structural columns
    op.drop_column('interview_turns', 'parent_turn_id')
    op.drop_column('interview_turns', 'intent')
    op.drop_column('interview_turns', 'final_score')

    # Interview sessions columns (reverse order of addition)
    op.drop_index('ix_interview_sessions_retell_call_id', table_name='interview_sessions')
    op.drop_column('interview_sessions', 'retell_agent_id')
    op.drop_column('interview_sessions', 'retell_call_id')
    op.drop_column('interview_sessions', 'interviewer_id')
    op.drop_index('ix_interview_sessions_round_id', table_name='interview_sessions')
    op.drop_column('interview_sessions', 'round_id')
    op.drop_column('interview_sessions', 'personalization_warnings')
    op.drop_column('interview_sessions', 'follow_up_quality_score')
    op.drop_column('interview_sessions', 'personalization_metadata')
    op.drop_column('interview_sessions', 'question_personalization_rate')
    op.drop_column('interview_sessions', 'retrieval_success_rate')
    op.drop_column('interview_sessions', 'extraction_confidence')

    # Note: rl_state JSONB -> JSON conversion not easily reversible, skip

    # Dynamic interviewers
    op.drop_index('ix_dynamic_interviewers_retell_agent_id', table_name='dynamic_interviewers')
    op.drop_index('ix_dynamic_interviewers_slug', table_name='dynamic_interviewers')
    op.drop_index('ix_dynamic_interviewers_id', table_name='dynamic_interviewers')
    op.drop_table('dynamic_interviewers')

    # Unique constraint
    op.drop_constraint(
        'uq_student_competency_user_skill',
        'student_competencies',
        type_='unique'
    )

    # Question_id on interview_turns
    op.drop_index(op.f('ix_interview_turns_question_id'), table_name='interview_turns')
    op.drop_column('interview_turns', 'question_id')

    # Competency evidence
    op.drop_index(op.f('ix_competency_evidence_user_id'), table_name='competency_evidence')
    op.drop_index(op.f('ix_competency_evidence_skill'), table_name='competency_evidence')
    op.drop_index(op.f('ix_competency_evidence_id'), table_name='competency_evidence')
    op.drop_table('competency_evidence')

    # Interview question analysis
    op.drop_index(op.f('ix_interview_question_analysis_turn_id'), table_name='interview_question_analysis')
    op.drop_index(op.f('ix_interview_question_analysis_interview_id'), table_name='interview_question_analysis')
    op.drop_index(op.f('ix_interview_question_analysis_id'), table_name='interview_question_analysis')
    op.drop_table('interview_question_analysis')

    # Interview messages
    op.drop_index(op.f('ix_interview_messages_turn_id'), table_name='interview_messages')
    op.drop_index(op.f('ix_interview_messages_id'), table_name='interview_messages')
    op.drop_index(op.f('ix_interview_messages_conversation_id'), table_name='interview_messages')
    op.drop_table('interview_messages')

    # Interview conversations
    op.drop_index(op.f('ix_interview_conversations_session_id'), table_name='interview_conversations')
    op.drop_index(op.f('ix_interview_conversations_interview_id'), table_name='interview_conversations')
    op.drop_index(op.f('ix_interview_conversations_id'), table_name='interview_conversations')
    op.drop_table('interview_conversations')

    # Student competencies
    op.drop_index(op.f('ix_student_competencies_user_id'), table_name='student_competencies')
    op.drop_index(op.f('ix_student_competencies_skill'), table_name='student_competencies')
    op.drop_index(op.f('ix_student_competencies_id'), table_name='student_competencies')
    op.drop_table('student_competencies')