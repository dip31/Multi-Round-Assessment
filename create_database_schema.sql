-- ============================================================================
-- EDI5 Multi-Round Assessment Platform - Complete Database Schema
-- Generated from SQLAlchemy ORM Models
-- Run this single file against any PostgreSQL database to create the full schema
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================================================
-- USERS & PROFILES
-- ============================================================================

-- Users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'student',
    is_active BOOLEAN NOT NULL DEFAULT true,
    is_verified BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);

-- Student Profiles
CREATE TABLE student_profiles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    roll_number VARCHAR(50),
    department VARCHAR(100) NOT NULL DEFAULT 'Computer Science',
    cgpa FLOAT NOT NULL DEFAULT 7.50,
    graduation_year INTEGER NOT NULL DEFAULT 2026,
    backlogs_count INTEGER NOT NULL DEFAULT 0,
    institution VARCHAR(200) NOT NULL DEFAULT 'Engineering College',
    target_role VARCHAR(100) DEFAULT 'Software Development Engineer',
    skills_json JSONB NOT NULL DEFAULT '[]',
    phone_number VARCHAR(20),
    mobile_no VARCHAR(50),
    full_name VARCHAR(150),
    college_email_id VARCHAR(150),
    gender VARCHAR(50),
    date_of_birth VARCHAR(50),
    nationality VARCHAR(100) DEFAULT 'Indian',
    tenth_marks FLOAT,
    twelfth_marks FLOAT,
    bio TEXT,
    portfolio_data JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_student_profiles_user_id ON student_profiles(user_id);
CREATE INDEX idx_student_profiles_department ON student_profiles(department);

-- Faculty Profiles
CREATE TABLE faculty_profiles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    department VARCHAR(100) NOT NULL DEFAULT 'Computer Science',
    designation VARCHAR(100) NOT NULL DEFAULT 'Assistant Professor',
    institution VARCHAR(200) NOT NULL DEFAULT 'Engineering College',
    employee_id VARCHAR(50),
    bio TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_faculty_profiles_user_id ON faculty_profiles(user_id);

-- TPO Profiles
CREATE TABLE tpo_profiles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    institution VARCHAR(200) NOT NULL DEFAULT 'Engineering College',
    designation VARCHAR(100) NOT NULL DEFAULT 'Training & Placement Officer',
    contact_email VARCHAR(150),
    contact_phone VARCHAR(20),
    bio TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tpo_profiles_user_id ON tpo_profiles(user_id);

