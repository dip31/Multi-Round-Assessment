"""Create core tables in SQLite database."""
import sqlite3

conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# Create users table
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'student' CHECK (role IN ('student','admin')),
    is_active BOOLEAN NOT NULL DEFAULT 1,
    is_verified BOOLEAN NOT NULL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")

# Create refresh_tokens table
cursor.execute("""
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token_hash TEXT NOT NULL,
    expires_at DATETIME NOT NULL,
    is_revoked BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
)
""")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_refresh_token_hash ON refresh_tokens(token_hash)")

# Create assessment_sessions table
cursor.execute("""
CREATE TABLE IF NOT EXISTS assessment_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('not_started','in_progress','completed','terminated','expired')),
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    total_score REAL DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
""")
# SQLite doesn't support partial indexes with WHERE clause like PostgreSQL
# CREATE UNIQUE INDEX one_active_session_per_user ON assessment_sessions(user_id) WHERE status='in_progress';

# Create assessment_rounds table
cursor.execute("""
CREATE TABLE IF NOT EXISTS assessment_rounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    round_type VARCHAR(20) NOT NULL CHECK (round_type IN ('aptitude','coding','interview')),
    status VARCHAR(20) NOT NULL CHECK (status IN ('pending','active','completed','terminated','expired')),
    score REAL DEFAULT 0,
    max_questions INTEGER NOT NULL DEFAULT 20,
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    FOREIGN KEY (session_id) REFERENCES assessment_sessions(id) ON DELETE CASCADE
)
""")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_round_session ON assessment_rounds(session_id)")

# Create aptitude_topics table
cursor.execute("""
CREATE TABLE IF NOT EXISTS aptitude_topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) UNIQUE NOT NULL
)
""")

# Create aptitude_questions table
cursor.execute("""
CREATE TABLE IF NOT EXISTS aptitude_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_text TEXT NOT NULL,
    option_a TEXT NOT NULL,
    option_b TEXT NOT NULL,
    option_c TEXT NOT NULL,
    option_d TEXT NOT NULL,
    correct_option CHAR(1) NOT NULL CHECK (correct_option IN ('A','B','C','D')),
    difficulty VARCHAR(10) NOT NULL CHECK (difficulty IN ('easy','medium','hard')),
    topic_id INTEGER,
    version INTEGER NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_by INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (topic_id) REFERENCES aptitude_topics(id),
    FOREIGN KEY (created_by) REFERENCES users(id)
)
""")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_aptitude_difficulty ON aptitude_questions(difficulty)")

# Create admin_question_feedback table
cursor.execute("""
CREATE TABLE IF NOT EXISTS admin_question_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER NOT NULL,
    admin_id INTEGER,
    action VARCHAR(20) NOT NULL CHECK (action IN ('approve','reject','review')),
    suggestion TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (question_id) REFERENCES aptitude_questions(id) ON DELETE CASCADE,
    FOREIGN KEY (admin_id) REFERENCES users(id) ON DELETE SET NULL
)
""")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_admin_qf_question_id ON admin_question_feedback(question_id)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_admin_qf_admin_id ON admin_question_feedback(admin_id)")

# Create aptitude_attempts table
cursor.execute("""
CREATE TABLE IF NOT EXISTS aptitude_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    round_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    attempt_number INTEGER NOT NULL,
    selected_option CHAR(1),
    is_correct BOOLEAN,
    response_time REAL,
    difficulty VARCHAR(10),
    reward REAL,
    attempted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (round_id) REFERENCES assessment_rounds(id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES aptitude_questions(id),
    UNIQUE (round_id, attempt_number)
)
""")

# Create rl_sessions table
cursor.execute("""
CREATE TABLE IF NOT EXISTS rl_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    round_id INTEGER NOT NULL,
    step_number INTEGER NOT NULL,
    prev_difficulty VARCHAR(10) CHECK (prev_difficulty IN ('easy','medium','hard')),
    action_taken VARCHAR(10) NOT NULL CHECK (action_taken IN ('easy','medium','hard')),
    reward_received REAL,
    accuracy_so_far REAL,
    avg_response_time REAL,
    q_values TEXT,  -- JSON stored as TEXT for SQLite
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (round_id) REFERENCES assessment_rounds(id) ON DELETE CASCADE,
    UNIQUE (round_id, step_number)
)
""")

# Create coding_problems table
cursor.execute("""
CREATE TABLE IF NOT EXISTS coding_problems (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    difficulty VARCHAR(10) CHECK (difficulty IN ('easy','medium','hard')),
    tags TEXT,  -- JSON array stored as TEXT
    input_format TEXT,
    output_format TEXT,
    constraints TEXT,
    created_by INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id)
)
""")

# Create coding_test_cases table
cursor.execute("""
CREATE TABLE IF NOT EXISTS coding_test_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    problem_id INTEGER NOT NULL,
    input_data TEXT NOT NULL,
    expected_output TEXT NOT NULL,
    is_hidden BOOLEAN DEFAULT 1,
    case_order INTEGER NOT NULL DEFAULT 0,
    explanation TEXT,
    FOREIGN KEY (problem_id) REFERENCES coding_problems(id) ON DELETE CASCADE
)
""")

# Create session_problems table
cursor.execute("""
CREATE TABLE IF NOT EXISTS session_problems (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    round_id INTEGER NOT NULL,
    problem_id INTEGER NOT NULL,
    problem_order INTEGER NOT NULL DEFAULT 0,
    marked_for_review BOOLEAN NOT NULL DEFAULT 0,
    assigned_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (round_id) REFERENCES assessment_rounds(id) ON DELETE CASCADE,
    FOREIGN KEY (problem_id) REFERENCES coding_problems(id) ON DELETE CASCADE
)
""")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_problems_round ON session_problems(round_id)")

# Create coding_submissions table
cursor.execute("""
CREATE TABLE IF NOT EXISTS coding_submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    round_id INTEGER NOT NULL,
    problem_id INTEGER NOT NULL,
    code TEXT NOT NULL,
    language VARCHAR(50),
    judge0_token VARCHAR(100),
    status VARCHAR(30) CHECK (status IN ('running','accepted','wrong_answer','runtime_error','time_limit_exceeded','compilation_error','memory_limit_exceeded','internal_error')),
    score REAL,
    execution_time REAL,
    memory_used INTEGER,
    submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (round_id) REFERENCES assessment_rounds(id) ON DELETE CASCADE,
    FOREIGN KEY (problem_id) REFERENCES coding_problems(id)
)
""")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_coding_submission_round ON coding_submissions(round_id)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_judge0_token ON coding_submissions(judge0_token)")

# Create interview_sessions table
cursor.execute("""
CREATE TABLE IF NOT EXISTS interview_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    round_id INTEGER NOT NULL,
    transcript TEXT,
    behavioral_score REAL,
    confidence_score REAL,
    technical_score REAL,
    rl_state TEXT,  -- JSON stored as TEXT
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (round_id) REFERENCES assessment_rounds(id) ON DELETE CASCADE
)
""")

# Create user_resumes table
cursor.execute("""
CREATE TABLE IF NOT EXISTS user_resumes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    resume_text TEXT NOT NULL,
    parsed_skills TEXT,  -- JSON stored as TEXT
    parsed_projects TEXT,  -- JSON stored as TEXT
    uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
)
""")

conn.commit()
conn.close()
print("Core tables created successfully!")

# Verify
conn = sqlite3.connect('database.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print('All tables:', [t[0] for t in tables])
conn.close()