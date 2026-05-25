-- ═══════════════════════════════════════════════════════════════
-- AI Recruitment System — PostgreSQL Schema
-- All table definitions for the recruitment pipeline
-- ═══════════════════════════════════════════════════════════════

-- Jobs table: stores job requisitions
CREATE TABLE IF NOT EXISTS jobs (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    department      TEXT,
    location        TEXT,
    employment_type TEXT DEFAULT 'full-time',
    experience_min  INTEGER DEFAULT 0,
    experience_max  INTEGER DEFAULT 0,
    salary_min      REAL,
    salary_max      REAL,
    currency        TEXT DEFAULT 'INR',
    skills          TEXT,              -- JSON array of required skills
    qualification   TEXT,              -- Required education level for scoring
    description     TEXT,              -- AI-generated full JD
    status          TEXT DEFAULT 'draft',  -- draft, active, closed
    headcount       INTEGER DEFAULT 1,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Candidates table: stores candidate profiles
CREATE TABLE IF NOT EXISTS candidates (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    email           TEXT,
    phone           TEXT,
    location        TEXT,
    current_role    TEXT,
    experience_years REAL DEFAULT 0,
    skills          TEXT,              -- JSON array
    education       TEXT,              -- JSON array
    work_history    TEXT,              -- JSON array
    resume_url      TEXT,
    source          TEXT DEFAULT 'upload',  -- upload, linkedin, github, naukri
    source_profile_url TEXT,
    raw_resume_text TEXT,
    parsed_data     TEXT,              -- Full parsed JSON from LlamaIndex
    status          TEXT DEFAULT 'new',    -- new, parsed, screened, shortlisted, rejected
    
    -- Stage 3 Screening fields
    job_id          TEXT,              -- Link to job for screening
    score           REAL,              -- Overall screening score
    score_breakdown TEXT,              -- JSON breakdown of scoring components
    is_duplicate    BOOLEAN DEFAULT FALSE,
    merged_into     TEXT,              -- ID of original candidate if duplicate
    rejection_reason TEXT,             -- Reason for rejection
    
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(id)
);

-- Applications: links candidates to jobs
CREATE TABLE IF NOT EXISTS applications (
    id              TEXT PRIMARY KEY,
    job_id          TEXT NOT NULL,
    candidate_id    TEXT NOT NULL,
    status          TEXT DEFAULT 'applied',  -- applied, screening, interview, offered, rejected
    match_score     REAL,
    applied_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(id),
    FOREIGN KEY (candidate_id) REFERENCES candidates(id)
);

-- Job postings: tracks where jobs are posted
CREATE TABLE IF NOT EXISTS job_postings (
    id              TEXT PRIMARY KEY,
    job_id          TEXT NOT NULL,
    platform        TEXT NOT NULL,     -- linkedin, indeed, naukri
    external_id     TEXT,              -- ID from the platform
    post_url        TEXT,
    status          TEXT DEFAULT 'pending',  -- pending, posted, expired, failed
    posted_at       TIMESTAMP,
    expires_at      TIMESTAMP,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(id)
);

-- Scores: candidate matching scores for jobs
CREATE TABLE IF NOT EXISTS scores (
    id              TEXT PRIMARY KEY,
    job_id          TEXT NOT NULL,
    candidate_id    TEXT NOT NULL,
    overall_score   REAL DEFAULT 0,
    skill_match     REAL DEFAULT 0,
    experience_match REAL DEFAULT 0,
    location_match  REAL DEFAULT 0,
    education_match REAL DEFAULT 0,
    scoring_algorithm TEXT DEFAULT 'basic',
    scored_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(id),
    FOREIGN KEY (candidate_id) REFERENCES candidates(id)
);

-- Interviews: interview scheduling and tracking
CREATE TABLE IF NOT EXISTS interviews (
    id              TEXT PRIMARY KEY,
    application_id  TEXT NOT NULL,
    interview_type  TEXT DEFAULT 'technical',  -- technical, hr, final, panel
    scheduled_at    TIMESTAMP,
    duration_minutes INTEGER DEFAULT 60,
    interviewer     TEXT,
    location        TEXT,
    meeting_link    TEXT,
    status          TEXT DEFAULT 'scheduled',  -- scheduled, completed, cancelled, rescheduled
    feedback        TEXT,
    rating          INTEGER,  -- 1-5 scale
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (application_id) REFERENCES applications(id)
);

-- Offers: job offer management
CREATE TABLE IF NOT EXISTS offers (
    id              TEXT PRIMARY KEY,
    application_id  TEXT NOT NULL,
    salary_offered  REAL,
    currency        TEXT DEFAULT 'INR',
    benefits        TEXT,              -- JSON array
    start_date      DATE,
    offer_letter_url TEXT,
    status          TEXT DEFAULT 'pending',  -- pending, accepted, rejected, withdrawn
    offered_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    response_deadline TIMESTAMP,
    accepted_at     TIMESTAMP,
    rejected_at     TIMESTAMP,
    rejection_reason TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (application_id) REFERENCES applications(id)
);

-- Onboarding Tasks: new hire onboarding checklist
CREATE TABLE IF NOT EXISTS onboarding_tasks (
    id              TEXT PRIMARY KEY,
    offer_id        TEXT NOT NULL,
    task_name       TEXT NOT NULL,
    task_description TEXT,
    assigned_to     TEXT,
    due_date        DATE,
    status          TEXT DEFAULT 'pending',  -- pending, in_progress, completed, skipped
    completed_at    TIMESTAMP,
    notes           TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (offer_id) REFERENCES offers(id)
);

-- Communications: candidate communication tracking
CREATE TABLE IF NOT EXISTS communications (
    id              TEXT PRIMARY KEY,
    candidate_id    TEXT NOT NULL,
    job_id          TEXT,
    communication_type TEXT NOT NULL,  -- email, sms, call, meeting
    direction       TEXT NOT NULL,     -- inbound, outbound
    subject         TEXT,
    content         TEXT,
    sent_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    read_at         TIMESTAMP,
    response_required BOOLEAN DEFAULT FALSE,
    response_deadline TIMESTAMP,
    created_by      TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (candidate_id) REFERENCES candidates(id),
    FOREIGN KEY (job_id) REFERENCES jobs(id)
);

-- Audit log: tracks all system events
CREATE TABLE IF NOT EXISTS audit_log (
    id              TEXT PRIMARY KEY,
    event_type      TEXT NOT NULL,
    agent_name      TEXT NOT NULL,
    entity_type     TEXT,
    entity_id       TEXT,
    details         TEXT,              -- JSON payload
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
