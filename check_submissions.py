import sqlite3
conn = sqlite3.connect('database.db')
cursor = conn.cursor()

cursor.execute('SELECT * FROM assessment_rounds WHERE round_type="coding"')
for row in cursor.fetchall():
    print('Round:', row)

cursor.execute('SELECT * FROM session_problems')
for row in cursor.fetchall():
    print('SessionProblem:', row)

cursor.execute('SELECT * FROM assessment_sessions')
for row in cursor.fetchall():
    print('Session:', row)

cursor.execute('SELECT * FROM coding_submissions')
for row in cursor.fetchall():
    print('Submission:', row)

conn.close()