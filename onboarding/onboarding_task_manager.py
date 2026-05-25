"""
onboarding_task_manager.py — Netra | Stage 9
Creates Day 1, Week 1, Month 1 task checklists in SQLite.
Sends emails via smtplib (free). No paid services.
"""

import sqlite3
import smtplib
import json
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from config import DATABASE_URL, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD

# Extract DB path from DATABASE_URL
DB_PATH = DATABASE_URL.replace("sqlite+aiosqlite:///", "")

TASK_CHECKLISTS = {
    "day_1": [
        "Collect laptop and access card from IT",
        "Set up company email and change password",
        "Join Slack workspace and introduce yourself",
        "Meet your manager and team",
        "Complete HR paperwork and policy acknowledgements",
    ],
    "week_1": [
        "Complete mandatory compliance training",
        "Set up all required software tools",
        "Schedule 1:1 meetings with key team members",
        "Review your 30-60-90 day goals with manager",
        "Submit bank details for payroll",
    ],
    "month_1": [
        "Complete role-specific onboarding training",
        "Submit first progress report to manager",
        "Complete 30-day check-in with HR",
        "Provide onboarding feedback survey",
    ]
}


def create_task_checklist(onboarding_id: int, candidate_id: int, joining_date: str) -> int:
    joining = datetime.strptime(joining_date, "%Y-%m-%d")
    offsets = {"day_1": 0, "week_1": 7, "month_1": 30}
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    total = 0
    for phase, tasks in TASK_CHECKLISTS.items():
        due = (joining + timedelta(days=offsets[phase])).strftime("%Y-%m-%d")
        for task in tasks:
            cur.execute("""
                INSERT INTO onboarding_tasks
                    (onboarding_id, candidate_id, phase, task, due_date, status)
                VALUES (?,?,?,?,?,'pending')
            """, (onboarding_id, candidate_id, phase, task, due))
            total += 1
    conn.commit()
    conn.close()
    print(f"[onboarding_task_manager] {total} tasks created for onboarding {onboarding_id}")
    return total


def send_task_checklist_email(candidate_email: str, candidate_name: str, joining_date: str):
    lines = []
    for phase, tasks in TASK_CHECKLISTS.items():
        lines.append(f"\n{phase.replace('_',' ').upper()}:")
        for t in tasks:
            lines.append(f"  - {t}")
    body = f"Dear {candidate_name},\n\nWelcome! Here's your onboarding checklist:\n" + \
           "\n".join(lines) + "\n\nBest regards,\nHR Team"
    msg = MIMEText(body, 'plain')
    msg['From'] = SMTP_USER
    msg['To'] = candidate_email
    msg['Subject'] = f"Your Onboarding Checklist — Starting {joining_date}"
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)


def send_pending_task_reminder(candidate_email: str, candidate_name: str, pending_tasks: list):
    items = "\n".join([f"  - {t['task']} (Due: {t['due_date']})" for t in pending_tasks])
    body = f"Dear {candidate_name},\n\nPending tasks:\n{items}\n\nBest regards,\nHR Team"
    msg = MIMEText(body, 'plain')
    msg['From'] = SMTP_USER
    msg['To'] = candidate_email
    msg['Subject'] = "Reminder: Pending Onboarding Tasks"
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)


def schedule_30_day_checkin(candidate_email: str, candidate_name: str, joining_date: str):
    checkin = (datetime.strptime(joining_date, "%Y-%m-%d") + timedelta(days=30)).strftime("%Y-%m-%d")
    body = f"Dear {candidate_name},\n\nIt's been 30 days! Please fill out our onboarding feedback survey.\n\nBest regards,\nHR Team"
    msg = MIMEText(body, 'plain')
    msg['From'] = SMTP_USER
    msg['To'] = candidate_email
    msg['Subject'] = "30-Day Check-In — How's It Going?"
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
    print(f"[onboarding_task_manager] 30-day check-in scheduled for {checkin}")


def mark_task_complete(task_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE onboarding_tasks SET status='completed', completed_at=datetime('now') WHERE id=?",
                (task_id,))
    conn.commit()
    conn.close()


def get_pending_tasks(onboarding_id: int) -> list:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, task, phase, due_date FROM onboarding_tasks
        WHERE onboarding_id=? AND status='pending' ORDER BY due_date
    """, (onboarding_id,))
    rows = cur.fetchall()
    conn.close()
    return [{"id": r[0], "task": r[1], "phase": r[2], "due_date": r[3]} for r in rows]
