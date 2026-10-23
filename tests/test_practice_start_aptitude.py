#!/usr/bin/env python
"""Test what happens when we call /practice/start with round_type='aptitude'."""

import sys
sys.path.insert(0, '.')

from fastapi.testclient import TestClient
from app.main import app
import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()
db_url = os.getenv("DATABASE_URL")

print("=" * 80)
print("TESTING /practice/start WITH round_type='aptitude'")
print("=" * 80)

# First, get a valid JWT token for user 21
# You'll need to login first or use an existing token
print("\nNote: You need to provide a valid JWT token for user 21")
print("Get it from your browser's localStorage or Network tab")
print("\nFor now, checking what the backend SHOULD do:")

# Check the database state
conn = psycopg2.connect(db_url)
cursor = conn.cursor()

print("\n[1] Current session 277 state:")
cursor.execute("""
    SELECT id, user_id, status, context_id
    FROM assessment_sessions
    WHERE id = 277
""")
session = cursor.fetchone()
print(f"  Session: {session}")

print("\n[2] Current rounds for session 277:")
cursor.execute("""
    SELECT id, round_type, status
    FROM assessment_rounds
    WHERE session_id = 277
    ORDER BY id
""")
for r in cursor.fetchall():
    print(f"  Round {r[0]}: {r[1]:10} {r[2]}")

print("\n[3] Context and Policy for session 277:")
cursor.execute("""
    SELECT c.id, c.mode, p.id, p.name, p.progression_mode
    FROM assessment_sessions s
    JOIN assessment_contexts c ON c.id = s.context_id
    JOIN assessment_policies p ON p.id = c.policy_id
    WHERE s.id = 277
""")
context = cursor.fetchone()
if context:
    print(f"  Context {context[0]}: {context[1]}")
    print(f"  Policy {context[2]}: {context[3]}")
    print(f"  Progression mode: {context[4]}")
    
    if context[4] == 'sequential':
        print("\n  ⚠ PROBLEM FOUND!")
        print("  progression_mode is 'sequential'")
        print("  This means /practice/start will ALWAYS start with 'aptitude'")
        print("  even if user requests 'coding' or 'interview'")
        print("\n  From practice_router.py line 273:")
        print("    if progression_mode == 'independent':")
        print("        round_type_to_start = payload.round_type")
        print("    else:")
        print("        round_type_to_start = ROUND_ORDER[0]  # ← Always 'aptitude'")
    elif context[4] == 'independent':
        print("\n  ✓ progression_mode is 'independent'")
        print("  User-requested round type will be used")
else:
    print("  ✗ No context found!")

print("\n[4] What SHOULD happen when user clicks 'Start Aptitude':")
print("  1. Frontend: POST /practice/start {round_type: 'aptitude'}")
print("  2. Backend: Finds existing session 277 (in_progress)")
print("  3. Backend: Calls get_active_round(277)")
print("  4. Backend: _expire_stale_rounds() expires round 270")
print("  5. Backend: No active round found")
print("  6. Backend: Creates NEW 'aptitude' round")
print("  7. Backend: Returns 201 with active_round = aptitude")
print("  8. Frontend: Navigates to /aptitude")
print("  9. Frontend: Calls GET /aptitude/next-question")
print(" 10. Backend: Finds active aptitude round, returns question")

print("\n[5] What's ACTUALLY happening (hypothesis):")
print("  - Session 277 exists with context 26")
print("  - Context 26 might have progression_mode = 'sequential'")
print("  - When you click 'Start Aptitude', backend ignores your choice")
print("  - Backend starts ROUND_ORDER[0] = 'aptitude' (correct by accident)")
print("  - OR backend is resuming existing session instead of creating new round")

conn.close()

print("\n" + "=" * 80)
print("RECOMMENDATION:")
print("=" * 80)
print("\n1. Check context 26's progression_mode:")
print("   psql ... -c \"SELECT id, mode, policy_id FROM assessment_contexts WHERE id = 26;\"")
print("   psql ... -c \"SELECT id, name, progression_mode FROM assessment_policies WHERE id IN (SELECT policy_id FROM assessment_contexts WHERE id = 26);\"")
print("\n2. If progression_mode = 'sequential':")
print("   This is causing the issue. Should be 'independent' for Practice.")
print("\n3. Solution:")
print("   UPDATE assessment_contexts SET policy_id = 2 WHERE id = 26;")
print("   (Policy 2 is 'Practice Policy' with progression_mode = 'independent')")
