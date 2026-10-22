"""Tests for the derived Mock Drive candidate roster + TPO result access (G4).

The roster is derived from authoritative AssessmentContext/Session/Round
records. These tests assert:

  * participants + counts come from persisted contexts, not duplicate state;
  * per-round status/score reflects the persisted round;
  * the roster is scoped to its own drive (cross-drive isolation);
  * RBAC: students and unauthenticated callers are rejected;
  * staff can read one candidate's consolidated result, and non-participants
    return 404.

HTTP-level, in-memory SQLite (never the live dev database), mirroring
tests/test_mock_drive_security_isolation.py.
"""

import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.db import get_db
from app.database.base import Base
from app.main import app as application
from app.middleware.rate_limit import RateLimitMiddleware
from app.config.security import create_access_token
from app.models.user import User
from app.models.profile import StudentProfile
from app.models.mock_drive import MockDrive
from app.models.assessment_context import AssessmentPolicy, AssessmentContext
from app.models.assessment import AssessmentSession, AssessmentRound
from app.services.assessment_context_service import DEFAULT_PRACTICE_POLICY_ID


# ── SQLite JSONB shim ─────────────────────────────────────────────────
@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "TEXT"


engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    if not db.query(AssessmentPolicy).filter(
        AssessmentPolicy.id == DEFAULT_PRACTICE_POLICY_ID
    ).first():
        db.add(
            AssessmentPolicy(
                id=DEFAULT_PRACTICE_POLICY_ID,
                name="Default Practice Policy",
                session_duration_minutes=180,
                round_duration_minutes=30,
                resume_allowed=True,
                exit_allowed=True,
                progression_mode="sequential",
                progression_config={"rounds": ["aptitude", "coding", "interview"]},
            )
        )
        db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)


def _reset_rate_limit() -> None:
    middleware = application.middleware_stack or application.build_middleware_stack()
    application.middleware_stack = middleware
    current = middleware
    while current is not None and not isinstance(current, RateLimitMiddleware):
        current = getattr(current, "app", None)
    if current is not None:
        current._requests.clear()


@pytest.fixture
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    application.dependency_overrides[get_db] = override_get_db
    _reset_rate_limit()
    with TestClient(application) as test_client:
        yield test_client
    application.dependency_overrides.clear()


