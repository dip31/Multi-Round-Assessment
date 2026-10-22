"""Regression tests for the Mock Drive interview-session bootstrap.

The Mock Drive interview round navigates straight to ``/interview`` (see
``ROUND_ROUTES``) without a ``pool_id`` and without guaranteeing a
``localStorage.interview_id``. The ``/interview`` page only read that global
key, so starting/advancing/refreshing a Mock Drive interview failed with
"Interview session not found" (or loaded a stale interview from a previous
attempt).

The fix adds an idempotent ``POST /interview/session/start-active`` that
resolves the caller's active interview round, guarantees an approved pool exists
for it (cloning the pre-generated blueprint pool — no candidate-time LLM call),
and returns the existing active interview session instead of creating a second
one.

Runs entirely on an in-memory SQLite database (isolated from the development
PostgreSQL database).
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.db import get_db
from app.database.base import Base
from app.main import app as application
from app.middleware.rate_limit import RateLimitMiddleware
from app.models.assessment_context import AssessmentPolicy
from app.models.company_data import CompanyBlueprint
from app.models.interview import ApprovedQuestionPool
from app.models.profile import StudentProfile
from app.models.question_pool_generation import (
    GeneratedQuestionPool,
    POOL_STATUS_COMPLETE,
)
from app.models.user import User
from app.config.security import create_access_token
from app.services.assessment_context_service import DEFAULT_PRACTICE_POLICY_ID


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "TEXT"


engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@pytest.fixture(scope="module", autouse=True)
def _schema():
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add(
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
    session.commit()
    session.close()
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


def _headers(user):
    token = create_access_token(data={"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


def _make_user(db, role, prefix):
    user = User(
        name=prefix,
        email=f"{prefix}_{uuid.uuid4().hex[:6]}@college.edu",
        role=role,
        password_hash="pw",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_student(db, prefix):
    user = _make_user(db, "student", prefix)
    db.add(
        StudentProfile(
            user_id=user.id,
            cgpa=8.5,
            backlogs_count=0,
            department="Computer Science",
        )
    )
    db.commit()
    return user


@pytest.fixture
def tpo(db_session):
    return _make_user(db_session, "tpo", "Bootstrap TPO")


@pytest.fixture
def student(db_session):
    return _make_student(db_session, "Bootstrap Student")


@pytest.fixture
def blueprint(db_session, tpo):
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
                },
                {
                    "round_type": "hr_interview",
                    "round_order": 2,
                    "round_name": "HR Interview",
                    "question_count": 3,
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


def _seed_generated_pool(db, blueprint_id, version, round_type, phase, count=3):
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
    db.add(row)
    db.commit()
    return row


def _create_and_publish_drive(client, tpo_headers, db_session, blueprint, pool_rounds=None):
    created = client.post(
        "/api/v1/tpo/mock-drives",
        json={
            "company_name": "Two Interviews Inc",
            "target_role": "Software Engineer",
            "minimum_cgpa": 6.0,
            "maximum_backlogs": 0,
            "eligible_branches": ["Computer Science"],
            "selected_rounds": {"technical_interview": True, "hr_interview": True},
            "blueprint_id": blueprint.id,
        },
        headers=tpo_headers,
    )
    assert created.status_code == 201, created.text
    drive_id = created.json()["id"]

    # Seed required pre-generated pools for enabled blueprint rounds
    if pool_rounds:
        for round_type in pool_rounds:
            _seed_generated_pool(db_session, blueprint.id, blueprint.version, round_type, "TECHNICAL" if round_type == "technical_interview" else "HR")

    published = client.post(
        f"/api/v1/tpo/mock-drives/{drive_id}/publish", headers=tpo_headers
    )
    assert published.status_code == 200, published.text
    return drive_id


def test_start_active_bootstraps_pool_and_is_idempotent(
    client, db_session, tpo, student, blueprint
):
    _clear_rate_limiter()
    tpo_headers = _headers(tpo)
    student_headers = _headers(student)

    drive_id = _create_and_publish_drive(
        client, tpo_headers, db_session, blueprint, pool_rounds=["technical_interview", "hr_interview"]
    )
    started = client.post(
        f"/api/v1/mock-drives/{drive_id}/start", headers=student_headers
    )
    assert started.status_code == 200, started.text
    assert started.json()["current_round"] == "technical_interview"
    session_id = started.json()["session_id"]

    first = client.post(
        "/api/v1/interview/session/start-active", headers=student_headers
    )
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["phase"] == "TECHNICAL"
    assert body["total_turns"] == 3
    interview_id = body["interview_id"]

    # A pool was created for the session, cloned from the generated blueprint
    # pool (no candidate-time generation).
    pools = (
        db_session.query(ApprovedQuestionPool)
        .filter_by(session_id=session_id)
        .all()
    )
    assert len(pools) == 1
    assert all(q["phase"] == "TECHNICAL" for q in pools[0].question_pool)

    # The interview can immediately serve its first question.
    nxt = client.get(
        f"/api/v1/interview/session/{interview_id}/next", headers=student_headers
    )
    assert nxt.status_code == 200, nxt.text
    assert nxt.json()["phase"] == "TECHNICAL"

    # Idempotent: a reload/refresh returns the same session, not a new one.
    second = client.post(
        "/api/v1/interview/session/start-active", headers=student_headers
    )
    assert second.status_code == 200, second.text
    assert second.json()["interview_id"] == interview_id


def test_start_active_resolves_current_round_after_advance(
    client, db_session, tpo, student, blueprint
):
    _clear_rate_limiter()
    tpo_headers = _headers(tpo)
    student_headers = _headers(student)

    drive_id = _create_and_publish_drive(
        client, tpo_headers, db_session, blueprint, pool_rounds=["technical_interview", "hr_interview"]
    )
    started = client.post(
        f"/api/v1/mock-drives/{drive_id}/start", headers=student_headers
    )
    assert started.status_code == 200, started.text

    technical = client.post(
        "/api/v1/interview/session/start-active", headers=student_headers
    )
    assert technical.status_code == 200, technical.text
    assert technical.json()["phase"] == "TECHNICAL"
    technical_id = technical.json()["interview_id"]

    advanced = client.post(
        f"/api/v1/mock-drives/{drive_id}/advance", headers=student_headers
    )
    assert advanced.status_code == 200, advanced.text
    assert advanced.json()["current_round"] == "hr_interview"

    # The active round moved to HR, so the bootstrap must resolve the HR
    # interview (not resume the still-open technical one).
    hr = client.post("/api/v1/interview/session/start-active", headers=student_headers)
    assert hr.status_code == 200, hr.text
    hr_body = hr.json()
    assert hr_body["phase"] == "HR"
    assert hr_body["interview_id"] != technical_id

    hr_next = client.get(
        f"/api/v1/interview/session/{hr_body['interview_id']}/next",
        headers=student_headers,
    )
    assert hr_next.status_code == 200, hr_next.text
    assert hr_next.json()["phase"] == "HR"


def test_start_active_returns_404_without_active_round(client, db_session, student):
    _clear_rate_limiter()
    # No active session at all -> 404, so the frontend falls back to localStorage.
    resp = client.post(
        "/api/v1/interview/session/start-active", headers=_headers(student)
    )
    assert resp.status_code == 404, resp.text


def test_start_active_isolated_per_candidate(
    client, db_session, tpo, student, blueprint
):
    _clear_rate_limiter()
    tpo_headers = _headers(tpo)
    student_headers = _headers(student)
    other = _make_student(db_session, "Other Student")
    other_headers = _headers(other)

    drive_id = _create_and_publish_drive(
        client, tpo_headers, db_session, blueprint, pool_rounds=["technical_interview", "hr_interview"]
    )
    started = client.post(
        f"/api/v1/mock-drives/{drive_id}/start", headers=student_headers
    )
    assert started.status_code == 200, started.text

    mine = client.post("/api/v1/interview/session/start-active", headers=student_headers)
    assert mine.status_code == 200, mine.text

    # Another candidate has no active session and must not hijack mine.
    theirs = client.post(
        "/api/v1/interview/session/start-active", headers=other_headers
    )
    assert theirs.status_code == 404, theirs.text
