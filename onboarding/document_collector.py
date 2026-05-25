"""
document_collector.py — Netra | Stage 9
Emails document checklist via smtplib (free).
Stores uploaded docs on local filesystem (no AWS).
Tracks pending vs submitted in SQLite.
"""

import sqlite3
import smtplib
import json
import os
from email.mime.text import MIMEText
from config import DATABASE_URL, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, DOCS_DIR

# Extract DB path from DATABASE_URL
DB_PATH = DATABASE_URL.replace("sqlite+aiosqlite:///", "")

REQUIRED_DOCUMENTS = [
    "id_proof",
    "address_proof",
    "educational_certificates",
    "previous_offer_letter"
]

DOCUMENT_LABELS = {
    "id_proof": "Government-issued ID (Passport / Driver's License)",
    "address_proof": "Address Proof (Utility Bill / Bank Statement)",
    "educational_certificates": "Educational Certificates (Degree / Marksheets)",
    "previous_offer_letter": "Previous Offer Letter or Relieving Letter"
}


def get_upload_path(candidate_id: int, doc_type: str) -> str:
    """Local folder path for document upload (replaces S3 pre-signed URL)."""
    folder = os.path.join(DOCS_DIR, str(candidate_id))
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, f"{doc_type}.pdf")


def create_onboarding_record(candidate_id: int, offer_id: int) -> int:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO onboarding (candidate_id, offer_id, status, documents_pending)
        VALUES (?,?,?,?)
    """, (candidate_id, offer_id, "pending", json.dumps(REQUIRED_DOCUMENTS)))
    onboarding_id = cur.lastrowid
    conn.commit()
    conn.close()
    return onboarding_id


def send_document_checklist_email(candidate_email: str, candidate_name: str,
                                   upload_paths: dict):
    doc_list = "\n".join([
        f"  - {DOCUMENT_LABELS[doc]}\n    Upload to: {path}"
        for doc, path in upload_paths.items()
    ])
    body = f"""Dear {candidate_name},

Welcome aboard! Please submit the following documents within 7 days:

{doc_list}

Please place your documents in the paths listed above.

Best regards,
HR Team"""
    msg = MIMEText(body, 'plain')
    msg['From'] = SMTP_USER
    msg['To'] = candidate_email
    msg['Subject'] = "Welcome! Please Submit Your Onboarding Documents"
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)


def mark_document_submitted(onboarding_id: int, doc_type: str, file_path: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT documents_submitted, documents_pending FROM onboarding WHERE id=?",
                (onboarding_id,))
    row = cur.fetchone()
    submitted = json.loads(row[0] or '{}')
    pending = json.loads(row[1] or '[]')
    submitted[doc_type] = file_path
    pending = [d for d in pending if d != doc_type]
    cur.execute("""
        UPDATE onboarding SET documents_submitted=?, documents_pending=? WHERE id=?
    """, (json.dumps(submitted), json.dumps(pending), onboarding_id))
    conn.commit()
    conn.close()


def check_document_completeness(onboarding_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT documents_pending FROM onboarding WHERE id=?", (onboarding_id,))
    pending = json.loads(cur.fetchone()[0] or '[]')
    conn.close()
    return len(pending) == 0


def get_pending_documents(onboarding_id: int) -> list:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT documents_pending FROM onboarding WHERE id=?", (onboarding_id,))
    row = cur.fetchone()
    conn.close()
    return json.loads(row[0]) if row and row[0] else []