def _make_user(db_session, role: str, *, cgpa: float = 8.5):
    user = User(
        name=f"{role.title()} {uuid.uuid4().hex[:6]}",
        email=f"{role}_{uuid.uuid4().hex[:8]}@college.edu",
        role=role,
        password_hash="pw",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    if role == "student":
        db_session.add(
            StudentProfile(user_id=user.id, cgpa=cgpa, backlogs_count=0)
        )
        db_session.commit()
    return user


def _auth(user: User) -> dict:
    token = create_access_token(data={"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


def _published_coding_drive(client, tpo_headers, *, name="Roster Co"):
    resp = client.post(
        "/api/v1/tpo/mock-drives",
        json={
            "company_name": name,
            "target_role": "Software Engineer",
            "minimum_cgpa": 0.0,
            "maximum_backlogs": 100,
            "selected_rounds": {"coding": True},
        },
        headers=tpo_headers,
    )
    assert resp.status_code == 201, resp.text
    drive_id = resp.json()["id"]
    pub = client.post(
        f"/api/v1/tpo/mock-drives/{drive_id}/publish", headers=tpo_headers
    )
    assert pub.status_code == 200, pub.text
    return drive_id


def _entry(roster: dict, candidate_id: int) -> dict:
    matches = [c for c in roster["candidates"] if c["candidate_id"] == candidate_id]
    assert matches, f"candidate {candidate_id} not present in roster"
    return matches[0]


# ══════════════════════════════════════════════════════════════════════
# Derivation + counts
# ══════════════════════════════════════════════════════════════════════


def test_roster_derives_participants_and_counts_from_contexts(client, db_session):
    tpo = _make_user(db_session, "tpo")
    student_a = _make_user(db_session, "student")
    student_b = _make_user(db_session, "student")
    tpo_headers = _auth(tpo)

    drive_id = _published_coding_drive(client, tpo_headers)

    # A starts but does not finish; B starts and completes the single round.
    assert (
        client.post(
            f"/api/v1/mock-drives/{drive_id}/start", headers=_auth(student_a)
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/mock-drives/{drive_id}/start", headers=_auth(student_b)
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/mock-drives/{drive_id}/advance", headers=_auth(student_b)
        ).status_code
        == 200
    )

    roster = client.get(
        f"/api/v1/tpo/mock-drives/{drive_id}/roster", headers=tpo_headers
    )
    assert roster.status_code == 200, roster.text
    body = roster.json()

    assert body["mock_drive_id"] == drive_id
    assert body["enabled_rounds"] == ["coding"]
    assert body["total_participants"] == 2
    assert body["in_progress_count"] == 1
    assert body["completed_count"] == 1

    a = _entry(body, student_a.id)
    assert a["context_status"] == "active"
    assert a["name"] == student_a.name
    assert a["email"] == student_a.email
    assert a["rounds"][0]["round"] == "coding"
    assert a["rounds"][0]["status"] == "active"

    b = _entry(body, student_b.id)
    assert b["context_status"] == "completed"
    assert b["rounds"][0]["status"] == "completed"
    assert b["rounds"][0]["max_score"] == 100.0
    assert b["overall_score"] is not None


def test_roster_exposes_expired_rounds_and_mapping_status(client, db_session):
    tpo = _make_user(db_session, "tpo")
    student = _make_user(db_session, "student")
    tpo_headers = _auth(tpo)
    drive_id = _published_coding_drive(client, tpo_headers, name="Expired Co")

    drive = db_session.query(MockDrive).get(drive_id)
    ctx = AssessmentContext(
        mode="mock_drive",
        purpose="mock_drive",
        student_id=student.id,
        company_name=drive.company_name,
        target_role=drive.target_role,
        policy_id=DEFAULT_PRACTICE_POLICY_ID,
        mock_drive_id=drive_id,
        blueprint_snapshot={},
        status="active",
        competency_mapping_status="pending",
    )
    db_session.add(ctx)
    db_session.flush()
    session = AssessmentSession(
        user_id=student.id,
        context_id=ctx.id,
        status="in_progress",
        started_at=datetime.utcnow(),
    )
    db_session.add(session)
    db_session.flush()
    db_session.add(
        AssessmentRound(
            session_id=session.id,
            round_type="coding",
            practice_type="coding",
            status="expired",
            score=0.0,
            completed_at=datetime.utcnow(),
        )
    )
    db_session.commit()

    roster = client.get(
        f"/api/v1/tpo/mock-drives/{drive_id}/roster", headers=tpo_headers
    ).json()

    entry = _entry(roster, student.id)
    assert entry["competency_mapping_status"] == "pending"
    assert entry["rounds"][0]["status"] == "expired"
    assert entry["rounds"][0]["deadline_passed"] is True
    assert entry["rounds"][0]["max_score"] == 100.0


def test_roster_marks_active_round_past_deadline(client, db_session):
    tpo = _make_user(db_session, "tpo")
    student = _make_user(db_session, "student")
    drive_id = _published_coding_drive(client, _auth(tpo), name="Overdue Co")
    drive = db_session.query(MockDrive).get(drive_id)
    context = AssessmentContext(
        mode="mock_drive",
        purpose="mock_drive",
        student_id=student.id,
        company_name=drive.company_name,
        target_role=drive.target_role,
        policy_id=DEFAULT_PRACTICE_POLICY_ID,
        mock_drive_id=drive_id,
        blueprint_snapshot={},
        status="active",
    )
    db_session.add(context)
    db_session.flush()
    session = AssessmentSession(
        user_id=student.id,
        context_id=context.id,
        status="in_progress",
        started_at=datetime.utcnow(),
    )
    db_session.add(session)
    db_session.flush()
    db_session.add(AssessmentRound(
        session_id=session.id,
        round_type="coding",
        practice_type="coding",
        status="active",
        expires_at=datetime.utcnow() - timedelta(seconds=1),
    ))
    db_session.commit()

    roster = client.get(
        f"/api/v1/tpo/mock-drives/{drive_id}/roster", headers=_auth(tpo)
    ).json()
    round_data = _entry(roster, student.id)["rounds"][0]
    assert round_data["status"] == "active"
    assert round_data["deadline_passed"] is True


def test_cohort_students_expose_current_session_time_remaining(client, db_session):
    tpo = _make_user(db_session, "tpo")
    student = _make_user(db_session, "student")
    session = AssessmentSession(
        user_id=student.id,
        status="in_progress",
        started_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(minutes=1),
    )
    db_session.add(session)
    db_session.commit()

    response = client.get("/api/v1/profile/cohort/students", headers=_auth(tpo))
    assert response.status_code == 200
    student_data = next(row for row in response.json()["students"] if row["user_id"] == student.id)
    assert student_data["session_status"] == "in_progress"
    assert student_data["session_time_remaining_seconds"] > 0

    session.expires_at = datetime.utcnow() - timedelta(seconds=1)
    db_session.commit()
    response = client.get("/api/v1/profile/cohort/students", headers=_auth(tpo))
    student_data = next(row for row in response.json()["students"] if row["user_id"] == student.id)
    assert student_data["session_time_remaining_seconds"] == 0


# ══════════════════════════════════════════════════════════════════════
# Authorization + isolation
# ══════════════════════════════════════════════════════════════════════


def test_roster_requires_staff(client, db_session):
    tpo = _make_user(db_session, "tpo")
    student = _make_user(db_session, "student")
    drive_id = _published_coding_drive(client, _auth(tpo), name="RBAC Co")

    # Student is forbidden, and must learn nothing about the roster.
    forbidden = client.get(
        f"/api/v1/tpo/mock-drives/{drive_id}/roster", headers=_auth(student)
    )
    assert forbidden.status_code == 403

    # Unauthenticated is 401.
    assert (
        client.get(f"/api/v1/tpo/mock-drives/{drive_id}/roster").status_code == 401
    )


def test_roster_is_scoped_to_its_own_drive(client, db_session):
    tpo = _make_user(db_session, "tpo")
    student = _make_user(db_session, "student")
    tpo_headers = _auth(tpo)

    drive_one = _published_coding_drive(client, tpo_headers, name="Scoped One")
    drive_two = _published_coding_drive(client, tpo_headers, name="Scoped Two")

    # Only drive_one has a participant.
    assert (
        client.post(
            f"/api/v1/mock-drives/{drive_one}/start", headers=_auth(student)
        ).status_code
        == 200
    )

    one = client.get(
        f"/api/v1/tpo/mock-drives/{drive_one}/roster", headers=tpo_headers
    ).json()
    two = client.get(
        f"/api/v1/tpo/mock-drives/{drive_two}/roster", headers=tpo_headers
    ).json()

    assert one["total_participants"] == 1
    assert two["total_participants"] == 0
    assert two["candidates"] == []


# ══════════════════════════════════════════════════════════════════════
# TPO result access (separated from candidate access)
# ══════════════════════════════════════════════════════════════════════


def test_staff_can_read_participant_result_and_non_participant_is_404(
    client, db_session
):
    tpo = _make_user(db_session, "tpo")
    student = _make_user(db_session, "student")
    stranger = _make_user(db_session, "student")
    tpo_headers = _auth(tpo)

    drive_id = _published_coding_drive(client, tpo_headers, name="Result Access Co")
    assert (
        client.post(
            f"/api/v1/mock-drives/{drive_id}/start", headers=_auth(student)
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/mock-drives/{drive_id}/advance", headers=_auth(student)
        ).status_code
        == 200
    )

    result = client.get(
        f"/api/v1/tpo/mock-drives/{drive_id}/candidates/{student.id}/result",
        headers=tpo_headers,
    )
    assert result.status_code == 200, result.text
    assert result.json()["candidate_id"] == student.id
    assert result.json()["status"] == "completed"

    # A candidate who never attempted the drive has no result.
    missing = client.get(
        f"/api/v1/tpo/mock-drives/{drive_id}/candidates/{stranger.id}/result",
        headers=tpo_headers,
    )
    assert missing.status_code == 404

    # Students cannot use the staff result route (access stays separated).
    assert (
        client.get(
            f"/api/v1/tpo/mock-drives/{drive_id}/candidates/{student.id}/result",
            headers=_auth(student),
        ).status_code
        == 403
    )


def test_candidate_cannot_read_another_candidates_status(client, db_session):
    tpo = _make_user(db_session, "tpo")
    student_a = _make_user(db_session, "student")
    student_b = _make_user(db_session, "student")
    drive_id = _published_coding_drive(client, _auth(tpo), name="Status Isolation Co")

    assert (
        client.post(
            f"/api/v1/mock-drives/{drive_id}/start", headers=_auth(student_a)
        ).status_code
        == 200
    )

    # B has no attempt: the student status route reports not_started for B, and
    # A's own attempt is unaffected.
    b_status = client.get(
        f"/api/v1/mock-drives/{drive_id}/status", headers=_auth(student_b)
    )
    assert b_status.status_code == 200
    assert b_status.json()["status"] == "not_started"

    a_status = client.get(
        f"/api/v1/mock-drives/{drive_id}/status", headers=_auth(student_a)
    )
    assert a_status.json()["status"] == "in_progress"
