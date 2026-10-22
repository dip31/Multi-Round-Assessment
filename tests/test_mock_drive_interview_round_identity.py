"""Regression tests: technical vs HR interview rounds must stay distinct.

Both interview rounds are persisted with ``AssessmentRound.round_type ==
"interview"`` because of the DB CHECK constraint, so they were previously
indistinguishable after a reload. ``_completed_rounds_for_context`` marked
every enabled interview key complete as soon as one interview finished, and
``get_mock_drive_status`` reported the first enabled interview key as the
active round. The reload therefore skipped the HR interview / finalised the
drive early.

The fix persists the canonical MockDrive round key in the existing
``AssessmentRound.practice_type`` column (no schema change) and prefers it in
every reverse lookup, with the legacy ``round_type`` reverse map as fallback.

These tests run entirely on an in-memory SQLite database (isolated from the
development PostgreSQL database).
"""

import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles

from app.database.db import get_db
from app.database.base import Base
from app.main import app as application
from app.models.user import User
from app.models.profile import StudentProfile
from app.models.company_data import CompanyBlueprint
from app.models.assessment_context import AssessmentPolicy
from app.models.assessment import AssessmentRound
from app.models.question_pool_generation import (
    GeneratedQuestionPool,
    POOL_STATUS_COMPLETE,
)
from app.middleware.rate_limit import RateLimitMiddleware
from app.config.security import create_access_token
from app.services.mock_drive_service import (
    _apply_round_key,
    _mock_round_key_for_round,
)
from app.services.assessment_context_service import DEFAULT_PRACTICE_POLICY_ID


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


TestingSessionLocal = sessionmaker(bind=engine)


@pytest.fixture(scope="module", autouse=True)
def _setup_schema():
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    if db.query(AssessmentPolicy).filter(
        AssessmentPolicy.id == DEFAULT_PRACTICE_POLICY_ID
    ).first() is None:
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


@pytest.fixture
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()
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
    with TestClient(application) as test_client:
        yield test_client
    application.dependency_overrides.clear()


def _clear_rate_limiter():
    stack = application.middleware_stack or application.build_middleware_stack()
    application.middleware_stack = stack
    current = stack
    while current is not None and not isinstance(current, RateLimitMiddleware):
        current = getattr(current, "app", None)
    if current is not None:
        current._requests.clear()


def _seed_generated_pool(db_session, blueprint_id, version, round_type, phase, count=3):
    """Insert a COMPLETE GeneratedQuestionPool row for the given blueprint/version/round."""
    content = [
        {
            "id": f"{round_type}-{i}",
            "question": f"{phase} question {i}",
            "phase": phase,
            "difficulty": "MEDIUM",
            "blueprint_pool": True,
        }
        for i in range(count)
    ]
    row = GeneratedQuestionPool(
        blueprint_id=blueprint_id,
        blueprint_version=version,
        company_name="Two Interviews Inc",
        target_role="Software Engineer",
        round_type=round_type,
        status=POOL_STATUS_COMPLETE,
        content=content,
        required_count=count,
        validated_count=count,
    )
    db_session.add(row)
    db_session.commit()
    return row


