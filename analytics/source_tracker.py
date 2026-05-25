"""
source_tracker.py — Netra | Stage 10
SQLite-based source tracking. No paid APIs.
"""

import sqlite3
from config import DATABASE_URL

# Extract DB path from DATABASE_URL
DB_PATH = DATABASE_URL.replace("sqlite+aiosqlite:///", "")

PLATFORM_COSTS = {
    "linkedin": 1200, "naukri": 400, "indeed": 300,
    "github": 0, "referral": 500, "direct": 0, "other": 100
}


def get_source_funnel() -> list:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT c.source,
               COUNT(DISTINCT c.id)                                         AS applicants,
               COUNT(DISTINCT CASE WHEN a.status IN ('selected','waitlisted')
                                   THEN c.id END)                           AS shortlisted,
               COUNT(DISTINCT CASE WHEN a.status='selected' THEN c.id END)  AS interviewed,
               COUNT(DISTINCT o.id)                                         AS offered,
               COUNT(DISTINCT CASE WHEN o.status='accepted' THEN o.id END)  AS hired
        FROM candidates c
        LEFT JOIN applications a ON a.candidate_id=c.id
        LEFT JOIN offers o ON o.candidate_id=c.id
        GROUP BY c.source
        ORDER BY applicants DESC
    """)
    rows = cur.fetchall()
    conn.close()
    results = []
    for row in rows:
        source, applicants, shortlisted, interviewed, offered, hired = row
        conv = round((hired / applicants * 100), 2) if applicants > 0 else 0
        results.append({
            "source": source, "applicants": applicants, "shortlisted": shortlisted,
            "interviewed": interviewed, "offered": offered, "hired": hired,
            "conversion_rate_pct": conv
        })
    return results


def calculate_cost_per_hire() -> list:
    sources = get_source_funnel()
    results = []
    for s in sources:
        cost = PLATFORM_COSTS.get(s['source'].lower(), PLATFORM_COSTS['other'])
        cph = round(cost / s['hired'], 2) if s['hired'] > 0 else None
        results.append({"source": s['source'], "hired": s['hired'],
                        "platform_monthly_cost": cost, "cost_per_hire": cph})
    return sorted(results, key=lambda x: (x['cost_per_hire'] or 9999))


def get_best_performing_source() -> dict:
    sources = get_source_funnel()
    return max(sources, key=lambda x: x['conversion_rate_pct']) if sources else {}

def track_source_roi() -> dict:
    """Calculate ROI metrics for all candidate sources."""
    funnel = get_source_funnel()
    cost_per_hire = calculate_cost_per_hire()
    best_source = get_best_performing_source()
    
    return {
        "source_funnel": funnel,
        "cost_analysis": cost_per_hire,
        "best_performing_source": best_source,
        "total_sources": len(funnel)
    }