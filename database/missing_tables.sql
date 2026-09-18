-- Tables defined in SQLAlchemy models but missing from schema.sql / advanced_proctoring_schema.sql

CREATE TABLE IF NOT EXISTS approved_question_pools (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES assessment_sessions(id) ON DELETE CASCADE,
    extracted_skills JSONB NOT NULL DEFAULT '[]',
    extracted_projects JSONB NOT NULL DEFAULT '{}',
    question_pool JSONB NOT NULL,
    admin_approved BOOLEAN NOT NULL DEFAULT false,
    approved_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    approved_at TIMESTAMP,
    detected_role VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_approved_question_pools_session_id ON approved_question_pools(session_id);
CREATE INDEX IF NOT EXISTS ix_approved_question_pools_admin_approved ON approved_question_pools(admin_approved);

CREATE TABLE IF NOT EXISTS interview_turns (
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
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_interview_turns_interview_id ON interview_turns(interview_id);

CREATE TABLE IF NOT EXISTS proctoring_violations (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES interview_sessions(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    confidence_score FLOAT,
    face_count INTEGER,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_proctoring_violations_session_id ON proctoring_violations(session_id);

CREATE TABLE IF NOT EXISTS rl_q_table (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    state TEXT NOT NULL,
    action TEXT NOT NULL,
    q_value FLOAT DEFAULT 0.1,
    visit_count INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, state, action)
);

CREATE TABLE IF NOT EXISTS rl_attempt_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    session_id INTEGER,
    question_id INTEGER,
    difficulty TEXT,
    state_before TEXT,
    action_taken TEXT,
    reward FLOAT,
    state_after TEXT,
    response_time FLOAT,
    is_correct BOOLEAN,
    created_at TIMESTAMP DEFAULT NOW()
);