@pytest.fixture
def tpo(db_session):
    user = User(
        name="Identity TPO",
        email=f"tpo_id_{uuid.uuid4().hex[:6]}@college.edu",
        role="tpo",
        password_hash="pw",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def student(db_session):
    user = User(
        name="Identity Student",
        email=f"student_id_{uuid.uuid4().hex[:6]}@college.edu",
        role="student",
        password_hash="pw",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    db_session.add(
        StudentProfile(
            user_id=user.id,
            cgpa=8.5,
            backlogs_count=0,
            department="Computer Science",
        )
    )
    db_session.commit()
    return user


@pytest.fixture
def interview_blueprint(db_session, tpo):
    blueprint = CompanyBlueprint(
        company_name="Two Interviews Inc",
        target_role="Software Engineer",
        status="approved",
        version=1,
        blueprint_data={
            "company_name": "Two Interviews Inc",
            "target_role": "Software Engineer",
            "status": "approved",
            "version": 1,
            "rounds": [
                {
                    "round_type": "technical_interview",
                    "round_order": 1,
                    "round_name": "Technical Interview",
                    "question_count": 3,
                    "time_limit_minutes": 25,
                },
                {
                    "round_type": "hr_interview",
                    "round_order": 2,
                    "round_name": "HR Interview",
                    "question_count": 3,
                    "time_limit_minutes": 15,
                },
            ],
        },
        confidence_level="high",
        evidence_sources_count=3,
        created_by_id=tpo.id,
    )
    db_session.add(blueprint)
    db_session.commit()
    db_session.refresh(blueprint)
    return blueprint


def _headers(user):
    token = create_access_token(data={"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


def test_two_interview_rounds_stay_distinct_across_reload(
    client, db_session, tpo, student, interview_blueprint
):
    """Reproduces the reload failure: finishing the technical interview must
    not mark HR complete nor report the technical round as current on reload."""
    _clear_rate_limiter()
    tpo_headers = _headers(tpo)
    student_headers = _headers(student)

    created = client.post(
        "/api/v1/tpo/mock-drives",
        json={
            "company_name": "Two Interviews Inc",
            "target_role": "Software Engineer",
            "minimum_cgpa": 6.0,
            "maximum_backlogs": 0,
            "eligible_branches": ["Computer Science"],
            "selected_rounds": {"technical_interview": True, "hr_interview": True},
            "blueprint_id": interview_blueprint.id,
        },
        headers=tpo_headers,
    )
    assert created.status_code == 201, created.text
    drive_id = created.json()["id"]

    # Seed required pre-generated pools for enabled blueprint rounds
    _seed_generated_pool(db_session, interview_blueprint.id, 1, "technical_interview", "TECHNICAL")
    _seed_generated_pool(db_session, interview_blueprint.id, 1, "hr_interview", "HR")

    published = client.post(
        f"/api/v1/tpo/mock-drives/{drive_id}/publish", headers=tpo_headers
    )
    assert published.status_code == 200, published.text

    started = client.post(f"/api/v1/mock-drives/{drive_id}/start", headers=student_headers)
    assert started.status_code == 200, started.text
    assert started.json()["current_round"] == "technical_interview"

    # The active round persists its canonical key (not just round_type).
    session_id = started.json()["session_id"]
    active = (
        db_session.query(AssessmentRound)
        .filter_by(session_id=session_id, status="active")
        .one()
    )
    assert active.round_type == "interview"
    assert active.practice_type == "technical_interview"

    # Completing the technical interview activates the HR interview.
    advanced = client.post(f"/api/v1/mock-drives/{drive_id}/advance", headers=student_headers)
    assert advanced.status_code == 200, advanced.text
    adv = advanced.json()
    assert adv["status"] == "in_progress"
    assert adv["current_round"] == "hr_interview"
    assert adv["redirect_url"] == "/interview"
    assert adv["completed_rounds"] == ["technical_interview"]

    hr_round = (
        db_session.query(AssessmentRound)
        .filter_by(session_id=session_id, status="active")
        .one()
    )
    assert adv["completed_rounds"] is not None
    assert hr_round.round_type == "interview"
    assert hr_round.practice_type == "hr_interview"

    # Reload (status poll): HR must still be the current, uncompleted round.
    reloaded = client.get(f"/api/v1/mock-drives/{drive_id}/status", headers=student_headers)
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["status"] == "in_progress"
    assert reloaded.json()["current_round"] == "hr_interview"
    assert reloaded.json()["completed_rounds"] == ["technical_interview"]
    assert "hr_interview" not in reloaded.json()["completed_rounds"]

    # Completing the HR interview finalises the drive.
    final = client.post(f"/api/v1/mock-drives/{drive_id}/advance", headers=student_headers)
    assert final.status_code == 200, final.text
    assert final.json()["status"] == "completed"
    assert set(final.json()["completed_rounds"]) == {
        "technical_interview",
        "hr_interview",
    }


def test_interview_round_durations_follow_blueprint_config(
    client, db_session, tpo, student, interview_blueprint
):
    """Each Mock Drive interview round must use its OWN configured duration.

    Regression: both interview rounds persist ``round_type="interview"``, so the
    duration resolver previously resolved the blueprint config by round_type and
    picked the first same-type entry (technical = 25 min) for the HR round too.
    The canonical round key must disambiguate so HR gets its own 15 minutes, and
    the interview start response must expose that server deadline.
    """
    _clear_rate_limiter()
    tpo_headers = _headers(tpo)
    student_headers = _headers(student)

    created = client.post(
        "/api/v1/tpo/mock-drives",
        json={
            "company_name": "Two Interviews Inc",
            "target_role": "Software Engineer",
            "minimum_cgpa": 6.0,
            "maximum_backlogs": 0,
            "eligible_branches": ["Computer Science"],
            "selected_rounds": {"technical_interview": True, "hr_interview": True},
            "blueprint_id": interview_blueprint.id,
        },
        headers=tpo_headers,
    )
    assert created.status_code == 201, created.text
    drive_id = created.json()["id"]

    _seed_generated_pool(db_session, interview_blueprint.id, 1, "technical_interview", "TECHNICAL")
    _seed_generated_pool(db_session, interview_blueprint.id, 1, "hr_interview", "HR")

    published = client.post(
        f"/api/v1/tpo/mock-drives/{drive_id}/publish", headers=tpo_headers
    )
    assert published.status_code == 200, published.text

    started = client.post(f"/api/v1/mock-drives/{drive_id}/start", headers=student_headers)
    assert started.status_code == 200, started.text
    session_id = started.json()["session_id"]

    tech = (
        db_session.query(AssessmentRound)
        .filter_by(session_id=session_id, status="active")
        .one()
    )
    assert tech.practice_type == "technical_interview"
    assert tech.expires_at is not None and tech.started_at is not None
    assert round((tech.expires_at - tech.started_at).total_seconds() / 60, 3) == 25.0

    advanced = client.post(f"/api/v1/mock-drives/{drive_id}/advance", headers=student_headers)
    assert advanced.status_code == 200, advanced.text
    assert advanced.json()["current_round"] == "hr_interview"

    hr = (
        db_session.query(AssessmentRound)
        .filter_by(session_id=session_id, status="active")
        .one()
    )
    assert hr.practice_type == "hr_interview"
    assert hr.expires_at is not None and hr.started_at is not None
    assert round((hr.expires_at - hr.started_at).total_seconds() / 60, 3) == 15.0

    # The interview start response must expose the server-side deadline so the
    # UI renders the same remaining time on refresh/resume.
    started_interview = client.post(
        "/api/v1/interview/session/start-active", headers=student_headers
    )
    assert started_interview.status_code == 200, started_interview.text
    body = started_interview.json()
    assert body["round_expires_at"] is not None
    assert body["session_expires_at"] is not None
    assert round(
        (
            datetime.fromisoformat(body["round_expires_at"]) - hr.started_at
        ).total_seconds() / 60,
        3,
    ) == 15.0


def test_canonical_key_preferred_and_legacy_fallback():
    """Unit-level: the persisted key wins; legacy NULL rows use round_type."""
    enabled = ["technical_interview", "hr_interview"]

    legacy = SimpleNamespace(round_type="interview", practice_type=None)
    assert _mock_round_key_for_round(legacy, enabled) == "technical_interview"

    canonical = SimpleNamespace(round_type="interview", practice_type="hr_interview")
    assert _mock_round_key_for_round(canonical, enabled) == "hr_interview"

    # A stored key outside the enabled set must not leak through.
    stale = SimpleNamespace(round_type="interview", practice_type="aptitude")
    assert _mock_round_key_for_round(stale, enabled) == "technical_interview"

    _apply_round_key(canonical, "hr_interview")
    assert canonical.practice_type == "hr_interview"
