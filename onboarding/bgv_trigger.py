"""
bgv_trigger.py — Netra | Stage 9
Simulated BGV — no paid SpringVerify API.
Runs basic rule-based checks on submitted documents.
In production: swap simulate_bgv_check() with real SpringVerify call.
"""

import sqlite3
import json
import os
from config import DATABASE_URL, DOCS_DIR

# Extract DB path from DATABASE_URL
DB_PATH = DATABASE_URL.replace("sqlite+aiosqlite:///", "")


def get_candidate_details(candidate_id: int) -> dict:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT name, email, phone, date_of_birth, address, pan_number, aadhar_number
        FROM candidates WHERE id=?
    """, (candidate_id,))
    row = cur.fetchone()
    conn.close()
    return {
        "name": row[0], "email": row[1], "phone": row[2],
        "dob": row[3], "address": row[4], "pan": row[5], "aadhar": row[6]
    }


def get_submitted_documents(onboarding_id: int) -> dict:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT documents_submitted FROM onboarding WHERE id=?", (onboarding_id,))
    row = cur.fetchone()
    conn.close()
    return json.loads(row[0]) if row and row[0] else {}


def simulate_bgv_check(candidate: dict, documents: dict) -> dict:
    """
    Rule-based BGV simulation (free — no external API).
    Checks: all docs present, PAN format valid, phone length valid.
    In production: replace with SpringVerify API call.
    """
    discrepancies = []

    required = ["id_proof", "address_proof", "educational_certificates", "previous_offer_letter"]
    for doc in required:
        if doc not in documents:
            discrepancies.append(f"Missing document: {doc}")

    if candidate.get('pan') and len(candidate['pan']) != 10:
        discrepancies.append("PAN number format invalid")

    if candidate.get('phone') and len(str(candidate['phone'])) != 10:
        discrepancies.append("Phone number invalid")

    status = "clear" if not discrepancies else "flagged"
    return {"status": status, "discrepancies": discrepancies, "request_id": "BGV_SIM_LOCAL"}


def save_bgv_result(onboarding_id: int, result: dict):
    status = result['status']
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        UPDATE onboarding
        SET bgv_request_id=?, bgv_status=?, bgv_discrepancies=?,
            status=?
        WHERE id=?
    """, (
        result['request_id'],
        status,
        json.dumps(result['discrepancies']),
        'bgv_complete' if status == 'clear' else 'bgv_flagged',
        onboarding_id
    ))
    conn.commit()
    conn.close()


def handle_bgv_result(onboarding_id: int, result: dict):
    status = result.get('status')
    discrepancies = result.get('discrepancies', [])
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        UPDATE onboarding
        SET bgv_status=?, bgv_discrepancies=?, status=?
        WHERE id=?
    """, (
        status,
        json.dumps(discrepancies),
        'bgv_complete' if status == 'clear' else 'bgv_flagged',
        onboarding_id
    ))
    conn.commit()
    conn.close()
    if discrepancies:
        print(f"[bgv_trigger] ⚠️  Discrepancies found: {discrepancies}")
    else:
        print(f"[bgv_trigger] ✅ BGV clear for onboarding {onboarding_id}")


def trigger_bgv(onboarding_id: int, candidate_id: int) -> str:
    candidate = get_candidate_details(candidate_id)
    documents = get_submitted_documents(onboarding_id)
    result = simulate_bgv_check(candidate, documents)
    save_bgv_result(onboarding_id, result)
    print(f"[bgv_trigger] BGV result: {result['status']} | ID: {result['request_id']}")
    return result['request_id']
