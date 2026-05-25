import sqlite3
import os, sys
sys.path.append(str(os.path.dirname(os.path.dirname(__file__))))
from config import DATABASE_URL
DB_PATH = DATABASE_URL.replace('sqlite+aiosqlite:///', '')
print('DB_PATH=',DB_PATH)
conn=sqlite3.connect(DB_PATH)
cur=conn.cursor()
print('interview_sessions:')
for row in cur.execute("PRAGMA table_info(interview_sessions)"):
    print(row)
print('\ninterview_turns:')
for row in cur.execute("PRAGMA table_info(interview_turns)"):
    print(row)
conn.close()