-- User Resumes
CREATE TABLE user_resumes (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    cv_name VARCHAR(200) NOT NULL DEFAULT 'My Resume',
    cv_type VARCHAR(100) NOT NULL DEFAULT 'Software Developer',
    file_name VARCHAR(255) NOT NULL DEFAULT 'resume.pdf',
    file_path VARCHAR(500) NOT NULL DEFAULT '',
    file_size INTEGER NOT NULL DEFAULT 0,
    resume_text TEXT,
    parsed_skills JSONB NOT NULL DEFAULT '[]',
    parsed_projects JSONB NOT NULL DEFAULT '[]',
    uploaded_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_user_resumes_user_id ON user_resumes(user_id);

-- ============================================================================
-- ASSESSMENT CONTEXTS & POLICIES
-- ============================================================================

-- Assessment Policies
CREATE TABLE assessment_policies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    session_duration_minutes INTEGER NOT NULL DEFAULT 180,
    round_duration_minutes INTEGER NOT NULL DEFAULT 30,
    max_attempts INTEGER,
    resume_allowed BOOLEAN NOT NULL DEFAULT true,
    exit_allowed BOOLEAN NOT NULL DEFAULT true,
    progression_mode VARCHAR(20) NOT NULL DEFAULT 'sequential',
    progression_config JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Assessment Contexts
CREATE TABLE assessment_contexts (
    id SERIAL PRIMARY KEY,
    mode VARCHAR(50) NOT NULL,
    purpose VARCHAR(100),
    created_by_id INTEGER REFERENCES users(id),
    student_id INTEGER REFERENCES users(id),
    company_name VARCHAR(200),
    target_role VARCHAR(100),
    jd_text TEXT,
    availability_start TIMESTAMP WITH TIME ZONE,
    availability_end TIMESTAMP WITH TIME ZONE,
    policy_id INTEGER NOT NULL REFERENCES assessment_policies(id),
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_assessment_contexts_mode ON assessment_contexts(mode);
CREATE INDEX idx_assessment_contexts_student_id ON assessment_contexts(student_id);
CREATE INDEX idx_assessment_contexts_policy_id ON assessment_contexts(policy_id);

-- Assessment Sessions
CREATE TABLE assessment_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    context_id INTEGER REFERENCES assessment_contexts(id),
    status VARCHAR(20) NOT NULL DEFAULT 'not_started',
    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    total_score FLOAT NOT NULL DEFAULT 0
);

CREATE INDEX idx_assessment_sessions_user_id ON assessment_sessions(user_id);
CREATE INDEX idx_assessment_sessions_context_id ON assessment_sessions(context_id);
CREATE INDEX idx_assessment_sessions_status ON assessment_sessions(status);

-- Assessment Rounds
CREATE TABLE assessment_rounds (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES assessment_sessions(id) ON DELETE CASCADE,
    round_type VARCHAR(20) NOT NULL,
    practice_type VARCHAR(20),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    score FLOAT NOT NULL DEFAULT 0,
    max_questions INTEGER NOT NULL DEFAULT 20,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_assessment_rounds_session_id ON assessment_rounds(session_id);
CREATE INDEX idx_assessment_rounds_round_type ON assessment_rounds(round_type);
CREATE INDEX idx_assessment_rounds_status ON assessment_rounds(status);

-- ============================================================================
-- APTITUDE ROUND
-- ============================================================================

-- Aptitude Topics
CREATE TABLE aptitude_topics (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL
);

CREATE INDEX idx_aptitude_topics_name ON aptitude_topics(name);

-- Aptitude Questions
CREATE TABLE aptitude_questions (
    id SERIAL PRIMARY KEY,
    question_text TEXT NOT NULL,
    option_a TEXT NOT NULL,
    option_b TEXT NOT NULL,
    option_c TEXT NOT NULL,
    option_d TEXT NOT NULL,
    correct_option CHAR(1) NOT NULL,
    difficulty VARCHAR(10) NOT NULL,
    topic_id INTEGER REFERENCES aptitude_topics(id),
    version INTEGER NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_aptitude_questions_difficulty ON aptitude_questions(difficulty);
CREATE INDEX idx_aptitude_questions_topic_id ON aptitude_questions(topic_id);
CREATE INDEX idx_aptitude_questions_is_active ON aptitude_questions(is_active);

-- Aptitude Attempts
CREATE TABLE aptitude_attempts (
    id SERIAL PRIMARY KEY,
    round_id INTEGER NOT NULL REFERENCES assessment_rounds(id) ON DELETE CASCADE,
    question_id INTEGER NOT NULL REFERENCES aptitude_questions(id),
    attempt_number INTEGER NOT NULL,
    selected_option CHAR(1),
    is_correct BOOLEAN,
    response_time FLOAT,
    difficulty VARCHAR(10),
    reward FLOAT,
    attempted_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_aptitude_attempts_round_id ON aptitude_attempts(round_id);
CREATE INDEX idx_aptitude_attempts_question_id ON aptitude_attempts(question_id);

-- RL Sessions (Aptitude)
CREATE TABLE rl_sessions (
    id SERIAL PRIMARY KEY,
    round_id INTEGER NOT NULL REFERENCES assessment_rounds(id) ON DELETE CASCADE,
    step_number INTEGER NOT NULL,
    prev_difficulty VARCHAR(10),
    action_taken VARCHAR(10) NOT NULL,
    reward_received FLOAT,
    accuracy_so_far FLOAT,
    avg_response_time FLOAT,
    q_values TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_rl_sessions_round_id ON rl_sessions(round_id);

-- ============================================================================
-- CODING ROUND
-- ============================================================================

-- Coding Problems
CREATE TABLE coding_problems (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    difficulty VARCHAR(10),
    tags TEXT,
    input_format TEXT,
    output_format TEXT,
    constraints TEXT,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_coding_problems_difficulty ON coding_problems(difficulty);

-- Coding Test Cases
CREATE TABLE coding_test_cases (
    id SERIAL PRIMARY KEY,
    problem_id INTEGER NOT NULL REFERENCES coding_problems(id) ON DELETE CASCADE,
    input_data TEXT NOT NULL,
    expected_output TEXT NOT NULL,
    is_hidden BOOLEAN NOT NULL DEFAULT true,
    case_order INTEGER NOT NULL DEFAULT 0,
    explanation TEXT
);

CREATE INDEX idx_coding_test_cases_problem_id ON coding_test_cases(problem_id);

-- Coding Submissions
CREATE TABLE coding_submissions (
    id SERIAL PRIMARY KEY,
    round_id INTEGER NOT NULL REFERENCES assessment_rounds(id) ON DELETE CASCADE,
    problem_id INTEGER NOT NULL REFERENCES coding_problems(id),
    code TEXT NOT NULL,
    language VARCHAR(50),
    judge0_token VARCHAR(100),
    status VARCHAR(30),
    score FLOAT,
    execution_time FLOAT,
    memory_used INTEGER,
    submitted_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_coding_submissions_round_id ON coding_submissions(round_id);
CREATE INDEX idx_coding_submissions_problem_id ON coding_submissions(problem_id);
CREATE INDEX idx_coding_submissions_judge0_token ON coding_submissions(judge0_token);

-- Session Problems (assigned problems for a round)
CREATE TABLE session_problems (
    id SERIAL PRIMARY KEY,
    round_id INTEGER NOT NULL REFERENCES assessment_rounds(id) ON DELETE CASCADE,
    problem_id INTEGER NOT NULL REFERENCES coding_problems(id) ON DELETE CASCADE,
    problem_order INTEGER NOT NULL DEFAULT 0,
    marked_for_review BOOLEAN NOT NULL DEFAULT false,
    assigned_at TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE INDEX idx_session_problems_round_id ON session_problems(round_id);
CREATE INDEX idx_session_problems_problem_id ON session_problems(problem_id);

-- ============================================================================
-- INTERVIEW ROUND
-- ============================================================================

-- Approved Question Pools
CREATE TABLE approved_question_pools (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES assessment_sessions(id) ON DELETE CASCADE,
    extracted_skills JSONB NOT NULL DEFAULT '[]',
    extracted_projects JSONB NOT NULL DEFAULT '{}',
    question_pool JSONB NOT NULL,
    admin_approved BOOLEAN NOT NULL DEFAULT false,
    approved_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    approved_at TIMESTAMP WITH TIME ZONE,
    detected_role VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_approved_question_pools_session_id ON approved_question_pools(session_id);
CREATE INDEX idx_approved_question_pools_admin_approved ON approved_question_pools(admin_approved);

-- Interview Sessions
CREATE TABLE interview_sessions (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES assessment_sessions(id) ON DELETE CASCADE,
    round_id INTEGER REFERENCES assessment_rounds(id) ON DELETE CASCADE,
    phase VARCHAR(20) NOT NULL DEFAULT 'HR',
    current_turn INTEGER NOT NULL DEFAULT 0,
    total_turns INTEGER NOT NULL DEFAULT 10,
    rl_state JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    completion_reason VARCHAR(30),
    completed_at TIMESTAMP WITHOUT TIME ZONE,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    interviewer_id VARCHAR(50),
    retell_call_id VARCHAR(100),
    retell_agent_id VARCHAR(100),
    extraction_confidence VARCHAR(10),
    retrieval_success_rate FLOAT,
    question_personalization_rate FLOAT,
    personalization_metadata JSONB,
    follow_up_quality_score FLOAT,
    personalization_warnings JSONB
);

CREATE INDEX idx_interview_sessions_session_id ON interview_sessions(session_id);
CREATE INDEX idx_interview_sessions_round_id ON interview_sessions(round_id);
CREATE INDEX idx_interview_sessions_retell_call_id ON interview_sessions(retell_call_id);

-- Interview Turns
CREATE TABLE interview_turns (
    id SERIAL PRIMARY KEY,
    interview_id INTEGER NOT NULL REFERENCES interview_sessions(id) ON DELETE CASCADE,
    turn_number INTEGER NOT NULL,
    question_text TEXT NOT NULL,
    question_difficulty VARCHAR(10),
    candidate_response TEXT,
    response_time_sec FLOAT,
    content_score FLOAT,
    final_score FLOAT,
    intent VARCHAR(10),
    behavioral_snapshot JSONB NOT NULL DEFAULT '{}',
    rl_reward FLOAT,
    is_followup BOOLEAN NOT NULL DEFAULT false,
    followup_number INTEGER NOT NULL DEFAULT 0,
    parent_turn_id INTEGER REFERENCES interview_turns(id),
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    personalization_source VARCHAR(200),
    question_grounding_confidence FLOAT,
    answer_classification JSONB,
    followup_grounding_score FLOAT,
    followup_targeted_aspect VARCHAR(200)
);

CREATE INDEX idx_interview_turns_interview_id ON interview_turns(interview_id);
CREATE INDEX idx_interview_turns_turn_number ON interview_turns(turn_number);

-- Proctoring Violations (Interview)
CREATE TABLE proctoring_violations (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES interview_sessions(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    confidence_score FLOAT,
    face_count INTEGER,
    metadata JSONB,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_proctoring_violations_session_id ON proctoring_violations(session_id);
CREATE INDEX idx_proctoring_violations_event_type ON proctoring_violations(event_type);

-- Dynamic Interviewers
CREATE TABLE dynamic_interviewers (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    title VARCHAR(200) NOT NULL,
    tagline VARCHAR(500) NOT NULL,
    description TEXT,
    personality TEXT NOT NULL,
    speaking_style TEXT NOT NULL,
    greeting TEXT NOT NULL,
    avatar_initials VARCHAR(10) NOT NULL,
    accent VARCHAR(20) NOT NULL,
    avatar_url VARCHAR(500),
    voice_id VARCHAR(100) NOT NULL,
    voice_model VARCHAR(100),
    voice_provider VARCHAR(50) NOT NULL DEFAULT 'retell',
    language_code VARCHAR(10) NOT NULL DEFAULT 'en-US',
    pace FLOAT NOT NULL DEFAULT 0.95,
    retell_llm_id VARCHAR(100),
    retell_agent_id VARCHAR(100),
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_dynamic_interviewers_slug ON dynamic_interviewers(slug);
CREATE INDEX idx_dynamic_interviewers_retell_agent_id ON dynamic_interviewers(retell_agent_id);
CREATE INDEX idx_dynamic_interviewers_is_active ON dynamic_interviewers(is_active);

-- ============================================================================
-- PROCTORING
-- ============================================================================

-- Basic Proctoring Events
CREATE TABLE proctoring_events (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES assessment_sessions(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    event_metadata TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_proctoring_events_session_id ON proctoring_events(session_id);
CREATE INDEX idx_proctoring_events_event_type ON proctoring_events(event_type);

-- Advanced Proctoring Events
CREATE TABLE advanced_proctoring_events (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES assessment_sessions(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL DEFAULT 'INFO',
    round_type VARCHAR(20),
    confidence FLOAT,
    event_metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_advanced_proctoring_events_session_id ON advanced_proctoring_events(session_id);
CREATE INDEX idx_advanced_proctoring_events_event_type ON advanced_proctoring_events(event_type);
CREATE INDEX idx_advanced_proctoring_events_created_at ON advanced_proctoring_events(created_at);

-- ============================================================================
-- RL ENGINE
-- ============================================================================

-- RL Q-Table (per-user Q-values)
CREATE TABLE rl_q_table (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    state TEXT NOT NULL,
    action TEXT NOT NULL,
    q_value FLOAT NOT NULL DEFAULT 0.1,
    visit_count INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, state, action)
);

CREATE INDEX idx_rl_q_table_user_id ON rl_q_table(user_id);

-- RL Attempt Log (audit trail)
CREATE TABLE rl_attempt_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    session_id INTEGER,
    question_id INTEGER,
    difficulty TEXT,
    state_before TEXT,
    action_taken TEXT,
    reward FLOAT,
    state_after TEXT,
    response_time FLOAT,
    is_correct BOOLEAN,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_rl_attempt_log_user_id ON rl_attempt_log(user_id);
CREATE INDEX idx_rl_attempt_log_session_id ON rl_attempt_log(session_id);

-- ============================================================================
-- ADMIN QUESTION FEEDBACK
-- ============================================================================

CREATE TABLE admin_question_feedback (
    id SERIAL PRIMARY KEY,
    question_id INTEGER NOT NULL REFERENCES aptitude_questions(id) ON DELETE CASCADE,
    admin_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(20) NOT NULL,  -- approve | reject | flag
    suggestion TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_admin_question_feedback_question_id ON admin_question_feedback(question_id);
CREATE INDEX idx_admin_question_feedback_admin_id ON admin_question_feedback(admin_id);

-- ============================================================================
-- TRIGGERS FOR updated_at
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply triggers
CREATE TRIGGER update_student_profiles_updated_at
    BEFORE UPDATE ON student_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_faculty_profiles_updated_at
    BEFORE UPDATE ON faculty_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_tpo_profiles_updated_at
    BEFORE UPDATE ON tpo_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_assessment_policies_updated_at
    BEFORE UPDATE ON assessment_policies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_dynamic_interviewers_updated_at
    BEFORE UPDATE ON dynamic_interviewers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- DEFAULT DATA
-- ============================================================================

-- Insert default assessment policy
INSERT INTO assessment_policies (id, name, session_duration_minutes, round_duration_minutes, max_attempts, resume_allowed, exit_allowed, progression_mode, progression_config)
VALUES (1, 'Default Policy', 180, 30, NULL, true, true, 'sequential', '{"rounds": ["aptitude", "coding", "interview"]}')
ON CONFLICT (id) DO NOTHING;

-- Reset sequences to avoid conflicts
SELECT setval('users_id_seq', COALESCE((SELECT MAX(id) FROM users), 1), false);
SELECT setval('student_profiles_id_seq', COALESCE((SELECT MAX(id) FROM student_profiles), 1), false);
SELECT setval('faculty_profiles_id_seq', COALESCE((SELECT MAX(id) FROM faculty_profiles), 1), false);
SELECT setval('tpo_profiles_id_seq', COALESCE((SELECT MAX(id) FROM tpo_profiles), 1), false);
SELECT setval('user_resumes_id_seq', COALESCE((SELECT MAX(id) FROM user_resumes), 1), false);
SELECT setval('assessment_policies_id_seq', COALESCE((SELECT MAX(id) FROM assessment_policies), 1), false);
SELECT setval('assessment_contexts_id_seq', COALESCE((SELECT MAX(id) FROM assessment_contexts), 1), false);
SELECT setval('assessment_sessions_id_seq', COALESCE((SELECT MAX(id) FROM assessment_sessions), 1), false);
SELECT setval('assessment_rounds_id_seq', COALESCE((SELECT MAX(id) FROM assessment_rounds), 1), false);
SELECT setval('aptitude_topics_id_seq', COALESCE((SELECT MAX(id) FROM aptitude_topics), 1), false);
SELECT setval('aptitude_questions_id_seq', COALESCE((SELECT MAX(id) FROM aptitude_questions), 1), false);
SELECT setval('aptitude_attempts_id_seq', COALESCE((SELECT MAX(id) FROM aptitude_attempts), 1), false);
SELECT setval('rl_sessions_id_seq', COALESCE((SELECT MAX(id) FROM rl_sessions), 1), false);
SELECT setval('coding_problems_id_seq', COALESCE((SELECT MAX(id) FROM coding_problems), 1), false);
SELECT setval('coding_test_cases_id_seq', COALESCE((SELECT MAX(id) FROM coding_test_cases), 1), false);
SELECT setval('coding_submissions_id_seq', COALESCE((SELECT MAX(id) FROM coding_submissions), 1), false);
SELECT setval('session_problems_id_seq', COALESCE((SELECT MAX(id) FROM session_problems), 1), false);
SELECT setval('approved_question_pools_id_seq', COALESCE((SELECT MAX(id) FROM approved_question_pools), 1), false);
SELECT setval('interview_sessions_id_seq', COALESCE((SELECT MAX(id) FROM interview_sessions), 1), false);
SELECT setval('interview_turns_id_seq', COALESCE((SELECT MAX(id) FROM interview_turns), 1), false);
SELECT setval('proctoring_violations_id_seq', COALESCE((SELECT MAX(id) FROM proctoring_violations), 1), false);
SELECT setval('dynamic_interviewers_id_seq', COALESCE((SELECT MAX(id) FROM dynamic_interviewers), 1), false);
SELECT setval('proctoring_events_id_seq', COALESCE((SELECT MAX(id) FROM proctoring_events), 1), false);
SELECT setval('advanced_proctoring_events_id_seq', COALESCE((SELECT MAX(id) FROM advanced_proctoring_events), 1), false);
SELECT setval('admin_question_feedback_id_seq', COALESCE((SELECT MAX(id) FROM admin_question_feedback), 1), false);

-- ============================================================================
-- COMPLETION MESSAGE
-- ============================================================================
\echo '============================================================================'
\echo 'EDI5 Database Schema Created Successfully!'
\echo '============================================================================'
\echo 'Tables created:'
\echo '  - users, student_profiles, faculty_profiles, tpo_profiles, user_resumes'
\echo '  - assessment_policies, assessment_contexts, assessment_sessions, assessment_rounds'
\echo '  - aptitude_topics, aptitude_questions, aptitude_attempts, rl_sessions'
\echo '  - coding_problems, coding_test_cases, coding_submissions, session_problems'
\echo '  - interview_sessions, approved_question_pools, interview_turns, proctoring_violations, dynamic_interviewers'
\echo '  - proctoring_events, advanced_proctoring_events'
\echo '  - rl_q_table, rl_attempt_log'
\echo '  - admin_question_feedback'
\echo ''
\echo 'Default policy inserted (id=1).'
\echo 'Sequences reset to avoid ID conflicts.'
\echo '============================================================================'