"""
offer_letter_generator.py — Netra | Stage 8
Consumes decision.made events. Pulls candidate + job data.
Generates PDF via ReportLab. Uses Groq (free) for personalization.
Storage: local filesystem (no AWS needed).
"""

import json
import sqlite3
import os
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from config import DATABASE_URL, OFFERS_DIR

# Extract DB path from DATABASE_URL
DB_PATH = DATABASE_URL.replace("sqlite+aiosqlite:///", "")


def get_candidate_and_job(candidate_id: int, job_id: int) -> dict:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT c.name, c.email, c.phone, c.experience_years,
               j.title, j.department, j.salary_min, j.salary_max,
               j.location, j.employment_type
        FROM candidates c, jobs j
        WHERE c.id=? AND j.id=?
    """, (candidate_id, job_id))
    row = cur.fetchone()
    conn.close()
    return {
        "candidate_name": row[0], "candidate_email": row[1],
        "candidate_phone": row[2], "experience_years": row[3],
        "job_title": row[4], "department": row[5],
        "salary_min": row[6], "salary_max": row[7],
        "location": row[8], "employment_type": row[9],
    }


def generate_letter_text(data: dict) -> str:
    """Generate offer letter text locally — no external API needed."""
    return f"""Dear {data['candidate_name']},

We are delighted to offer you the position of {data['job_title']} in our {data['department']} team.

Offer Details:
  - Annual Salary  : ${data['offered_salary']:,.0f}
  - Joining Date   : {data['joining_date']}
  - Location       : {data['location']}
  - Employment Type: {data['employment_type']}

Please sign and return this letter within 7 days to confirm your acceptance.

We look forward to welcoming you to the team!

Best regards,
HR Team"""


def generate_offer_pdf(data: dict, letter_text: str) -> str:
    os.makedirs(OFFERS_DIR, exist_ok=True)
    filename = os.path.join(OFFERS_DIR, f"offer_{data['candidate_id']}_{data['job_id']}.pdf")
    doc = SimpleDocTemplate(filename, pagesize=A4,
                            rightMargin=inch, leftMargin=inch,
                            topMargin=inch, bottomMargin=inch)
    styles = getSampleStyleSheet()
    story = [Paragraph("OFFER LETTER", styles['Title']), Spacer(1, 0.3 * inch),
             Paragraph(f"Dear {data['candidate_name']},", styles['Normal']),
             Spacer(1, 0.2 * inch)]
    for line in letter_text.split('\n'):
        if line.strip():
            story.append(Paragraph(line, styles['Normal']))
            story.append(Spacer(1, 0.1 * inch))
    doc.build(story)
    return filename


def save_offer_to_db(candidate_id: int, job_id: int,
                     offered_salary: float, pdf_path: str, joining_date: str,
                     interview_id: int = None) -> int:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Ensure schema supports interview_id column (add if missing)
    try:
        cur.execute("PRAGMA table_info(offers)")
        cols = [r[1] for r in cur.fetchall()]
        if 'interview_id' not in cols:
            cur.execute("ALTER TABLE offers ADD COLUMN interview_id INTEGER")
    except Exception:
        # If offers table does not exist or ALTER fails, continue and let insert fail later
        pass

    if interview_id is not None:
        cur.execute("""
            INSERT INTO offers (candidate_id, job_id, offered_salary, pdf_path,
                                joining_date, interview_id, status)
            VALUES (?,?,?,?,?,?,'generated')
        """, (candidate_id, job_id, offered_salary, pdf_path, joining_date, interview_id))
    else:
        cur.execute("""
            INSERT INTO offers (candidate_id, job_id, offered_salary, pdf_path,
                                joining_date, status)
            VALUES (?,?,?,?,?,'generated')
        """, (candidate_id, job_id, offered_salary, pdf_path, joining_date))

    offer_id = cur.lastrowid
    conn.commit()
    conn.close()
    return offer_id
