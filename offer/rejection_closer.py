"""
rejection_closer.py — Netra | Stage 8
Sends closing emails via smtplib (free).
Adds waitlisted candidates to talent pool.
"""

import sqlite3
import smtplib
import json
from email.mime.text import MIMEText
from config import DATABASE_URL, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD

# Extract DB path from DATABASE_URL
DB_PATH = DATABASE_URL.replace("sqlite+aiosqlite:///", "")


def get_waitlisted_candidates(job_id: int) -> list:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT c.id, c.name, c.email, c.skills, c.experience_years
        FROM candidates c JOIN applications a ON a.candidate_id=c.id
        WHERE a.job_id=? AND a.status='waitlisted'
    """, (job_id,))
    rows = cur.fetchall()
    conn.close()
    return [{"id": r[0], "name": r[1], "email": r[2],
             "skills": json.loads(r[3]) if r[3] else [], "experience_years": r[4]}
            for r in rows]


def get_job_title(job_id: int) -> str:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT title FROM jobs WHERE id=?", (job_id,))
    title = cur.fetchone()[0]
    conn.close()
    return title


def send_closing_email(candidate: dict, job_title: str):
    body = f"""Dear {candidate['name']},

Thank you for your time and interest in the {job_title} position.

After careful consideration, we have moved forward with another candidate.
We were impressed by your profile and will keep you in mind for future roles.

Best regards,
HR Team"""
    msg = MIMEText(body, 'plain')
    msg['From'] = SMTP_USER
    msg['To'] = candidate['email']
    msg['Subject'] = f"Update on Your Application — {job_title}"
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)


def add_to_talent_pool(candidate: dict, job_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO talent_pool
            (candidate_id, skills, experience_years, source)
        VALUES (?,?,?,'waitlisted')
    """, (candidate['id'], json.dumps(candidate['skills']), candidate['experience_years']))
    conn.commit()
    conn.close()


def update_application_status(candidate_id: int, job_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE applications SET status='closed' WHERE candidate_id=? AND job_id=?",
                (candidate_id, job_id))
    conn.commit()
    conn.close()
