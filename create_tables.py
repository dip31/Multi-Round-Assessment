"""Create proctoring tables directly in SQLite database."""
import sqlite3

conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# Create proctoring_events table (matching the model which uses Text for metadata)
cursor.execute("""
CREATE TABLE IF NOT EXISTS proctoring_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    event_metadata TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES assessment_sessions (id) ON DELETE CASCADE
)
""")

# Create index
cursor.execute("CREATE INDEX IF NOT EXISTS idx_proctoring_session ON proctoring_events (session_id)")

# Create advanced_proctoring_events table (matching the model which uses JSON)
cursor.execute("""
CREATE TABLE IF NOT EXISTS advanced_proctoring_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    confidence REAL,
    event_metadata JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES assessment_sessions (id) ON DELETE CASCADE
)
""")

# Create indexes
cursor.execute("CREATE INDEX IF NOT EXISTS ix_advanced_proctoring_events_id ON advanced_proctoring_events (id)")
cursor.execute("CREATE INDEX IF NOT EXISTS ix_advanced_proctoring_events_session_id ON advanced_proctoring_events (session_id)")
cursor.execute("CREATE INDEX IF NOT EXISTS ix_advanced_proctoring_events_event_type ON advanced_proctoring_events (event_type)")
cursor.execute("CREATE INDEX IF NOT EXISTS ix_advanced_proctoring_events_created_at ON advanced_proctoring_events (created_at)")

# Create proctoring_violations table (for interview proctoring)
cursor.execute("""
CREATE TABLE IF NOT EXISTS proctoring_violations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    confidence_score REAL,
    face_count INTEGER,
    metadata JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES interview_sessions (id) ON DELETE CASCADE
)
""")

cursor.execute("CREATE INDEX IF NOT EXISTS idx_violations_session ON proctoring_violations (session_id, created_at)")

conn.commit()
conn.close()
print("Tables created successfully!")

# Verify
conn = sqlite3.connect('database.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%proctor%'")
tables = cursor.fetchall()
print('Proctoring tables:', tables)

for table in ['proctoring_events', 'advanced_proctoring_events', 'proctoring_violations']:
    cursor.execute(f"PRAGMA table_info({table})")
    cols = cursor.fetchall()
    print(f'{table} columns:', cols)

conn.close()