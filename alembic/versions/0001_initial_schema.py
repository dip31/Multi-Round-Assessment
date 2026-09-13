"""Initial comprehensive schema for AI Placement Platform

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-08-20 00:00:00.000000

Consolidates all tables from:
- app/models/*.py (SQLAlchemy ORM models)
- database/schema.sql (PostgreSQL DDL)

Tables included:
users, refresh_tokens, user_resumes, assessment_sessions, assessment_rounds,
aptitude_topics, aptitude_questions, admin_question_feedback, aptitude_attempts,
rl_sessions, coding_problems, coding_test_cases, session_problems,
coding_submissions, proctoring_events, advanced_proctoring_events,
interview_sessions, approved_question_pools, interview_turns,
proctoring_violations, resume_processing_jobs, rl_q_table, rl_attempt_log
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============================================
    # USERS
    # ============================================
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=150), nullable=False),
        sa.Column('password_hash', sa.Text(), nullable=False),
        sa.Column('role', sa.String(length=20), server_default=sa.text("'student'"), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('is_verified', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
        sa.CheckConstraint("role IN ('student','admin')", name='ck_users_role'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_users_email', 'users', ['email'], unique=True)

    # ============================================
    # REFRESH TOKENS (from schema.sql)
    # ============================================
    op.create_table(
        'refresh_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.Text(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('is_revoked', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_refresh_token_hash', 'refresh_tokens', ['token_hash'], unique=False)

    # ============================================
    # USER RESUMES (from schema.sql)
    # ============================================
    op.create_table(
        'user_resumes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('resume_text', sa.Text(), nullable=False),
        sa.Column('parsed_skills', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('parsed_projects', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # ============================================
    # ASSESSMENT SESSIONS
    # ============================================
    op.create_table(
        'assessment_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), server_default=sa.text("'not_started'"), nullable=False),
        sa.Column('started_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('total_score', sa.Float(), server_default=sa.text('0'), nullable=False),
        sa.CheckConstraint(
            "status IN ('not_started','in_progress','completed','terminated','expired')",
            name='ck_assessment_sessions_status'
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_assessment_sessions_user', 'assessment_sessions', ['user_id'], unique=False)
    op.execute(
        "CREATE UNIQUE INDEX one_active_session_per_user "
        "ON assessment_sessions(user_id) WHERE status='in_progress'"
    )

    # ============================================
    # ASSESSMENT ROUNDS
    # ============================================
    op.create_table(
        'assessment_rounds',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('round_type', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
        sa.Column('score', sa.Float(), server_default=sa.text('0'), nullable=False),
        sa.Column('max_questions', sa.Integer(), server_default=sa.text('20'), nullable=False),
        sa.Column('started_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "round_type IN ('aptitude','coding','interview')",
            name='ck_assessment_rounds_type'
        ),
        sa.CheckConstraint(
            "status IN ('pending','active','completed','terminated','expired')",
            name='ck_assessment_rounds_status'
        ),
        sa.ForeignKeyConstraint(['session_id'], ['assessment_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_round_session', 'assessment_rounds', ['session_id'], unique=False)

    # ============================================
    # APTITUDE TOPICS
    # ============================================
    op.create_table(
        'aptitude_topics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    # ============================================
    # APTITUDE QUESTIONS
    # ============================================
    op.create_table(
        'aptitude_questions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('option_a', sa.Text(), nullable=False),
        sa.Column('option_b', sa.Text(), nullable=False),
        sa.Column('option_c', sa.Text(), nullable=False),
        sa.Column('option_d', sa.Text(), nullable=False),
        sa.Column('correct_option', sa.String(length=1), nullable=False),
        sa.Column('difficulty', sa.String(length=10), nullable=False),
        sa.Column('topic_id', sa.Integer(), nullable=True),
        sa.Column('version', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
        sa.CheckConstraint("correct_option IN ('A','B','C','D')", name='ck_aptitude_correct_option'),
        sa.CheckConstraint("difficulty IN ('easy','medium','hard')", name='ck_aptitude_difficulty'),
        sa.ForeignKeyConstraint(['topic_id'], ['aptitude_topics.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_aptitude_difficulty', 'aptitude_questions', ['difficulty'], unique=False)
    op.create_index('idx_aptitude_topic', 'aptitude_questions', ['topic_id'], unique=False)

    # ============================================
    # ADMIN QUESTION FEEDBACK
    # ============================================
    op.create_table(
        'admin_question_feedback',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('question_id', sa.Integer(), nullable=False),
        sa.Column('admin_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=20), nullable=False),
        sa.Column('suggestion', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.CheckConstraint("action IN ('approve','reject','review')", name='ck_admin_qf_action'),
        sa.ForeignKeyConstraint(['question_id'], ['aptitude_questions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['admin_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_admin_qf_question_id', 'admin_question_feedback', ['question_id'], unique=False)
    op.create_index('idx_admin_qf_admin_id', 'admin_question_feedback', ['admin_id'], unique=False)

    # ============================================
    # APTITUDE ATTEMPTS
    # ============================================
    op.create_table(
        'aptitude_attempts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('round_id', sa.Integer(), nullable=False),
        sa.Column('question_id', sa.Integer(), nullable=False),
        sa.Column('attempt_number', sa.Integer(), nullable=False),
        sa.Column('selected_option', sa.String(length=1), nullable=True),
        sa.Column('is_correct', sa.Boolean(), nullable=True),
        sa.Column('response_time', sa.Float(), nullable=True),
        sa.Column('difficulty', sa.String(length=10), nullable=True),
        sa.Column('reward', sa.Float(), nullable=True),
        sa.Column('attempted_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
        sa.ForeignKeyConstraint(['round_id'], ['assessment_rounds.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['question_id'], ['aptitude_questions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('round_id', 'attempt_number', name='uq_aptitude_attempts_round_attempt')
    )
    op.create_index('idx_aptitude_attempts_round', 'aptitude_attempts', ['round_id'], unique=False)

    # ============================================
    # RL SESSIONS (adaptive difficulty tracking)
    # ============================================
    op.create_table(
        'rl_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('round_id', sa.Integer(), nullable=False),
        sa.Column('step_number', sa.Integer(), nullable=False),
        sa.Column('prev_difficulty', sa.String(length=10), nullable=True),
        sa.Column('action_taken', sa.String(length=10), nullable=False),
        sa.Column('reward_received', sa.Float(), nullable=True),
        sa.Column('accuracy_so_far', sa.Float(), nullable=True),
        sa.Column('avg_response_time', sa.Float(), nullable=True),
        sa.Column('q_values', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
        sa.CheckConstraint("prev_difficulty IN ('easy','medium','hard')", name='ck_rl_prev_difficulty'),
        sa.CheckConstraint("action_taken IN ('easy','medium','hard')", name='ck_rl_action_taken'),
        sa.ForeignKeyConstraint(['round_id'], ['assessment_rounds.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('round_id', 'step_number', name='uq_rl_sessions_round_step')
    )
    op.create_index('idx_rl_sessions_round', 'rl_sessions', ['round_id'], unique=False)

    # ============================================
    # CODING PROBLEMS
    # ============================================
    op.create_table(
        'coding_problems',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('difficulty', sa.String(length=10), nullable=True),
        sa.Column('tags', sa.ARRAY(sa.Text()), nullable=True),
        sa.Column('input_format', sa.Text(), nullable=True),
        sa.Column('output_format', sa.Text(), nullable=True),
        sa.Column('constraints', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
        sa.CheckConstraint("difficulty IN ('easy','medium','hard')", name='ck_coding_difficulty'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

    # ============================================
    # CODING TEST CASES
    # ============================================
    op.create_table(
        'coding_test_cases',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('problem_id', sa.Integer(), nullable=False),
        sa.Column('input_data', sa.Text(), nullable=False),
        sa.Column('expected_output', sa.Text(), nullable=False),
        sa.Column('is_hidden', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('case_order', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('explanation', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['problem_id'], ['coding_problems.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_coding_test_cases_problem', 'coding_test_cases', ['problem_id'], unique=False)

    # ============================================
    # SESSION PROBLEMS (assigned coding problems per round)
    # ============================================
    op.create_table(
        'session_problems',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('round_id', sa.Integer(), nullable=False),
        sa.Column('problem_id', sa.Integer(), nullable=False),
        sa.Column('problem_order', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('marked_for_review', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('assigned_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['round_id'], ['assessment_rounds.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['problem_id'], ['coding_problems.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_session_problems_round', 'session_problems', ['round_id'], unique=False)

    # ============================================
    # CODING SUBMISSIONS
    # ============================================
    op.create_table(
        'coding_submissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('round_id', sa.Integer(), nullable=False),
        sa.Column('problem_id', sa.Integer(), nullable=False),
        sa.Column('code', sa.Text(), nullable=False),
        sa.Column('language', sa.String(length=50), nullable=True),
        sa.Column('judge0_token', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=True),
        sa.Column('score', sa.Float(), nullable=True),
        sa.Column('execution_time', sa.Float(), nullable=True),
        sa.Column('memory_used', sa.Integer(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
        sa.CheckConstraint(
            "status IN ('running','accepted','wrong_answer','runtime_error','time_limit_exceeded','compilation_error')",
            name='ck_coding_submission_status'
        ),
        sa.ForeignKeyConstraint(['round_id'], ['assessment_rounds.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['problem_id'], ['coding_problems.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_coding_submission_round', 'coding_submissions', ['round_id'], unique=False)
    op.create_index('idx_judge0_token', 'coding_submissions', ['judge0_token'], unique=False)

    # ============================================
    # PROCTORING EVENTS (basic)
    # ============================================
    op.create_table(
        'proctoring_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('event_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['assessment_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_proctoring_session', 'proctoring_events', ['session_id'], unique=False)
    op.create_index('idx_proctoring_type', 'proctoring_events', ['event_type'], unique=False)

    # ============================================
    # ADVANCED PROCTORING EVENTS
    # ============================================
    op.create_table(
        'advanced_proctoring_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('event_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['assessment_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_adv_proctoring_session', 'advanced_proctoring_events', ['session_id'], unique=False)
    op.create_index('idx_adv_proctoring_type', 'advanced_proctoring_events', ['event_type'], unique=False)
    op.create_index('idx_adv_proctoring_created', 'advanced_proctoring_events', ['created_at'], unique=False)

    # ============================================
    # INTERVIEW SESSIONS (enhanced from schema.sql)
    # ============================================
    op.create_table(
        'interview_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('phase', sa.String(length=20), server_default='HR', nullable=False),
        sa.Column('current_turn', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('total_turns', sa.Integer(), server_default=sa.text('10'), nullable=False),
        sa.Column('rl_state', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'"), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='ACTIVE', nullable=False),
        sa.Column('completion_reason', sa.String(length=30), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
        sa.CheckConstraint(
            "phase IN ('HR','TECHNICAL','BEHAVIORAL')",
            name='ck_interview_phase'
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE','COMPLETED','TERMINATED')",
            name='ck_interview_status'
        ),
        sa.CheckConstraint(
            "completion_reason IN ('ALL_QUESTIONS_COMPLETED','USER_SUBMITTED','TIME_EXPIRED')",
            name='ck_interview_completion_reason'
        ),
        sa.ForeignKeyConstraint(['session_id'], ['assessment_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_interview_session', 'interview_sessions', ['session_id'], unique=False)

    # ============================================
    # APPROVED QUESTION POOLS
    # ============================================
    op.create_table(
        'approved_question_pools',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('extracted_skills', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'"), nullable=False),
        sa.Column('extracted_projects', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'"), nullable=False),
        sa.Column('question_pool', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('admin_approved', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('approved_by', sa.Integer(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('detected_role', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['assessment_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_approved_pool_session', 'approved_question_pools', ['session_id'], unique=False)
    op.create_index('idx_approved_pool_approved', 'approved_question_pools', ['admin_approved'], unique=False)

    # ============================================
    # INTERVIEW TURNS
    # ============================================
    op.create_table(
        'interview_turns',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('interview_id', sa.Integer(), nullable=False),
        sa.Column('turn_number', sa.Integer(), nullable=False),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('question_difficulty', sa.String(length=10), nullable=True),
        sa.Column('candidate_response', sa.Text(), nullable=True),
        sa.Column('response_time_sec', sa.Float(), nullable=True),
        sa.Column('content_score', sa.Float(), nullable=True),
        sa.Column('final_score', sa.Float(), nullable=True),
        sa.Column('intent', sa.String(length=10), nullable=True),
        sa.Column('behavioral_snapshot', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'"), nullable=False),
        sa.Column('rl_reward', sa.Float(), nullable=True),
        sa.Column('is_followup', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('followup_number', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('parent_turn_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
        sa.ForeignKeyConstraint(['interview_id'], ['interview_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_turn_id'], ['interview_turns.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_interview_turns_interview', 'interview_turns', ['interview_id'], unique=False)
    op.create_index('idx_interview_turns_turn', 'interview_turns', ['interview_id', 'turn_number'], unique=False)

    # ============================================
    # PROCTORING VIOLATIONS (interview-specific)
    # ============================================
    op.create_table(
        'proctoring_violations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('face_count', sa.Integer(), nullable=True),
        sa.Column('violation_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['interview_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_proctoring_violations_session', 'proctoring_violations', ['session_id'], unique=False)

    # ============================================
    # RESUME PROCESSING JOBS (async upload flow)
    # ============================================
    op.create_table(
        'resume_processing_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('storage_key', sa.Text(), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=20), server_default=sa.text("'PENDING'"), nullable=False),
        sa.Column('progress_step', sa.String(length=50), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('job_metadata', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'"), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['session_id'], ['assessment_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_resume_jobs_user', 'resume_processing_jobs', ['user_id'], unique=False)
    op.create_index('idx_resume_jobs_session', 'resume_processing_jobs', ['session_id'], unique=False)
    op.create_index('idx_resume_jobs_status', 'resume_processing_jobs', ['status'], unique=False)
    op.create_index('idx_resume_jobs_created', 'resume_processing_jobs', ['created_at'], unique=False)

    # ============================================
    # RL Q-TABLE (persisted across sessions)
    # ============================================
    op.create_table(
        'rl_q_table',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('state', sa.Text(), nullable=False),
        sa.Column('action', sa.Text(), nullable=False),
        sa.Column('q_value', sa.Float(), server_default=sa.text('0.1'), nullable=False),
        sa.Column('visit_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'state', 'action')
    )
    op.create_index('idx_rl_qtable_user', 'rl_q_table', ['user_id'], unique=False)

    # ============================================
    # RL ATTEMPT LOG (audit trail)
    # ============================================
    op.create_table(
        'rl_attempt_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('session_id', sa.Integer(), nullable=True),
        sa.Column('question_id', sa.Integer(), nullable=True),
        sa.Column('difficulty', sa.Text(), nullable=True),
        sa.Column('state_before', sa.Text(), nullable=True),
        sa.Column('action_taken', sa.Text(), nullable=True),
        sa.Column('reward', sa.Float(), nullable=True),
        sa.Column('state_after', sa.Text(), nullable=True),
        sa.Column('response_time', sa.Float(), nullable=True),
        sa.Column('is_correct', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_rl_log_user', 'rl_attempt_log', ['user_id'], unique=False)
    op.create_index('idx_rl_log_session', 'rl_attempt_log', ['session_id'], unique=False)

    # ============================================
    # MATERIALIZED VIEW: ROUND ANALYTICS
    # ============================================
    op.execute("""
        CREATE MATERIALIZED VIEW round_analytics AS
        SELECT
            r.id AS round_id,
            r.round_type,
            COUNT(aa.id) AS total_questions,
            SUM(CASE WHEN aa.is_correct THEN 1 ELSE 0 END) AS correct_answers,
            AVG(aa.response_time) AS avg_response_time,
            NULL::FLOAT AS coding_score
        FROM assessment_rounds r
        LEFT JOIN aptitude_attempts aa ON aa.round_id = r.id
        WHERE r.round_type = 'aptitude'
        GROUP BY r.id, r.round_type

        UNION ALL

        SELECT
            r.id,
            r.round_type,
            COUNT(cs.id),
            NULL,
            NULL,
            AVG(cs.score)
        FROM assessment_rounds r
        LEFT JOIN coding_submissions cs ON cs.round_id = r.id
        WHERE r.round_type = 'coding'
        GROUP BY r.id, r.round_type
    """)
    op.execute(
        "CREATE UNIQUE INDEX idx_round_analytics_round_id ON round_analytics(round_id)"
    )


def downgrade() -> None:
    # Drop materialized view first
    op.execute("DROP INDEX IF EXISTS idx_round_analytics_round_id")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS round_analytics")

    # Drop tables in reverse dependency order
    op.drop_index('idx_rl_log_session', table_name='rl_attempt_log')
    op.drop_index('idx_rl_log_user', table_name='rl_attempt_log')
    op.drop_table('rl_attempt_log')

    op.drop_index('idx_rl_qtable_user', table_name='rl_q_table')
    op.drop_table('rl_q_table')

    op.drop_index('idx_resume_jobs_created', table_name='resume_processing_jobs')
    op.drop_index('idx_resume_jobs_status', table_name='resume_processing_jobs')
    op.drop_index('idx_resume_jobs_session', table_name='resume_processing_jobs')
    op.drop_index('idx_resume_jobs_user', table_name='resume_processing_jobs')
    op.drop_table('resume_processing_jobs')

    op.drop_index('idx_proctoring_violations_session', table_name='proctoring_violations')
    op.drop_table('proctoring_violations')

    op.drop_index('idx_interview_turns_turn', table_name='interview_turns')
    op.drop_index('idx_interview_turns_interview', table_name='interview_turns')
    op.drop_table('interview_turns')

    op.drop_index('idx_approved_pool_approved', table_name='approved_question_pools')
    op.drop_index('idx_approved_pool_session', table_name='approved_question_pools')
    op.drop_table('approved_question_pools')

    op.drop_index('idx_interview_session', table_name='interview_sessions')
    op.drop_table('interview_sessions')

    op.drop_index('idx_adv_proctoring_created', table_name='advanced_proctoring_events')
    op.drop_index('idx_adv_proctoring_type', table_name='advanced_proctoring_events')
    op.drop_index('idx_adv_proctoring_session', table_name='advanced_proctoring_events')
    op.drop_table('advanced_proctoring_events')

    op.drop_index('idx_proctoring_type', table_name='proctoring_events')
    op.drop_index('idx_proctoring_session', table_name='proctoring_events')
    op.drop_table('proctoring_events')

    op.drop_index('idx_judge0_token', table_name='coding_submissions')
    op.drop_index('idx_coding_submission_round', table_name='coding_submissions')
    op.drop_table('coding_submissions')

    op.drop_index('idx_session_problems_round', table_name='session_problems')
    op.drop_table('session_problems')

    op.drop_index('idx_coding_test_cases_problem', table_name='coding_test_cases')
    op.drop_table('coding_test_cases')

    op.drop_table('coding_problems')

    op.drop_index('idx_rl_sessions_round', table_name='rl_sessions')
    op.drop_table('rl_sessions')

    op.drop_index('idx_aptitude_attempts_round', table_name='aptitude_attempts')
    op.drop_table('aptitude_attempts')

    op.drop_index('idx_admin_qf_admin_id', table_name='admin_question_feedback')
    op.drop_index('idx_admin_qf_question_id', table_name='admin_question_feedback')
    op.drop_table('admin_question_feedback')

    op.drop_index('idx_aptitude_topic', table_name='aptitude_questions')
    op.drop_index('idx_aptitude_difficulty', table_name='aptitude_questions')
    op.drop_table('aptitude_questions')

    op.drop_table('aptitude_topics')

    op.drop_index('idx_round_session', table_name='assessment_rounds')
    op.drop_table('assessment_rounds')

    op.execute("DROP INDEX IF EXISTS one_active_session_per_user")
    op.drop_index('idx_assessment_sessions_user', table_name='assessment_sessions')
    op.drop_table('assessment_sessions')

    op.drop_table('user_resumes')

    op.drop_index('idx_refresh_token_hash', table_name='refresh_tokens')
    op.drop_table('refresh_tokens')

    op.drop_index('idx_users_email', table_name='users')
    op.drop_table('users')