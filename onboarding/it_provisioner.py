"""
it_provisioner.py — Netra | Stage 9
Free implementation — no Google Workspace, JIRA, or Slack APIs.
Generates provisioning report as a local text file.
In production: swap each section with real API calls.
"""

import sqlite3
import json
import os
from datetime import datetime
from config import DATABASE_URL, PROVISIONING_DIR

# Extract DB path from DATABASE_URL
DB_PATH = DATABASE_URL.replace("sqlite+aiosqlite:///", "")

ROLE_SOFTWARE_MAP = {
    "engineering": ["GitHub", "VSCode", "Postman", "AWS Console", "Jira", "Confluence"],
    "design": ["Figma", "Adobe XD", "Zeplin", "Jira"],
    "marketing": ["HubSpot", "Google Analytics", "Canva", "Slack"],
    "hr": ["Workday", "LinkedIn Recruiter", "Slack", "Google Workspace"],
    "default": ["Office365", "Slack", "Zoom", "Google Workspace"]
}


def get_candidate_and_role(candidate_id: int) -> dict:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT c.name, c.email, j.title, j.department, j.location
        FROM candidates c
        JOIN offers o ON o.candidate_id=c.id
        JOIN jobs j ON j.id=o.job_id
        WHERE c.id=? AND o.status='accepted'
        LIMIT 1
    """, (candidate_id,))
    row = cur.fetchone()
    conn.close()
    return {"name": row[0], "personal_email": row[1],
            "job_title": row[2], "department": row[3].lower(), "location": row[4]}


def generate_company_email(name: str, domain: str = "company.com") -> str:
    parts = name.lower().split()
    return f"{parts[0]}.{parts[-1]}@{domain}"


def assign_software_licenses(department: str) -> list:
    return ROLE_SOFTWARE_MAP.get(department, ROLE_SOFTWARE_MAP['default'])


def generate_provisioning_report(candidate_id: int, onboarding_id: int,
                                  company_email: str, licenses: list,
                                  ticket_id: str) -> str:
    """Save provisioning details to a local text file (replaces JIRA/Google API)."""
    os.makedirs(PROVISIONING_DIR, exist_ok=True)
    path = os.path.join(PROVISIONING_DIR, f"it_provision_{candidate_id}.txt")
    with open(path, 'w', encoding='utf-8') as f:
        f.write(f"IT PROVISIONING REPORT\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n")
        f.write(f"{'='*40}\n")
        f.write(f"Candidate ID   : {candidate_id}\n")
        f.write(f"Onboarding ID  : {onboarding_id}\n")
        f.write(f"Company Email  : {company_email}\n")
        f.write(f"Ticket ID      : {ticket_id}\n")
        f.write(f"Slack Invited  : Yes\n")
        f.write(f"Licenses       : {', '.join(licenses)}\n")
        f.write(f"\n[IN PRODUCTION]\n")
        f.write(f"- Google Workspace API → create {company_email}\n")
        f.write(f"- JIRA API → raise laptop ticket {ticket_id}\n")
        f.write(f"- Slack API → invite {company_email}\n")
    return path


def save_it_provisioning(onboarding_id: int, company_email: str,
                          ticket: str, licenses: list):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        UPDATE onboarding
        SET company_email=?, it_jira_ticket=?,
            software_licenses=?, slack_invited=1,
            status='it_provisioned'
        WHERE id=?
    """, (company_email, ticket, json.dumps(licenses), onboarding_id))
    conn.commit()
    conn.close()


def provision(onboarding_id: int, candidate_id: int) -> dict:
    info = get_candidate_and_role(candidate_id)
    company_email = generate_company_email(info['name'])
    licenses = assign_software_licenses(info['department'])
    ticket_id = f"IT-{1000 + candidate_id}"

    report_path = generate_provisioning_report(
        candidate_id, onboarding_id, company_email, licenses, ticket_id)
    save_it_provisioning(onboarding_id, company_email, ticket_id, licenses)

    print(f"[it_provisioner] ✅ Provisioning complete")
    print(f"  Company Email : {company_email}")
    print(f"  Ticket        : {ticket_id}")
    print(f"  Licenses      : {', '.join(licenses)}")
    print(f"  Report saved  : {report_path}")

    return {"company_email": company_email, "ticket": ticket_id,
            "licenses": licenses, "report": report_path}
