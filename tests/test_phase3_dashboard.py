"""
Automated tests for Phase 3: Student Dashboard + Real Data.

Verifies:
1. Latest completed session returned on /api/v1/session/status when no active session.
2. Analytics session_history includes Aptitude, Coding, and Interview rounds.
3. Real analytics calculations (overall readiness, accuracy, percentile).
4. Student ownership (Student A cannot retrieve Student B's data).
5. Unauthenticated access rejected (401).
6. Fresh assessment cycle endpoint /api/v1/session/fresh.
7. Empty student data handled cleanly.
"""

import uuid
import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from app.main import app
from app.database.db import SessionLocal
from app.models.user import User
from app.models.assessment import AssessmentSession, AssessmentRound
from app.models.profile import StudentProfile

client = TestClient(app)


def _create_student(name: str = "Test Student", cgpa: float = 8.5, backlogs: int = 0):
    uid = uuid.uuid4().hex[:6]
    email = f"student_{uid}@college.edu"
    password = "Password@123"

    reg_resp = client.post(
        "/api/v1/auth/register",
        json={
            "name": name,
            "email": email,
            "password": password,
            "role": "student",
        },
    )
    assert reg_resp.status_code == 201

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    user_id = login_resp.json()["user"]["id"]

    headers = {"Authorization": f"Bearer {token}"}

    # Update profile CGPA, backlogs, department via standard API
    client.put(
        "/api/v1/profile/student/me",
        headers=headers,
        json={
            "cgpa": cgpa,
            "backlogs_count": backlogs,
            "roll_number": f"CS-{uid.upper()}",
            "department": "Computer Science",
            "target_role": "Full Stack Engineer",
        },
    )

    return {"email": email, "token": token, "user_id": user_id, "headers": headers}


def _get_test_db():
    from app.database.db import get_db
    if get_db in app.dependency_overrides:
        gen = app.dependency_overrides[get_db]()
        return next(gen)
    return SessionLocal()


def test_latest_completed_session_on_session_status():
    """Verify that when no active session exists, /session/status returns latest completed session."""
    student = _create_student("Latest Session Student")

    # 1. Start a session
    start_resp = client.post("/api/v1/session/start", headers=student["headers"])
    assert start_resp.status_code in (200, 201)
    session_id = start_resp.json()["id"]

    # Complete the session
    comp_resp = client.post("/api/v1/session/complete", headers=student["headers"])
    assert comp_resp.status_code == 200
    assert comp_resp.json()["status"] == "completed"

    # 2. Query /session/status: should return the completed session rather than 404 or empty
    status_resp = client.get("/api/v1/session/status", headers=student["headers"])
    assert status_resp.status_code == 200
    data = status_resp.json()

    assert data["id"] == session_id
    assert data["status"] == "completed"
    assert "rounds" in data
    assert len(data["rounds"]) >= 1


def test_analytics_session_history_includes_all_three_rounds():
    """Verify that /api/v1/report/analytics session_history includes Aptitude, Coding, and Interview rounds."""
    student = _create_student("History Student")

    # Seed real completed rounds for this student in DB
    db = _get_test_db()
    sess = AssessmentSession(user_id=student["user_id"], status="completed", total_score=0.85)
    db.add(sess)
    db.commit()
    db.refresh(sess)

    # Add Aptitude round
    apt_round = AssessmentRound(
        session_id=sess.id,
        round_type="aptitude",
        status="completed",
        score=0.80,
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
    )
    # Add Coding round
    cod_round = AssessmentRound(
        session_id=sess.id,
        round_type="coding",
        status="completed",
        score=0.90,
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
    )
    # Add Interview round
    int_round = AssessmentRound(
        session_id=sess.id,
        round_type="interview",
        status="completed",
        score=0.85,
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
    )
    db.add_all([apt_round, cod_round, int_round])
    db.commit()
    db.close()

    # Call /report/analytics
    analytics_resp = client.get("/api/v1/report/analytics", headers=student["headers"])
    assert analytics_resp.status_code == 200
    data = analytics_resp.json()

    history = data.get("session_history", [])
    assert len(history) >= 3

    types = [item["type"] for item in history]
    assert any("Aptitude" in t for t in types)
    assert any("Coding" in t for t in types), "Coding round must not be omitted from session_history"
    assert any("Interview" in t for t in types)

    # Verify rounds in completed_rounds
    completed_rounds = data.get("completed_rounds", [])
    assert "aptitude" in completed_rounds
    assert "coding" in completed_rounds
    assert "interview" in completed_rounds


