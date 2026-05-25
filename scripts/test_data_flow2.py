import sqlite3
import json
import datetime
import time
import os, sys
sys.path.append(str(os.path.dirname(os.path.dirname(__file__))))
from config import DATABASE_URL

DB_PATH = DATABASE_URL.replace('sqlite+aiosqlite:///', '')
print('Using DB:', DB_PATH)
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Ensure candidate_id column exists
cols = [r[1] for r in cur.execute("PRAGMA table_info(interview_sessions)")]
print('Columns in interview_sessions:', cols)
if 'candidate_id' not in cols:
    print('Adding candidate_id column')
    cur.execute("ALTER TABLE interview_sessions ADD COLUMN candidate_id TEXT")
    conn.commit()
# Add job_id, status, completed_at if missing
cols = [r[1] for r in cur.execute("PRAGMA table_info(interview_sessions)")]
if 'job_id' not in cols:
    print('Adding job_id column')
    cur.execute("ALTER TABLE interview_sessions ADD COLUMN job_id TEXT")
if 'status' not in cols:
    print('Adding status column')
    cur.execute("ALTER TABLE interview_sessions ADD COLUMN status TEXT")
if 'completed_at' not in cols:
    print('Adding completed_at column')
    cur.execute("ALTER TABLE interview_sessions ADD COLUMN completed_at TEXT")
conn.commit()

# Insert a completed interview (leave id to autoincrement)
now = datetime.datetime.utcnow().isoformat()
cur.execute("INSERT INTO interview_sessions (candidate_id, job_id, phase, current_turn, total_turns, rl_state, status, created_at, completed_at) VALUES (?,?,?,?,?,?,?,?,?)",
            ('123', 'job_001', 'COMPLETE', 10, 10, '{}', 'completed', now, now))
interview_id = cur.lastrowid
print('Inserted interview_id', interview_id)

# Insert some main turns (no id provided)
turns = [
    (interview_id, 1, 'Q1', 'MEDIUM', 'Answer 1', 3.2, 0.8, 0.8, 'POSITIVE', json.dumps({'eye_contact_pct':0.8,'head_stability':0.7}), 0.1, 0, 0, now),
    (interview_id, 2, 'Q2', 'MEDIUM', 'Answer 2', 2.5, 0.6, 0.65, 'NEUTRAL', json.dumps({'eye_contact_pct':0.6,'head_stability':0.6}), 0.05, 0, 0, now),
    (interview_id, 3, 'Q3', 'HARD', 'Answer 3', 4.0, 0.9, 0.85, 'POSITIVE', json.dumps({'eye_contact_pct':0.9,'head_stability':0.8}), 0.15, 0, 0, now)
]
cur.executemany("INSERT INTO interview_turns (interview_id,turn_number,question_text,question_difficulty,candidate_response,response_time_sec,content_score,final_score,intent,behavioral_snapshot,rl_reward,is_followup,followup_number,parent_turn_id,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", turns)
conn.commit()
print('Inserted turns')
conn.close()

# Wait briefly
time.sleep(1)

# Call API
try:
    import requests
    url = 'http://localhost:8000/api/offer/candidate-interview-summary/123'
    print('Calling', url)
    r = requests.get(url, timeout=5)
    print('Status:', r.status_code)
    print('Response:', r.text)
except Exception as e:
    print('Request failed:', e)
    print('Manually run: curl http://localhost:8000/api/offer/candidate-interview-summary/123')
