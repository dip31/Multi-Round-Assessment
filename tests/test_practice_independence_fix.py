"""
Test Practice Mode Independence - EDI5 Fix Verification

Tests that Practice Mode is completely independent:
- Every practice round is independently selectable
- Every practice round is repeatable
- Completing one round does NOT force another round
- Session remains active across multiple practice rounds
- Practice types (mcq/technical/combined) are distinguished
"""

import pytest
from sqlalchemy.orm import Session
from datetime import datetime

from app.database.db import get_db
from app.models.user import User
from app.models.assessment import AssessmentSession, AssessmentRound
from app.services.auth_service import create_user
from app.main import app
from fastapi.testclient import TestClient


client = TestClient(app)


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def db() -> Session:
    """Provide database session."""
    db_gen = get_db()
    db_session = next(db_gen)
    try:
        yield db_session
    finally:
        db_session.close()


def _create_test_user(db: Session, email: str, name: str) -> User:
    """Helper to create a test user with unique email."""
    import time
    unique_email = f"{email.split('@')[0]}_{int(time.time() * 1000)}@{email.split('@')[1]}"
    return create_user(
        db=db,
        name=name,
        email=unique_email,
        password="password123",
        role="student",
    )


def _get_headers(email: str, password: str) -> dict:
    """Helper to login and get auth headers."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password}
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_mcq_repeat_same_type(db: Session):
    """Test: Complete MCQ → Start MCQ again → Success (same session, new round)"""
    user = _create_test_user(db, "mcq_repeat_user@test.com", "MCQ Repeat Test")
    headers = _get_headers(user.email, "password123")
    
    # Start MCQ practice #1
    resp1 = client.post(
        "/api/v1/practice/start",
        json={"round_type": "aptitude", "practice_type": "mcq"},
        headers=headers
    )
    assert resp1.status_code == 201
    data1 = resp1.json()
    session_id_1 = data1["session_id"]
    round_id_1 = data1["active_round"]["id"]
    assert data1["active_round"]["round_type"] == "aptitude"
    assert data1["active_round"]["practice_type"] == "mcq"
    
    # Complete MCQ #1
    complete_resp = client.post(
        "/api/v1/practice/complete-round",
        json={"round_id": round_id_1, "round_type": "aptitude"},
        headers=headers
    )
    assert complete_resp.status_code == 200
    complete_data = complete_resp.json()
    assert complete_data["session_completed"] == False  # Session should NOT be completed
    
    # Start MCQ practice #2 (should reuse same session)
    resp2 = client.post(
        "/api/v1/practice/start",
        json={"round_type": "aptitude", "practice_type": "mcq"},
        headers=headers
    )
    assert resp2.status_code == 201
    data2 = resp2.json()
    session_id_2 = data2["session_id"]
    round_id_2 = data2["active_round"]["id"]
    
    # CRITICAL: Should be same session, different round
    assert session_id_2 == session_id_1, "Should reuse same session for multiple practice rounds"
    assert round_id_2 != round_id_1, "Should create new round for repeat practice"
    assert data2["active_round"]["practice_type"] == "mcq"
    
    # Verify database state
    session = db.query(AssessmentSession).filter(AssessmentSession.id == session_id_1).first()
    assert session.status == "in_progress", "Session should remain in_progress"
    
    rounds = db.query(AssessmentRound).filter(AssessmentRound.session_id == session_id_1).all()
    assert len(rounds) == 2, "Should have 2 rounds in same session"
    assert rounds[0].status == "completed"
    assert rounds[1].status == "active"
    assert rounds[0].practice_type == "mcq"
    assert rounds[1].practice_type == "mcq"


def test_mcq_to_technical_mcq(db: Session):
    """Test: Complete MCQ → Start Technical MCQ → Success (same session)"""
    user = _create_test_user(db, "mcq_technical_user@test.com", "MCQ Technical Test")
    headers = _get_headers(user.email, "password123")
    
    # Start MCQ
    resp1 = client.post(
        "/api/v1/practice/start",
        json={"round_type": "aptitude", "practice_type": "mcq"},
        headers=headers
    )
    assert resp1.status_code == 201
    session_id = resp1.json()["session_id"]
    round_id_1 = resp1.json()["active_round"]["id"]
    
    # Complete MCQ
    client.post(
        "/api/v1/practice/complete-round",
        json={"round_id": round_id_1, "round_type": "aptitude"},
        headers=headers
    )
    
    # Start Technical MCQ
    resp2 = client.post(
        "/api/v1/practice/start",
        json={"round_type": "aptitude", "practice_type": "technical"},
        headers=headers
    )
    assert resp2.status_code == 201
    data2 = resp2.json()
    
    # Should be same session, new round with different practice_type
    assert data2["session_id"] == session_id
    assert data2["active_round"]["practice_type"] == "technical"
    assert data2["active_round"]["id"] != round_id_1
    
    # Verify history
    rounds = db.query(AssessmentRound).filter(AssessmentRound.session_id == session_id).all()
    assert len(rounds) == 2
    assert rounds[0].practice_type == "mcq"
    assert rounds[1].practice_type == "technical"


def test_mcq_to_combined_mcq(db: Session):
    """Test: Complete MCQ → Start Combined MCQ → Success"""
    user = _create_test_user(db, "mcq_combined_user@test.com", "MCQ Combined Test")
    headers = _get_headers(user.email, "password123")
    
    # Start MCQ
    resp1 = client.post(
        "/api/v1/practice/start",
        json={"round_type": "aptitude", "practice_type": "mcq"},
        headers=headers
    )
    session_id = resp1.json()["session_id"]
    round_id_1 = resp1.json()["active_round"]["id"]
    
    # Complete MCQ
    client.post(
        "/api/v1/practice/complete-round",
        json={"round_id": round_id_1, "round_type": "aptitude"},
        headers=headers
    )
    
    # Start Combined MCQ
    resp2 = client.post(
        "/api/v1/practice/start",
        json={"round_type": "aptitude", "practice_type": "combined"},
        headers=headers
    )
    assert resp2.status_code == 201
    assert resp2.json()["session_id"] == session_id
    assert resp2.json()["active_round"]["practice_type"] == "combined"


def test_mcq_to_coding(db: Session):
    """Test: Complete MCQ → Start Coding → Success"""
    user = _create_test_user(db, "mcq_coding_user@test.com", "MCQ Coding Test")
    headers = _get_headers(user.email, "password123")
    
    # Start MCQ
    resp1 = client.post(
        "/api/v1/practice/start",
        json={"round_type": "aptitude", "practice_type": "mcq"},
        headers=headers
    )
    session_id = resp1.json()["session_id"]
    round_id_1 = resp1.json()["active_round"]["id"]
    
    # Complete MCQ
    client.post(
        "/api/v1/practice/complete-round",
        json={"round_id": round_id_1, "round_type": "aptitude"},
        headers=headers
    )
    
    # Start Coding
    resp2 = client.post(
        "/api/v1/practice/start",
        json={"round_type": "coding", "practice_type": "coding"},
        headers=headers
    )
    assert resp2.status_code == 201
    assert resp2.json()["session_id"] == session_id
    assert resp2.json()["active_round"]["round_type"] == "coding"
    assert resp2.json()["active_round"]["practice_type"] == "coding"


def test_mcq_to_interview(db: Session):
    """Test: Complete MCQ → Start Interview → Success"""
    user = _create_test_user(db, "mcq_interview_user@test.com", "MCQ Interview Test")
    headers = _get_headers(user.email, "password123")
    
    # Start MCQ
    resp1 = client.post(
        "/api/v1/practice/start",
        json={"round_type": "aptitude", "practice_type": "mcq"},
        headers=headers
    )
    session_id = resp1.json()["session_id"]
    round_id_1 = resp1.json()["active_round"]["id"]
    
    # Complete MCQ
    client.post(
        "/api/v1/practice/complete-round",
        json={"round_id": round_id_1, "round_type": "aptitude"},
        headers=headers
    )
    
    # Start Interview
    resp2 = client.post(
        "/api/v1/practice/start",
        json={"round_type": "interview", "practice_type": "interview"},
        headers=headers
    )
    assert resp2.status_code == 201
    assert resp2.json()["session_id"] == session_id
    assert resp2.json()["active_round"]["round_type"] == "interview"


def test_coding_to_mcq(db: Session):
    """Test: Complete Coding → Start MCQ → Success"""
    user = _create_test_user(db, "coding_mcq_user@test.com", "Coding MCQ Test")
    headers = _get_headers(user.email, "password123")
    
    # Start Coding
    resp1 = client.post(
        "/api/v1/practice/start",
        json={"round_type": "coding", "practice_type": "coding"},
        headers=headers
    )
    session_id = resp1.json()["session_id"]
    round_id_1 = resp1.json()["active_round"]["id"]
    
    # Complete Coding
    client.post(
        "/api/v1/practice/complete-round",
        json={"round_id": round_id_1, "round_type": "coding"},
        headers=headers
    )
    
    # Start MCQ
    resp2 = client.post(
        "/api/v1/practice/start",
        json={"round_type": "aptitude", "practice_type": "mcq"},
        headers=headers
    )
    assert resp2.status_code == 201
    assert resp2.json()["session_id"] == session_id
    assert resp2.json()["active_round"]["round_type"] == "aptitude"
    assert resp2.json()["active_round"]["practice_type"] == "mcq"


def test_coding_repeat(db: Session):
    """Test: Complete Coding → Start Coding again → Success"""
    user = _create_test_user(db, "coding_repeat_user@test.com", "Coding Repeat Test")
    headers = _get_headers(user.email, "password123")
    
    # Start Coding #1
    resp1 = client.post(
        "/api/v1/practice/start",
        json={"round_type": "coding", "practice_type": "coding"},
        headers=headers
    )
    session_id = resp1.json()["session_id"]
    round_id_1 = resp1.json()["active_round"]["id"]
    
    # Complete Coding #1
    client.post(
        "/api/v1/practice/complete-round",
        json={"round_id": round_id_1, "round_type": "coding"},
        headers=headers
    )
    
    # Start Coding #2
    resp2 = client.post(
        "/api/v1/practice/start",
        json={"round_type": "coding", "practice_type": "coding"},
        headers=headers
    )
    assert resp2.status_code == 201
    assert resp2.json()["session_id"] == session_id
    assert resp2.json()["active_round"]["id"] != round_id_1
    
    # Verify 2 coding rounds in same session
    rounds = db.query(AssessmentRound).filter(AssessmentRound.session_id == session_id).all()
    assert len(rounds) == 2
    assert all(r.round_type == "coding" for r in rounds)


def test_interview_to_coding(db: Session):
    """Test: Complete Interview → Start Coding → Success"""
    user = _create_test_user(db, "interview_coding_user@test.com", "Interview Coding Test")
    headers = _get_headers(user.email, "password123")
    
    # Start Interview
    resp1 = client.post(
        "/api/v1/practice/start",
        json={"round_type": "interview", "practice_type": "interview"},
        headers=headers
    )
    session_id = resp1.json()["session_id"]
    round_id_1 = resp1.json()["active_round"]["id"]
    
    # Complete Interview
    client.post(
        "/api/v1/practice/complete-round",
        json={"round_id": round_id_1, "round_type": "interview"},
        headers=headers
    )
    
    # Start Coding
    resp2 = client.post(
        "/api/v1/practice/start",
        json={"round_type": "coding", "practice_type": "coding"},
        headers=headers
    )
    assert resp2.status_code == 201
    assert resp2.json()["session_id"] == session_id


def test_no_auto_progression_after_mcq_completion(db: Session):
    """Test: After completing MCQ, NO Coding round is automatically created"""
    user = _create_test_user(db, "no_auto_user@test.com", "No Auto Test")
    headers = _get_headers(user.email, "password123")
    
    # Start and complete MCQ
    resp1 = client.post(
        "/api/v1/practice/start",
        json={"round_type": "aptitude", "practice_type": "mcq"},
        headers=headers
    )
    session_id = resp1.json()["session_id"]
    round_id_1 = resp1.json()["active_round"]["id"]
    
    complete_resp = client.post(
        "/api/v1/practice/complete-round",
        json={"round_id": round_id_1, "round_type": "aptitude"},
        headers=headers
    )
    
    # Verify NO next round was created
    assert complete_resp.json()["next_round"] is None
    assert complete_resp.json()["session_completed"] == False
    
    # Verify only 1 round exists
    rounds = db.query(AssessmentRound).filter(AssessmentRound.session_id == session_id).all()
    assert len(rounds) == 1
    assert rounds[0].round_type == "aptitude"
    assert rounds[0].status == "completed"


def test_history_preserves_all_attempts(db: Session):
    """Test: Multiple practice rounds are preserved in history"""
    user = _create_test_user(db, "history_user@test.com", "History Test")
    headers = _get_headers(user.email, "password123")
    
    # Do multiple practice rounds
    practice_sequence = [
        ("aptitude", "mcq"),
        ("aptitude", "technical"),
        ("aptitude", "combined"),
        ("coding", "coding"),
        ("interview", "interview"),
    ]
    
    for round_type, practice_type in practice_sequence:
        start_resp = client.post(
            "/api/v1/practice/start",
            json={"round_type": round_type, "practice_type": practice_type},
            headers=headers
        )
        round_id = start_resp.json()["active_round"]["id"]
        
        # Complete it
        client.post(
            "/api/v1/practice/complete-round",
            json={"round_id": round_id, "round_type": round_type},
            headers=headers
        )
    
    # Verify history
    history_resp = client.get("/api/v1/practice/history", headers=headers)
    assert history_resp.status_code == 200
    history = history_resp.json()
    
    assert len(history) == 1, "Should be 1 session"
    assert len(history[0]["rounds"]) == 5, "Should have 5 rounds in same session"
    
    # Verify practice types are preserved
    practice_types = [r["round_type"] for r in history[0]["rounds"]]
    assert "aptitude" in practice_types
    assert "coding" in practice_types
    assert "interview" in practice_types


def test_practice_uses_independent_policy(db: Session):
    """Test: Practice context uses independent progression policy"""
    from app.services.assessment_context_service import (
        get_or_create_practice_context,
        get_progression_mode
    )
    
    user = _create_test_user(db, "policy_user@test.com", "Policy Test")
    context = get_or_create_practice_context(db, user.id)
    
    assert get_progression_mode(context) == "independent"
    assert context.policy.progression_mode == "independent"
    assert context.mode == "practice"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