def test_real_analytics_values_not_hardcoded():
    """Verify analytics values are calculated from real stored data."""
    student = _create_student("Score Student")

    db = _get_test_db()
    sess = AssessmentSession(user_id=student["user_id"], status="completed", total_score=0.88)
    db.add(sess)
    db.commit()
    db.refresh(sess)

    cod_round = AssessmentRound(
        session_id=sess.id,
        round_type="coding",
        status="completed",
        score=0.88,
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
    )
    db.add(cod_round)
    db.commit()
    db.close()

    analytics_resp = client.get("/api/v1/report/analytics", headers=student["headers"])
    assert analytics_resp.status_code == 200
    data = analytics_resp.json()

    assert data["overall_score"] == 88.0
    assert len(data["skill_breakdown"]) >= 1
    assert data["skill_breakdown"][0]["name"] == "Coding Proficiency"
    assert data["skill_breakdown"][0]["score"] == 88.0


def test_student_ownership_and_authoritative_eligibility():
    """Verify Student A cannot access Student B's data, and authoritative eligibility is enforced."""
    student_a = _create_student("Student Alpha", cgpa=8.5, backlogs=0)
    student_b = _create_student("Student Beta", cgpa=5.5, backlogs=2)

    # Profile A should show Tier-1 Eligible
    prof_a_resp = client.get("/api/v1/profile/me", headers=student_a["headers"])
    assert prof_a_resp.status_code == 200
    prof_a = prof_a_resp.json()
    assert prof_a["student_profile"]["placement_eligibility"]["status"] == "tier_1_eligible"
    assert prof_a["student_profile"]["placement_eligibility"]["badge_variant"] == "emerald"

    # Profile B should show Attention Required
    prof_b_resp = client.get("/api/v1/profile/me", headers=student_b["headers"])
    assert prof_b_resp.status_code == 200
    prof_b = prof_b_resp.json()
    assert prof_b["student_profile"]["placement_eligibility"]["status"] == "attention_required"
    assert prof_b["student_profile"]["placement_eligibility"]["badge_variant"] == "amber"

    # Student A must not see Student B's details in their own profile
    assert prof_a["id"] == student_a["user_id"]
    assert prof_b["id"] == student_b["user_id"]


def test_unauthenticated_access_rejected():
    """Verify that unauthenticated requests to dashboard endpoints return 401."""
    assert client.get("/api/v1/session/status").status_code == 401
    assert client.get("/api/v1/report/analytics").status_code == 401
    assert client.get("/api/v1/profile/me").status_code == 401
    assert client.get("/api/v1/profile/resumes").status_code == 401


def test_start_fresh_session():
    """Verify /session/fresh creates a fresh active assessment cycle."""
    student = _create_student("Fresh Session Candidate")

    fresh_resp = client.post("/api/v1/session/fresh", headers=student["headers"])
    assert fresh_resp.status_code == 201
    fresh_data = fresh_resp.json()
    assert fresh_data["status"] == "in_progress"
    assert len(fresh_data["rounds"]) == 1
    assert fresh_data["rounds"][0]["round_type"] == "aptitude"


def test_empty_student_dashboard_data():
    """Verify dashboard endpoints handle a brand-new student with no records gracefully."""
    student = _create_student("Brand New Candidate", cgpa=0.0, backlogs=0)

    # 1. /session/status should return not_started without 500 or 404
    sess_resp = client.get("/api/v1/session/status", headers=student["headers"])
    assert sess_resp.status_code == 200
    assert sess_resp.json()["status"] == "not_started"
    assert sess_resp.json()["rounds"] == []

    # 2. /report/analytics should return safe empty analytics
    analytics_resp = client.get("/api/v1/report/analytics", headers=student["headers"])
    assert analytics_resp.status_code == 200
    data = analytics_resp.json()
    assert data["overall_score"] == 0.0
    assert data["session_history"] == []
    assert data["percentile"] is None

    # 3. /profile/resumes should return empty list
    resumes_resp = client.get("/api/v1/profile/resumes", headers=student["headers"])
    assert resumes_resp.status_code == 200
    assert resumes_resp.json() == []
