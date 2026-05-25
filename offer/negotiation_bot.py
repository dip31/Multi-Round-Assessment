"""
negotiation_bot.py — Netra | Stage 8
Handles salary negotiation using Groq (free API).
Auto-approves within 10% of max budget.
Counters with max offer + benefits pitch if above budget.
"""

import sqlite3
import smtplib
from email.mime.text import MIMEText
from config import DATABASE_URL, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD

# Extract DB path from DATABASE_URL
DB_PATH = DATABASE_URL.replace("sqlite+aiosqlite:///", "")


def generate_negotiation_reply(candidate_name: str, job_title: str,
                                candidate_ask: float, decision: str,
                                counter_offer: float = None) -> str:
    """Generate negotiation reply locally — no external API."""
    if decision == "approve":
        return f"""Dear {candidate_name},

We are pleased to accept your salary request of ${candidate_ask:,.0f} for the {job_title} role.

We look forward to having you on board!

Best regards,
HR Team"""
    else:
        return f"""Dear {candidate_name},

Thank you for your response regarding the {job_title} position.

After careful consideration, our best offer is ${counter_offer:,.0f}, which includes
a comprehensive benefits package: health insurance, flexible working hours, and
a learning & development budget.

We hope you will consider this offer.

Best regards,
HR Team"""


def get_offer_and_budget(offer_id: int) -> dict:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT o.offered_salary, o.candidate_id, o.job_id,
               c.name, c.email, j.title, j.salary_max
        FROM offers o
        JOIN candidates c ON c.id=o.candidate_id
        JOIN jobs j ON j.id=o.job_id
        WHERE o.id=?
    """, (offer_id,))
    row = cur.fetchone()
    conn.close()
    return {
        "offered_salary": row[0], "candidate_id": row[1], "job_id": row[2],
        "candidate_name": row[3], "candidate_email": row[4],
        "job_title": row[5], "max_budget": row[6]
    }


def log_negotiation(offer_id: int, round_num: int,
                    candidate_ask: float, bot_response: str, approved: bool):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO negotiation_log
            (offer_id, round_number, candidate_ask, bot_response, approved)
        VALUES (?,?,?,?,?)
    """, (offer_id, round_num, candidate_ask, bot_response, 1 if approved else 0))
    conn.commit()
    conn.close()


def update_offer_salary(offer_id: int, new_salary: float):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE offers SET offered_salary=? WHERE id=?", (new_salary, offer_id))
    conn.commit()
    conn.close()


def generate_bot_reply(candidate_name: str, job_title: str,
                       candidate_ask: float, decision: str,
                       counter_offer: float = None) -> str:
    return generate_negotiation_reply(candidate_name, job_title,
                                      candidate_ask, decision, counter_offer)


def send_negotiation_email(to_email: str, subject: str, body: str):
    msg = MIMEText(body, 'plain')
    msg['From'] = SMTP_USER
    msg['To'] = to_email
    msg['Subject'] = subject
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)


def handle_negotiation(offer_id: int, candidate_ask: float, round_num: int = 1) -> dict:
    offer = get_offer_and_budget(offer_id)
    max_budget = offer['max_budget']

    if candidate_ask <= max_budget * 1.10:
        approved_salary = min(candidate_ask, max_budget)
        reply = generate_bot_reply(offer['candidate_name'], offer['job_title'],
                                   candidate_ask, "approve")
        update_offer_salary(offer_id, approved_salary)
        log_negotiation(offer_id, round_num, candidate_ask, reply, True)
        send_negotiation_email(offer['candidate_email'],
                               f"Re: Offer for {offer['job_title']}", reply)
        return {"approved": True, "final_salary": approved_salary, "message": reply}
    else:
        reply = generate_bot_reply(offer['candidate_name'], offer['job_title'],
                                   candidate_ask, "counter", max_budget)
        log_negotiation(offer_id, round_num, candidate_ask, reply, False)
        send_negotiation_email(offer['candidate_email'],
                               f"Re: Offer for {offer['job_title']}", reply)
        return {"approved": False, "final_salary": max_budget, "message": reply}
