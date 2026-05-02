-- ============================================
-- AI Placement Platform Database Schema v3.0
-- PostgreSQL
-- ============================================


-- ============================================
-- USERS
-- ============================================
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'student',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK (role IN ('student','admin'))
);

CREATE INDEX idx_users_email ON users(email);



-- ============================================
-- REFRESH TOKENS
-- ============================================
CREATE TABLE refresh_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    token_hash TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    is_revoked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_refresh_token_hash ON refresh_tokens(token_hash);



-- ============================================
-- USER RESUMES
-- ============================================
CREATE TABLE user_resumes (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    resume_text TEXT NOT NULL,
    parsed_skills JSONB,
    parsed_projects JSONB,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);



-- ============================================
-- ASSESSMENT SESSIONS
-- ============================================
CREATE TABLE assessment_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL
        CHECK (status IN ('not_started','in_progress','completed','terminated','expired')),
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    total_score FLOAT DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE UNIQUE INDEX one_active_session_per_user
ON assessment_sessions(user_id)
WHERE status='in_progress';



-- ============================================
-- ASSESSMENT ROUNDS
-- ============================================
CREATE TABLE assessment_rounds (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL,
    round_type VARCHAR(20) NOT NULL
        CHECK (round_type IN ('aptitude','coding','interview')),
    status VARCHAR(20) NOT NULL
        CHECK (status IN ('pending','active','completed','terminated','expired')),
    score FLOAT DEFAULT 0,
    max_questions INTEGER NOT NULL DEFAULT 20,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (session_id)
        REFERENCES assessment_sessions(id) ON DELETE CASCADE
);

CREATE INDEX idx_round_session ON assessment_rounds(session_id);



-- ============================================
-- APTITUDE TOPICS
-- ============================================
CREATE TABLE aptitude_topics (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL
);



-- ============================================
-- APTITUDE QUESTIONS
-- ============================================
CREATE TABLE aptitude_questions (
    id SERIAL PRIMARY KEY,
    question_text TEXT NOT NULL,
    option_a TEXT NOT NULL,
    option_b TEXT NOT NULL,
    option_c TEXT NOT NULL,
    option_d TEXT NOT NULL,
    correct_option CHAR(1) NOT NULL
        CHECK (correct_option IN ('A','B','C','D')),
    difficulty VARCHAR(10) NOT NULL
        CHECK (difficulty IN ('easy','medium','hard')),
    topic_id INTEGER,
    version INTEGER NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (topic_id) REFERENCES aptitude_topics(id),
    FOREIGN KEY (created_by) REFERENCES users(id)
);

CREATE INDEX idx_aptitude_difficulty ON aptitude_questions(difficulty);



-- ============================================
-- ADMIN QUESTION FEEDBACK
-- ============================================
CREATE TABLE admin_question_feedback (
    id SERIAL PRIMARY KEY,
    question_id INTEGER NOT NULL,
    admin_id INTEGER,
    action VARCHAR(20) NOT NULL
        CHECK (action IN ('approve','reject','review')),
    suggestion TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (question_id)
        REFERENCES aptitude_questions(id) ON DELETE CASCADE,
    FOREIGN KEY (admin_id)
        REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_admin_qf_question_id ON admin_question_feedback(question_id);
CREATE INDEX idx_admin_qf_admin_id ON admin_question_feedback(admin_id);



-- ============================================
-- APTITUDE ATTEMPTS
-- ============================================
CREATE TABLE aptitude_attempts (
    id SERIAL PRIMARY KEY,
    round_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    attempt_number INTEGER NOT NULL,
    selected_option CHAR(1),
    is_correct BOOLEAN,
    response_time FLOAT,
    difficulty VARCHAR(10),
    reward FLOAT,
    attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (round_id)
        REFERENCES assessment_rounds(id) ON DELETE CASCADE,
    FOREIGN KEY (question_id)
        REFERENCES aptitude_questions(id),
    UNIQUE (round_id, attempt_number)
);



-- ============================================
-- RL SESSIONS
-- ============================================
CREATE TABLE rl_sessions (
    id SERIAL PRIMARY KEY,
    round_id INTEGER NOT NULL,
    step_number INTEGER NOT NULL,
    prev_difficulty VARCHAR(10)
        CHECK (prev_difficulty IN ('easy','medium','hard')),
    action_taken VARCHAR(10) NOT NULL
        CHECK (action_taken IN ('easy','medium','hard')),
    reward_received FLOAT,
    accuracy_so_far FLOAT,
    avg_response_time FLOAT,
    q_values JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (round_id)
        REFERENCES assessment_rounds(id) ON DELETE CASCADE,
    UNIQUE (round_id, step_number)
);



-- ============================================
-- CODING PROBLEMS
-- ============================================
CREATE TABLE coding_problems (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    difficulty VARCHAR(10)
        CHECK (difficulty IN ('easy','medium','hard')),
    tags TEXT[],
    input_format TEXT,
    output_format TEXT,
    constraints TEXT,
    created_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id)
);



-- ============================================
-- CODING TEST CASES
-- ============================================
CREATE TABLE coding_test_cases (
    id SERIAL PRIMARY KEY,
    problem_id INTEGER NOT NULL,
    input_data TEXT NOT NULL,
    expected_output TEXT NOT NULL,
    is_hidden BOOLEAN DEFAULT TRUE,
    case_order INTEGER NOT NULL DEFAULT 0,
    explanation TEXT,
    FOREIGN KEY (problem_id)
        REFERENCES coding_problems(id) ON DELETE CASCADE
);



-- ============================================
-- CODING SUBMISSIONS
-- ============================================
CREATE TABLE coding_submissions (
    id SERIAL PRIMARY KEY,
    round_id INTEGER NOT NULL,
    problem_id INTEGER NOT NULL,
    code TEXT NOT NULL,
    language VARCHAR(50),
    judge0_token VARCHAR(100),
    status VARCHAR(30)
        CHECK (status IN (
            'running',
            'accepted',
            'wrong_answer',
            'runtime_error',
            'time_limit_exceeded',
            'compilation_error'
        )),
    score FLOAT,
    execution_time FLOAT,
    memory_used INTEGER,
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (round_id)
        REFERENCES assessment_rounds(id) ON DELETE CASCADE,
    FOREIGN KEY (problem_id)
        REFERENCES coding_problems(id)
);

CREATE INDEX idx_coding_submission_round
ON coding_submissions(round_id);

CREATE INDEX idx_judge0_token
ON coding_submissions(judge0_token);



-- ============================================
-- PROCTORING EVENTS
-- ============================================
CREATE TABLE proctoring_events (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    event_metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (session_id)
        REFERENCES assessment_sessions(id) ON DELETE CASCADE
);

CREATE INDEX idx_proctoring_session
ON proctoring_events(session_id);



-- ============================================
-- INTERVIEW SESSIONS
-- ============================================
CREATE TABLE interview_sessions (
    id SERIAL PRIMARY KEY,
    round_id INTEGER NOT NULL,
    transcript TEXT,
    behavioral_score FLOAT,
    confidence_score FLOAT,
    technical_score FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (round_id)
        REFERENCES assessment_rounds(id) ON DELETE CASCADE
);



-- ============================================
-- MATERIALIZED VIEW
-- ============================================
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
GROUP BY r.id, r.round_type;


CREATE UNIQUE INDEX idx_round_analytics_round_id
ON round_analytics(round_id);