DROP TABLE IF EXISTS interview_turns CASCADE;
DROP TABLE IF EXISTS proctoring_violations CASCADE;
DROP TABLE IF EXISTS interview_sessions CASCADE;

CREATE TABLE interview_sessions (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES assessment_sessions(id) ON DELETE CASCADE,
    phase VARCHAR(20) NOT NULL DEFAULT 'HR',
    current_turn INTEGER NOT NULL DEFAULT 0,
    total_turns INTEGER NOT NULL DEFAULT 10,
    rl_state JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    completion_reason VARCHAR(30),
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX ix_interview_sessions_session_id ON interview_sessions(session_id);

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
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX ix_interview_turns_interview_id ON interview_turns(interview_id);

CREATE TABLE proctoring_violations (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES interview_sessions(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    confidence_score FLOAT,
    face_count INTEGER,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX ix_proctoring_violations_session_id ON proctoring_violations(session_id);