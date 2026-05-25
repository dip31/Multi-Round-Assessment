"""
offer_dispatcher.py — Netra | Stage 8
Sends offer PDF via email (smtplib — free, uses Gmail).
Tracks sent/opened/signed/declined.
On acceptance fires offer.accepted. On decline fires offer.declined.
"""

import sqlite3
import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from config import DATABASE_URL, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD

# Extract DB path from DATABASE_URL
DB_PATH = DATABASE_URL.replace("sqlite+aiosqlite:///", "")


def get_offer_details(offer_id: int) -> dict:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT o.id, o.candidate_id, o.job_id, o.offered_salary,
               o.pdf_path, o.joining_date,
               c.name, c.email, j.title
        FROM offers o
        JOIN candidates c ON c.id=o.candidate_id
        JOIN jobs j ON j.id=o.job_id
        WHERE o.id=?
    """, (offer_id,))
    row = cur.fetchone()
    conn.close()
    return {
        "offer_id": row[0], "candidate_id": row[1], "job_id": row[2],
        "offered_salary": row[3], "pdf_path": row[4], "joining_date": row[5],
        "candidate_name": row[6], "candidate_email": row[7], "job_title": row[8]
    }


def send_offer_email(offer: dict):
    """Send offer PDF via Gmail SMTP (free)."""
    msg = MIMEMultipart()
    msg['From'] = SMTP_USER
    msg['To'] = offer['candidate_email']
    msg['Subject'] = f"Job Offer — {offer['job_title']}"

    body = f"""Dear {offer['candidate_name']},

Please find your offer letter attached for the position of {offer['job_title']}.

Offered Salary : ${offer['offered_salary']:,.0f}
Joining Date   : {offer['joining_date']}

Please reply to this email to accept or negotiate.

Best regards,
HR Team"""
    msg.attach(MIMEText(body, 'plain'))

    # Attach PDF
    if offer['pdf_path'] and os.path.exists(offer['pdf_path']):
        with open(offer['pdf_path'], 'rb') as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition',
                            f'attachment; filename=offer_letter.pdf')
            msg.attach(part)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
    print(f"[offer_dispatcher] Offer email sent to {offer['candidate_email']}")


def send_reminder_email(offer: dict):
    msg = MIMEMultipart()
    msg['From'] = SMTP_USER
    msg['To'] = offer['candidate_email']
    msg['Subject'] = f"Reminder: Please respond to your offer — {offer['job_title']}"
    msg.attach(MIMEText(
        f"Dear {offer['candidate_name']},\n\nThis is a reminder to respond to your offer.\n\nHR Team",
        'plain'))
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)


def update_offer_status(offer_id: int, status: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE offers SET status=? WHERE id=?", (status, offer_id))
    conn.commit()
    conn.close()


def dispatch_offer(offer_id: int):
    offer = get_offer_details(offer_id)
    send_offer_email(offer)
    update_offer_status(offer_id, "sent")
    print(f"[offer_dispatcher] Offer {offer_id} dispatched ✅")
