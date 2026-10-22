"""
Test Practice Mode Independence - EDI5 Fix Verification

Tests that Practice Mode is completely independent:
- Every practice round is independently selectable
- Every practice round is repeatable
- Completing one round does NOT force another round
- Each completed practice attempt finalizes its own session/context
- A subsequent attempt starts a fresh independent session
- Practice types (mcq/technical/combined) are distinguished
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.db import get_db
from app.models.assessment_context import AssessmentContext, AssessmentPolicy
from app.models.user import User
from app.models.assessment import AssessmentSession, AssessmentRound
from app.services.auth_service import create_user
from app.services.assessment_context_service import DEFAULT_PRACTICE_POLICY_ID
from app.main import app
from fastapi.testclient import TestClient


client = TestClient(app)


# ── Isolated in-memory SQLite (never the development database) ────────

@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "TEXT"


engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="module", autouse=True)
def _setup_db():
    """Create the schema and seed the default practice policy."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    if not db.query(AssessmentPolicy).filter(
        AssessmentPolicy.id == DEFAULT_PRACTICE_POLICY_ID
    ).first():
        db.add(
            AssessmentPolicy(
                id=DEFAULT_PRACTICE_POLICY_ID,
                name="Practice Policy",
                session_duration_minutes=180,
                round_duration_minutes=30,
                resume_allowed=True,
                exit_allowed=True,
                progression_mode="independent",
                progression_config={},
            )
        )
        db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db() -> Session:
    """Provide an isolated database session shared with the HTTP client."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _override_get_db(db: Session):
    """Bind the app's ``get_db`` dependency to the isolated session."""
    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    yield
    app.dependency_overrides.pop(get_db, None)


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
    """Test: Complete MCQ → Start MCQ again → new independent session."""
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

    # Complete MCQ #1 (independent practice finalizes its session)
    complete_resp = client.post(
        "/api/v1/practice/complete-round",
        json={"round_id": round_id_1, "round_type": "aptitude"},
        headers=headers
    )
    assert complete_resp.status_code == 200
    complete_data = complete_resp.json()
    assert complete_data["session_completed"] is True
    assert complete_data["next_round"] is None

    # Start MCQ practice #2 (a new independent attempt → new session)
    resp2 = client.post(
        "/api/v1/practice/start",
        json={"round_type": "aptitude", "practice_type": "mcq"},
        headers=headers
    )
    assert resp2.status_code == 201
    data2 = resp2.json()
    session_id_2 = data2["session_id"]
    round_id_2 = data2["active_round"]["id"]

    # CRITICAL: each independent attempt owns its own session and round
    assert session_id_2 != session_id_1, "Each practice attempt should create a new session"
    assert round_id_2 != round_id_1, "Should create new round for repeat practice"
    assert data2["active_round"]["practice_type"] == "mcq"

    # Verify the first session was finalized with a single completed round
    session = db.query(AssessmentSession).filter(AssessmentSession.id == session_id_1).first()
    assert session.status == "completed", "Session should be completed after its practice round completes"

    rounds = db.query(AssessmentRound).filter(AssessmentRound.session_id == session_id_1).all()
    assert len(rounds) == 1, "Each independent attempt owns exactly one round"
    assert rounds[0].status == "completed"
    assert rounds[0].practice_type == "mcq"


def test_mcq_to_technical_mcq(db: Session):
    """Test: Complete MCQ → Start Technical MCQ → new independent session."""
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

    # New independent attempt → new session with different practice_type
    assert data2["session_id"] != session_id
    assert data2["active_round"]["practice_type"] == "technical"
    assert data2["active_round"]["id"] != round_id_1


def test_mcq_to_combined_mcq(db: Session):
    """Test: Complete MCQ → Start Combined MCQ → new independent session."""
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
    assert resp2.json()["session_id"] != session_id
    assert resp2.json()["active_round"]["practice_type"] == "combined"


def test_mcq_to_coding(db: Session):
    """Test: Complete MCQ → Start Coding → new independent session."""
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
    assert resp2.json()["session_id"] != session_id
    assert resp2.json()["active_round"]["practice_type"] == "coding"


def test_mcq_to_interview(db: Session):
    """Test: Complete MCQ → Start Interview → new independent session."""
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
    assert resp2.json()["session_id"] != session_id
    assert resp2.json()["active_round"]["practice_type"] == "interview"


def test_coding_to_mcq(db: Session):
    """Test: Complete Coding → Start MCQ → new independent session."""
    user = _create_test_user(db, "mcq_coding_user@test.com", "MCQ Coding Test")
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
    assert resp2.json()["session_id"] != session_id
    assert resp2.json()["active_round"]["round_type"] == "aptitude"


def test_coding_repeat(db: Session):
    """Test: Complete Coding → Start Coding → new independent session."""
    user = _create_test_user(db, "mcq_coding_user@test.com", "MCQ Coding Test")
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
    assert resp2.json()["session_id"] != session_id
    assert resp2.json()["active_round"]["id"] != round_id_1


def test_interview_to_coding(db: Session):
    """Test: Complete Interview → Start Coding → new independent session."""
    user = _create_test_user(db, "mcq_interview_user@test.com", "MCQ Interview Test")
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
    assert resp2.json()["session_id"] != session_id


def test_no_auto_progression_after_mcq_completion(db: Session):
    """Test: Completing an independent practice round creates no next round."""
    user = _create_test_user(db, "history_user@test.com", "History Test")
    headers = _get_headers(user.email, "password123")

    # Start MCQ
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

    # No next round is created; the independent session is finalized.
    assert complete_resp.json()["next_round"] is None
    assert complete_resp.json()["session_completed"] is True

    # Verify only 1 round exists
    rounds = db.query(AssessmentRound).filter(AssessmentRound.session_id == session_id).all()
    assert len(rounds) == 1
    assert rounds[0].round_type == "aptitude"
    assert rounds[0].status == "completed"


def test_history_preserves_all_attempts(db: Session):
    """Test: Every independent practice attempt is preserved as its own session."""
    user = _create_test_user(db, "history_user@test.com", "History Test")
    headers = _get_headers(user.email, "password123")

    # Do multiple independent practice rounds
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

        # Complete it (finalizes that independent attempt's session)
        client.post(
            "/api/v1/practice/complete-round",
            json={"round_id": round_id, "round_type": round_type},
            headers=headers
        )

    # Verify history: one session per independent attempt, each with one round
    history_resp = client.get("/api/v1/practice/history", headers=headers)
    assert history_resp.status_code == 200
    history = history_resp.json()

    assert len(history) == 5, "Each independent attempt is its own session"
    assert all(len(session["rounds"]) == 1 for session in history)

    # Verify practice types are preserved across attempts
    round_types = [session["rounds"][0]["round_type"] for session in history]
    assert "aptitude" in round_types
    assert "coding" in round_types
    assert "interview" in round_types


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
