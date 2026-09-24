"""Baseline complete schema - creates all tables from scratch

Revision ID: 20260924_baseline
Revises: 
Create Date: 2026-09-24

This is a consolidated baseline migration that creates the complete database schema
in a single step. New team members can run `alembic upgrade head` to get the full schema.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20260924_baseline'
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
        sa.Column('role', sa.String(length=20), nullable=False, server_default='student'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.CheckConstraint("role IN ('student', 'faculty', 'tpo', 'admin')", name='users_role_check'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email', name='users_email_key')
    )
    op.create_index('idx_users_email', 'users', ['email'], unique=False)

    # ============================================
    # USER PROFILES
    # ============================================
    op.create_table(
        'student_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('roll_number', sa.String(length=50), nullable=True),
        sa.Column('department', sa.String(length=100), nullable=False),
        sa.Column('cgpa', sa.Float(), nullable=False),
        sa.Column('graduation_year', sa.Integer(), nullable=False),
        sa.Column('backlogs_count', sa.Integer(), nullable=False),
        sa.Column('institution', sa.String(length=200), nullable=False),
        sa.Column('target_role', sa.String(length=100), nullable=True),
        sa.Column('skills_json', sa.JSON(), nullable=False),
        sa.Column('phone_number', sa.String(length=20), nullable=True),
        sa.Column('mobile_no', sa.String(length=50), nullable=True),
        sa.Column('full_name', sa.String(length=150), nullable=True),
        sa.Column('college_email_id', sa.String(length=150), nullable=True),
        sa.Column('gender', sa.String(length=50), nullable=True),
        sa.Column('date_of_birth', sa.String(length=50), nullable=True),
        sa.Column('nationality', sa.String(length=100), nullable=True),
        sa.Column('tenth_marks', sa.Float(), nullable=True),
        sa.Column('twelfth_marks', sa.Float(), nullable=True),
        sa.Column('bio', sa.Text(), nullable=True),
        sa.Column('portfolio_data', sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', name='student_profiles_user_id_key')
    )

    op.create_table(
        'faculty_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('department', sa.String(length=100), nullable=False),
        sa.Column('designation', sa.String(length=100), nullable=False),
        sa.Column('institution', sa.String(length=200), nullable=False),
        sa.Column('employee_id', sa.String(length=50), nullable=True),
        sa.Column('bio', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', name='faculty_profiles_user_id_key')
    )

    op.create_table(
        'tpo_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('institution', sa.String(length=200), nullable=False),
        sa.Column('designation', sa.String(length=100), nullable=False),
        sa.Column('contact_email', sa.String(length=150), nullable=True),
        sa.Column('contact_phone', sa.String(length=20), nullable=True),
        sa.Column('bio', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', name='tpo_profiles_user_id_key')
    )

    # ============================================
    # REFRESH TOKENS
    # ============================================
    op.create_table(
        'refresh_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.Text(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('is_revoked', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_refresh_token_hash', 'refresh_tokens', ['token_hash'], unique=False)

    # ============================================
    # USER RESUMES
    # ============================================
    op.create_table(
        'user_resumes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('cv_name', sa.String(length=200), nullable=False),
        sa.Column('cv_type', sa.String(length=100), nullable=False),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('resume_text', sa.Text(), nullable=True),
        sa.Column('parsed_skills', sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column('parsed_projects', sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column('uploaded_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_user_resumes_user_id', 'user_resumes', ['user_id'], unique=False)

    # ============================================
    # ASSESSMENT POLICIES & CONTEXTS
    # ============================================
    op.create_table(
        'assessment_policies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('session_duration_minutes', sa.Integer(), nullable=False),
        sa.Column('round_duration_minutes', sa.Integer(), nullable=False),
        sa.Column('max_attempts', sa.Integer(), nullable=True),
        sa.Column('resume_allowed', sa.Boolean(), nullable=False),
        sa.Column('exit_allowed', sa.Boolean(), nullable=False),
        sa.Column('progression_mode', sa.String(length=20), nullable=False),
        sa.Column('progression_config', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'assessment_contexts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('mode', sa.String(length=50), nullable=False),
        sa.Column('purpose', sa.String(length=100), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('student_id', sa.Integer(), nullable=True),
        sa.Column('company_name', sa.String(length=200), nullable=True),
        sa.Column('target_role', sa.String(length=100), nullable=True),
        sa.Column('jd_text', sa.Text(), nullable=True),
        sa.Column('availability_start', sa.DateTime(), nullable=True),
        sa.Column('availability_end', sa.DateTime(), nullable=True),
        sa.Column('policy_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id']),
        sa.ForeignKeyConstraint(['policy_id'], ['assessment_policies.id']),
        sa.ForeignKeyConstraint(['student_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_assessment_contexts_student_id', 'assessment_contexts', ['student_id'], unique=False)
    op.create_index('idx_assessment_contexts_policy_id', 'assessment_contexts', ['policy_id'], unique=False)

    # ============================================
    # ASSESSMENT SESSIONS
    # ============================================
    op.create_table(
        'assessment_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('context_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default=sa.text("'not_started'")),
        sa.Column('started_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('total_score', sa.Float(), nullable=False, server_default=sa.text('0')),
        sa.CheckConstraint("status IN ('not_started','in_progress','completed','terminated','expired')", name='assessment_sessions_status_check'),
        sa.ForeignKeyConstraint(['context_id'], ['assessment_contexts.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('one_active_session_per_user', 'assessment_sessions', ['user_id'], unique=True, postgresql_where=sa.text("status='in_progress'"))
    op.create_index('idx_assessment_sessions_context_id', 'assessment_sessions', ['context_id'], unique=False)

    # ============================================
    # ASSESSMENT ROUNDS
    # ============================================
    op.create_table(
        'assessment_rounds',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('round_type', sa.String(length=20), nullable=False),
        sa.Column('practice_type', sa.String(length=20), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column('score', sa.Float(), nullable=False, server_default=sa.text('0')),
        sa.Column('max_questions', sa.Integer(), nullable=False, server_default=sa.text('20')),
        sa.Column('started_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint("round_type IN ('aptitude','coding','interview')", name='assessment_rounds_round_type_check'),
        sa.CheckConstraint("status IN ('pending','active','completed','terminated','expired')", name='assessment_rounds_status_check'),
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
        sa.UniqueConstraint('name', name='aptitude_topics_name_key')
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
        sa.Column('correct_option', sa.CHAR(length=1), nullable=False),
        sa.Column('difficulty', sa.String(length=10), nullable=False),
        sa.Column('topic_id', sa.Integer(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default=sa.text('1')),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.CheckConstraint("correct_option IN ('A','B','C','D')", name='aptitude_questions_correct_option_check'),
        sa.CheckConstraint("difficulty IN ('easy','medium','hard')", name='aptitude_questions_difficulty_check'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['topic_id'], ['aptitude_topics.id']),
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
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.CheckConstraint("action IN ('approve','reject','review')", name='admin_question_feedback_action_check'),
        sa.ForeignKeyConstraint(['admin_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['question_id'], ['aptitude_questions.id'], ondelete='CASCADE'),
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
        sa.Column('selected_option', sa.CHAR(length=1), nullable=True),
        sa.Column('is_correct', sa.Boolean(), nullable=True),
        sa.Column('response_time', sa.Float(), nullable=True),
        sa.Column('difficulty', sa.String(length=10), nullable=True),
        sa.Column('reward', sa.Float(), nullable=True),
        sa.Column('attempted_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['question_id'], ['aptitude_questions.id']),
        sa.ForeignKeyConstraint(['round_id'], ['assessment_rounds.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('round_id', 'attempt_number', name='aptitude_attempts_round_id_attempt_number_key')
    )
    op.create_index('idx_aptitude_attempts_round', 'aptitude_attempts', ['round_id'], unique=False)
    op.create_index('idx_aptitude_attempts_question', 'aptitude_attempts', ['question_id'], unique=False)

    # ============================================
    # RL SESSIONS
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
        sa.Column('q_values', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.CheckConstraint("prev_difficulty IN ('easy','medium','hard')", name='rl_sessions_prev_difficulty_check'),
        sa.CheckConstraint("action_taken IN ('easy','medium','hard')", name='rl_sessions_action_taken_check'),
        sa.ForeignKeyConstraint(['round_id'], ['assessment_rounds.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('round_id', 'step_number', name='rl_sessions_round_id_step_number_key')
    )
    op.create_index('idx_rl_sessions_round', 'rl_sessions', ['round_id'], unique=False)

    # ============================================
    # RL Q-TABLE
    # ============================================
    op.create_table(
        'rl_q_table',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('state', sa.Text(), nullable=False),
        sa.Column('action', sa.Text(), nullable=False),
        sa.Column('q_value', sa.Float(), nullable=False, server_default=sa.text('0.1')),
        sa.Column('visit_count', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'state', 'action', name='rl_q_table_pkey')
    )
    op.create_index('idx_rl_q_table_user', 'rl_q_table', ['user_id'], unique=False)

    # ============================================
    # RL ATTEMPT LOG
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
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['question_id'], ['aptitude_questions.id']),
        sa.ForeignKeyConstraint(['session_id'], ['assessment_sessions.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_rl_attempt_log_user', 'rl_attempt_log', ['user_id'], unique=False)
    op.create_index('idx_rl_attempt_log_session', 'rl_attempt_log', ['session_id'], unique=False)

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
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.CheckConstraint("difficulty IN ('easy','medium','hard')", name='coding_problems_difficulty_check'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_coding_problems_difficulty', 'coding_problems', ['difficulty'], unique=False)
    op.create_index('idx_coding_problems_created_by', 'coding_problems', ['created_by'], unique=False)

    # ============================================
    # CODING TEST CASES
    # ============================================
    op.create_table(
        'coding_test_cases',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('problem_id', sa.Integer(), nullable=False),
        sa.Column('input_data', sa.Text(), nullable=False),
        sa.Column('expected_output', sa.Text(), nullable=False),
        sa.Column('is_hidden', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('case_order', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('explanation', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['problem_id'], ['coding_problems.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_coding_test_cases_problem', 'coding_test_cases', ['problem_id'], unique=False)

    # ============================================
    # SESSION PROBLEMS
    # ============================================
    op.create_table(
        'session_problems',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('round_id', sa.Integer(), nullable=False),
        sa.Column('problem_id', sa.Integer(), nullable=False),
        sa.Column('problem_order', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('marked_for_review', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('assigned_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['problem_id'], ['coding_problems.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['round_id'], ['assessment_rounds.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_session_problems_round', 'session_problems', ['round_id'], unique=False)
    op.create_index('idx_session_problems_problem', 'session_problems', ['problem_id'], unique=False)

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
        sa.Column('submitted_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.CheckConstraint("status IN ('running','accepted','wrong_answer','runtime_error','time_limit_exceeded','compilation_error')", name='coding_submissions_status_check'),
        sa.ForeignKeyConstraint(['problem_id'], ['coding_problems.id']),
        sa.ForeignKeyConstraint(['round_id'], ['assessment_rounds.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_coding_submission_round', 'coding_submissions', ['round_id'], unique=False)
    op.create_index('idx_coding_submission_problem', 'coding_submissions', ['problem_id'], unique=False)
    op.create_index('idx_judge0_token', 'coding_submissions', ['judge0_token'], unique=False)

    # ============================================
    # APPROVED QUESTION POOLS
    # ============================================
    op.create_table(
        'approved_question_pools',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('extracted_skills', sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column('extracted_projects', sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column('question_pool', sa.JSON(), nullable=False),
        sa.Column('admin_approved', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('approved_by', sa.Integer(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('detected_role', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['session_id'], ['assessment_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_approved_question_pools_session_id', 'approved_question_pools', ['session_id'], unique=False)
    op.create_index('ix_approved_question_pools_admin_approved', 'approved_question_pools', ['admin_approved'], unique=False)

    # ============================================
    # PROCTORING EVENTS (Basic)
    # ============================================
    op.create_table(
        'proctoring_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('event_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['session_id'], ['assessment_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_proctoring_session', 'proctoring_events', ['session_id'], unique=False)
    op.create_index('idx_proctoring_event_type', 'proctoring_events', ['event_type'], unique=False)
    op.create_index('idx_proctoring_created_at', 'proctoring_events', ['created_at'], unique=False)

    # ============================================
    # ADVANCED PROCTORING EVENTS
    # ============================================
    op.create_table(
        'advanced_proctoring_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('severity', sa.String(length=10), nullable=False, server_default=sa.text("'INFO'")),
        sa.Column('round_type', sa.String(length=20), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('event_metadata', sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.CheckConstraint("severity IN ('INFO', 'WARNING', 'CRITICAL')", name='chk_severity'),
        sa.CheckConstraint("round_type IN ('APTITUDE', 'CODING', 'INTERVIEW')", name='advanced_proctoring_events_round_type_check'),
        sa.CheckConstraint('confidence >= 0.0 AND confidence <= 1.0', name='advanced_proctoring_events_confidence_check'),
        sa.ForeignKeyConstraint(['session_id'], ['assessment_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_adv_proctoring_session', 'advanced_proctoring_events', ['session_id'], unique=False)
    op.create_index('idx_adv_proctoring_event_type', 'advanced_proctoring_events', ['event_type'], unique=False)
    op.create_index('idx_adv_proctoring_severity', 'advanced_proctoring_events', ['severity'], unique=False)
    op.create_index('idx_adv_proctoring_round', 'advanced_proctoring_events', ['round_type'], unique=False)
    op.create_index('idx_adv_proctoring_created_at', 'advanced_proctoring_events', ['created_at'], unique=False)
    op.create_index('idx_adv_proctoring_metadata', 'advanced_proctoring_events', ['event_metadata'], unique=False, postgresql_using='gin')
    op.create_index('idx_adv_proctoring_dedup', 'advanced_proctoring_events', ['session_id', 'event_type', sa.text("date_trunc('second', created_at)")], unique=True)

    # ============================================
    # INTERVIEW SESSIONS
    # ============================================
    op.create_table(
        'interview_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('phase', sa.String(length=20), nullable=False, server_default=sa.text("'HR'")),
        sa.Column('current_turn', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('total_turns', sa.Integer(), nullable=False, server_default=sa.text('10')),
        sa.Column('rl_state', sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column('status', sa.String(length=20), nullable=False, server_default=sa.text("'ACTIVE'")),
        sa.Column('completion_reason', sa.String(length=30), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['session_id'], ['assessment_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_interview_sessions_session_id', 'interview_sessions', ['session_id'], unique=False)

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
        sa.Column('behavioral_snapshot', sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column('rl_reward', sa.Float(), nullable=True),
        sa.Column('is_followup', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('followup_number', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('parent_turn_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['interview_id'], ['interview_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_turn_id'], ['interview_turns.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_interview_turns_interview_id', 'interview_turns', ['interview_id'], unique=False)

    # ============================================
    # PROCTORING VIOLATIONS
    # ============================================
    op.create_table(
        'proctoring_violations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('face_count', sa.Integer(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['session_id'], ['interview_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_proctoring_violations_session_id', 'proctoring_violations', ['session_id'], unique=False)


def downgrade() -> None:
    # Drop in reverse order of creation (respecting foreign keys)
    op.drop_index('ix_proctoring_violations_session_id', table_name='proctoring_violations')
    op.drop_table('proctoring_violations')
    
    op.drop_index('ix_interview_turns_interview_id', table_name='interview_turns')
    op.drop_table('interview_turns')
    
    op.drop_index('ix_interview_sessions_session_id', table_name='interview_sessions')
    op.drop_table('interview_sessions')
    
    op.drop_index('idx_adv_proctoring_dedup', table_name='advanced_proctoring_events')
    op.drop_index('idx_adv_proctoring_metadata', table_name='advanced_proctoring_events')
    op.drop_index('idx_adv_proctoring_created_at', table_name='advanced_proctoring_events')
    op.drop_index('idx_adv_proctoring_round', table_name='advanced_proctoring_events')
    op.drop_index('idx_adv_proctoring_severity', table_name='advanced_proctoring_events')
    op.drop_index('idx_adv_proctoring_event_type', table_name='advanced_proctoring_events')
    op.drop_index('idx_adv_proctoring_session', table_name='advanced_proctoring_events')
    op.drop_table('advanced_proctoring_events')
    
    op.drop_index('idx_proctoring_created_at', table_name='proctoring_events')
    op.drop_index('idx_proctoring_event_type', table_name='proctoring_events')
    op.drop_index('idx_proctoring_session', table_name='proctoring_events')
    op.drop_table('proctoring_events')
    
    op.drop_index('ix_approved_question_pools_admin_approved', table_name='approved_question_pools')
    op.drop_index('ix_approved_question_pools_session_id', table_name='approved_question_pools')
    op.drop_table('approved_question_pools')
    
    op.drop_index('idx_judge0_token', table_name='coding_submissions')
    op.drop_index('idx_coding_submission_problem', table_name='coding_submissions')
    op.drop_index('idx_coding_submission_round', table_name='coding_submissions')
    op.drop_table('coding_submissions')
    
    op.drop_index('idx_session_problems_problem', table_name='session_problems')
    op.drop_index('idx_session_problems_round', table_name='session_problems')
    op.drop_table('session_problems')
    
    op.drop_index('idx_coding_test_cases_problem', table_name='coding_test_cases')
    op.drop_table('coding_test_cases')
    
    op.drop_index('idx_coding_problems_created_by', table_name='coding_problems')
    op.drop_index('idx_coding_problems_difficulty', table_name='coding_problems')
    op.drop_table('coding_problems')
    
    op.drop_index('idx_rl_attempt_log_session', table_name='rl_attempt_log')
    op.drop_index('idx_rl_attempt_log_user', table_name='rl_attempt_log')
    op.drop_table('rl_attempt_log')
    
    op.drop_index('idx_rl_q_table_user', table_name='rl_q_table')
    op.drop_table('rl_q_table')
    
    op.drop_index('idx_rl_sessions_round', table_name='rl_sessions')
    op.drop_table('rl_sessions')
    
    op.drop_index('idx_aptitude_attempts_question', table_name='aptitude_attempts')
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
    
    op.drop_index('idx_assessment_sessions_context_id', table_name='assessment_sessions')
    op.drop_index('one_active_session_per_user', table_name='assessment_sessions')
    op.drop_table('assessment_sessions')
    
    op.drop_index('idx_assessment_contexts_policy_id', table_name='assessment_contexts')
    op.drop_index('idx_assessment_contexts_student_id', table_name='assessment_contexts')
    op.drop_table('assessment_contexts')
    
    op.drop_table('assessment_policies')
    
    op.drop_index('idx_user_resumes_user_id', table_name='user_resumes')
    op.drop_table('user_resumes')
    
    op.drop_index('idx_refresh_token_hash', table_name='refresh_tokens')
    op.drop_table('refresh_tokens')
    
    op.drop_table('tpo_profiles')
    op.drop_table('faculty_profiles')
    op.drop_table('student_profiles')
    
    op.drop_index('idx_users_email', table_name='users')
    op.drop_table('users')