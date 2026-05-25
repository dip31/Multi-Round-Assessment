import sqlite3
import json
import datetime
import uuid
import time
import os

# Allow running from repo root
import sys
sys.path.append(str(os.path.dirname(os.path.dirname(__file__))))

from config import DATABASE_URL

DB_PATH = DATABASE_URL.replace("sqlite+aiosqlite:///", "")
print("Using DB:", DB_PATH)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Create minimal tables if missing
cur.execute("""
CREATE TABLE IF NOT EXISTS interview_sessions (
 id TEXT PRIMARY KEY,
 candidate_id TEXT,
 job_id TEXT,
 phase TEXT,
 current_turn INTEGER,
 total_turns INTEGER,
 rl_state TEXT,
 status TEXT,
 created_at TEXT,
 completed_at TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS interview_turns (
 id TEXT PRIMARY KEY,
 interview_id TEXT,
 turn_number INTEGER,
 question_text TEXT,
 question_difficulty TEXT,
 candidate_response TEXT,
 response_time_sec REAL,
 content_score REAL,
 final_score REAL,
 intent TEXT,
 behavioral_snapshot TEXT,
 rl_reward REAL,
 is_followup INTEGER,
 followup_number INTEGER,
 parent_turn_id TEXT,
 created_at TEXT
)
""")
conn.commit()

# Insert test session and turns
now = datetime.datetime.utcnow().isoformat()
session_id = 'test_' + str(uuid.uuid4())[:8]
print('Creating interview session', session_id)
cur.execute("INSERT INTO interview_sessions (id,candidate_id,job_id,phase,current_turn,total_turns,rl_state,status,created_at,completed_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (session_id, '123', 'job_001', 'COMPLETE', 10, 10, '{}', 'completed', now, now))

turns = [
    (str(uuid.uuid4())[:8], session_id, 1, 'Q1', 'MEDIUM', 'Answer 1', 3.2, 0.8, 0.8, 'POSITIVE', json.dumps({'eye_contact_pct':0.8,'head_stability':0.7}), 0.1, 0, None, now),
    (str(uuid.uuid4())[:8], session_id, 2, 'Q2', 'MEDIUM', 'Answer 2', 2.5, 0.6, 0.65, 'NEUTRAL', json.dumps({'eye_contact_pct':0.6,'head_stability':0.6}), 0.05, 0, None, now),
    (str(uuid.uuid4())[:8], session_id, 3, 'Q3', 'HARD', 'Answer 3', 4.0, 0.9, 0.85, 'POSITIVE', json.dumps({'eye_contact_pct':0.9,'head_stability':0.8}), 0.15, 0, None, now)
]

cur.executemany("INSERT INTO interview_turns (id,interview_id,turn_number,question_text,question_difficulty,candidate_response,response_time_sec,content_score,final_score,intent,behavioral_snapshot,rl_reward,is_followup,followup_number,parent_turn_id,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", turns)
conn.commit()
print('Inserted turns')
conn.close()

# Wait a bit for server to be ready
print('Waiting 1s for server...')
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
    print('You can manually run:')
    print('curl http://localhost:8000/api/offer/candidate-interview-summary/123')
