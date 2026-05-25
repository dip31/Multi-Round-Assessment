"""
time_to_hire_reporter.py — Netra | Stage 10
SQLite-based. Email alerts via smtplib (free). No paid APIs.
"""

import sqlite3
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
from config import DATABASE_URL, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD

# Extract DB path from DATABASE_URL
DB_PATH = DATABASE_URL.replace("sqlite+aiosqlite:///", "")

STAGE_BENCHMARKS = {
    "intake_to_sourcing": 2,
    "sourcing_to_screening": 3,
    "screening_to_outreach": 1,
    "outreach_to_prescreening": 5,
    "prescreening_to_interview": 3,
    "interview_to_evaluation": 2,
    "evaluation_to_offer": 1,
    "offer_to_acceptance": 7,
}


def get_candidate_stage_timestamps(candidate_id: int) -> dict:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT event_type, created_at FROM audit_log WHERE entity_id=? AND entity_type='candidate' ORDER BY created_at",
                (str(candidate_id),))
    rows = cur.fetchall()
    conn.close()
    return {r[0]: datetime.fromisoformat(r[1]) for r in rows if r[1]}


def calculate_stage_durations(timestamps: dict) -> dict:
    stage_order = [
        "job_posted", "profile_parsed", "shortlisted", "outreach_sent",
        "prescreening_passed", "interview_scheduled", "interview_completed",
        "decision_made", "offer_sent", "offer_accepted"
    ]
    keys = list(STAGE_BENCHMARKS.keys())
    durations = {}
    for i, key in enumerate(keys):
        from_s, to_s = stage_order[i], stage_order[i + 1]
        if from_s in timestamps and to_s in timestamps:
            durations[key] = (timestamps[to_s] - timestamps[from_s]).days
    return durations


def calculate_total_time_to_hire(timestamps: dict) -> int:
    if "job_posted" in timestamps and "offer_accepted" in timestamps:
        return (timestamps["offer_accepted"] - timestamps["job_posted"]).days
    return -1


def check_sla_breaches(durations: dict) -> list:
    return [
        {"stage": s, "actual_days": d, "benchmark_days": STAGE_BENCHMARKS[s],
         "exceeded_by": d - STAGE_BENCHMARKS[s]}
        for s, d in durations.items() if d > STAGE_BENCHMARKS.get(s, 999)
    ]


def send_sla_alert(breaches: list, job_title: str, candidate_id: int):
    rows = "\n".join([
        f"  {b['stage']}: {b['actual_days']} days (benchmark: {b['benchmark_days']}, exceeded by +{b['exceeded_by']})"
        for b in breaches
    ])
    body = f"SLA Breach Alert — {job_title} (Candidate {candidate_id})\n\n{rows}\n\nPlease review."
    msg = MIMEText(body, 'plain')
    msg['From'] = SMTP_USER
    msg['To'] = SMTP_USER  # alert goes to HR manager (same account for dev)
    msg['Subject'] = f"⚠️ SLA Breach — {job_title}"
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)


def get_avg_time_to_hire_by_department() -> list:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT j.department, COUNT(o.id) AS hires
        FROM offers o JOIN jobs j ON j.id=o.job_id
        WHERE o.status='accepted'
        GROUP BY j.department
    """)
    rows = cur.fetchall()
    conn.close()
    return [{"department": r[0], "total_hires": r[1]} for r in rows]


def generate_report(candidate_id: int, job_title: str) -> dict:
    timestamps = get_candidate_stage_timestamps(candidate_id)
    durations = calculate_stage_durations(timestamps)
    total_days = calculate_total_time_to_hire(timestamps)
    breaches = check_sla_breaches(durations)
    if breaches:
        send_sla_alert(breaches, job_title, candidate_id)
    report = {
        "candidate_id": candidate_id, "job_title": job_title,
        "total_days_to_hire": total_days, "stage_durations": durations,
        "sla_breaches": breaches,
        "sla_status": "breached" if breaches else "on_track"
    }
    print(f"[time_to_hire_reporter] {total_days} days | {'⚠️ SLA breached' if breaches else '✅ On track'}")
    return report


def calculate_time_to_hire() -> dict:
    """Calculate time-to-hire metrics for all completed hires."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Get basic metrics
    cur.execute("""
        SELECT 
            AVG(julianday(o.created_at) - julianday(j.created_at)) as avg_days_job_to_offer,
            COUNT(*) as total_offers,
            COUNT(CASE WHEN o.status = 'accepted' THEN 1 END) as accepted_offers
        FROM offers o 
        JOIN jobs j ON j.id = o.job_id
    """)
    result = cur.fetchone()
    
    avg_days = result[0] if result[0] else 0
    total_offers = result[1] if result[1] else 0
    accepted_offers = result[2] if result[2] else 0
    
    # Get department breakdown
    cur.execute("""
        SELECT 
            j.department,
            AVG(julianday(o.created_at) - julianday(j.created_at)) as avg_days,
            COUNT(*) as offers_count
        FROM offers o 
        JOIN jobs j ON j.id = o.job_id
        WHERE o.status = 'accepted'
        GROUP BY j.department
    """)
    dept_breakdown = [
        {
            "department": row[0] or "Unknown",
            "avg_days": round(row[1], 1) if row[1] else 0,
            "hires": row[2]
        }
        for row in cur.fetchall()
    ]
    
    conn.close()
    
    return {
        "overall_avg_days": round(avg_days, 1),
        "total_offers": total_offers,
        "accepted_offers": accepted_offers,
        "acceptance_rate": round((accepted_offers / total_offers * 100), 1) if total_offers > 0 else 0,
        "department_breakdown": dept_breakdown
    }