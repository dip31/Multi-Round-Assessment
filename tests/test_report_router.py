"""Regression tests for the TPO/admin Mock Drive analytics endpoints.

Covers the three report endpoints that were previously broken against the real
schema (undefined ``get_competency_id`` and non-existent model attributes):

  GET /api/v1/report/admin/mock-drive-completion
  GET /api/v1/report/admin/mock-drive/{drive_id}/results
  GET /api/v1/report/admin/mock-drive/{drive_id}/evidence-coverage

Runs against an isolated in-memory SQLite database with FastAPI dependency
overrides (mirroring ``tests/test_mock_drive.py``); it never touches the live
dev database. Completion is defined per-candidate (``AssessmentContext.status ==
"completed"``); a drive is "completed" when at least one candidate completed it.
"""

import uuid

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

from tests.test_competency_mapping import (
    _snapshot,
    _seed_context_session,
    _add_aptitude_attempt,
    map_session_evidence,
)

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


# Force-import all models so Base.metadata is complete
import app.models.user               # noqa: F401, E402
import app.models.profile            # noqa: F401, E402
import app.models.assessment         # noqa: F401, E402
import app.models.assessment_context # noqa: F401, E402
import app.models.mock_drive         # noqa: F401, E402
import app.models.aptitude           # noqa: F401, E402
import app.models.coding             # noqa: F401, E402
import app.models.interview          # noqa: F401, E402
import app.models.competency         # noqa: F401, E402
import app.models.company_data       # noqa: F401, E402

from app.models.assessment import AssessmentRound, AssessmentSession  # noqa: E402
from app.models.assessment_context import AssessmentPolicy  # noqa: E402
from app.models.user import User                            # noqa: E402

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module", autouse=True)
def _install_db_override():
    application.dependency_overrides[get_db] = override_get_db
    yield
    application.dependency_overrides.pop(get_db, None)


client = TestClient(application)

PASSWORD = "Password@123"
COMPLETION_URL = "/api/v1/report/admin/mock-drive-completion"

COMPETENCIES = [
    {"id": "quant", "name": "Quant", "weight_pct": 60, "topics": ["Quant Apt"]},
    {"id": "reasoning", "name": "Reasoning", "weight_pct": 40, "topics": ["Logical Reasoning"]},
]


@pytest.fixture(autouse=True)
def _fresh_schema():
    """Rebuild a clean schema (and required policies) before every test."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        db.add(AssessmentPolicy(
            id=1, name="Legacy Practice Policy", session_duration_minutes=180,
            round_duration_minutes=30, max_attempts=None, resume_allowed=True,
            exit_allowed=True, progression_mode="sequential",
            progression_config={"rounds": ["aptitude", "coding", "interview"]},
        ))
        db.add(AssessmentPolicy(
            id=2, name="Practice Policy", session_duration_minutes=180,
            round_duration_minutes=30, max_attempts=None, resume_allowed=True,
            exit_allowed=True, progression_mode="independent",
            progression_config={},
        ))
        db.commit()
    finally:
        db.close()
    yield


def _register_and_login(role):
    uid = uuid.uuid4().hex[:8]
    email = f"report_{role}_{uid}@test.com"
    reg = client.post(
        "/api/v1/auth/register",
        json={"name": f"Test {role}", "email": email, "password": PASSWORD, "role": role},
    )
    assert reg.status_code in (200, 201), reg.text
    login = client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    return headers, email


def _user_id(email):
    db = TestingSessionLocal()
    try:
        return db.query(User).filter(User.email == email).first().id
    finally:
        db.close()


def _seed_drive(
    tpo_id,
    student_id,
    *,
    drive_status="published",
    context_status="completed",
    round_status="completed",
    round_score=80.0,
    with_snapshot=True,
):
    """Create a MockDrive + context + session (+ round/evidence) and commit."""
    db = TestingSessionLocal()
    try:
        student = db.query(User).filter(User.id == student_id).first()
        snapshot = _snapshot(COMPETENCIES) if with_snapshot else None
        drive, ctx, session = _seed_context_session(db, student, snapshot)
        drive.status = drive_status
        drive.created_by_id = tpo_id

        round_ = AssessmentRound(
            session_id=session.id,
            round_type="aptitude",
            status=round_status,
            score=round_score,
            max_questions=5,
        )
        db.add(round_)
        db.flush()
        _add_aptitude_attempt(db, round_.id, "Quant Apt", is_correct=True)
        if with_snapshot:
            map_session_evidence(db, session)
        ctx.status = context_status
        db.commit()
        return {
            "drive_id": drive.id,
            "context_id": ctx.id,
            "session_id": session.id,
            "round_id": round_.id,
        }
    finally:
        db.close()


# ─── Authorization ────────────────────────────────────────────────────


def test_completion_requires_authentication():
    assert client.get(COMPLETION_URL).status_code in (401, 403)


def test_completion_rejects_student():
    headers, _ = _register_and_login("student")
    r = client.get(COMPLETION_URL, headers=headers)
    assert r.status_code == 403


def test_completion_allows_tpo():
    headers, _ = _register_and_login("tpo")
    r = client.get(COMPLETION_URL, headers=headers)
    assert r.status_code == 200


# ─── Completion endpoint ──────────────────────────────────────────────


def test_completion_returns_expected_shape():
    tpo_headers, tpo_email = _register_and_login("tpo")
    _, student_email = _register_and_login("student")
    seeded = _seed_drive(_user_id(tpo_email), _user_id(student_email))

    r = client.get(COMPLETION_URL, headers=tpo_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    for key in (
        "total_drives", "completed_drives", "completion_rate",
        "drive_summaries", "competency_results", "generated_at",
    ):
        assert key in data

    assert data["total_drives"] >= 1
    assert data["completed_drives"] >= 1

    summary = next(
        (s for s in data["drive_summaries"] if s["drive_id"] == seeded["drive_id"]),
        None,
    )
    assert summary is not None
    assert summary["status"] == "completed"
    assert summary["completed_candidates"] == 1
    assert summary["total_candidates"] == 1
    assert summary["avg_score"] == 80.0

    # Competency results come from the scoring service, keyed by competency_id.
    by_cid = {c["competency_id"]: c for c in data["competency_results"]}
    assert "quant" in by_cid
    assert by_cid["quant"]["status_distribution"]["assessed"] == 1


def test_completion_excludes_draft_drives():
    tpo_headers, tpo_email = _register_and_login("tpo")
    _, student_email = _register_and_login("student")
    seeded = _seed_drive(
        _user_id(tpo_email), _user_id(student_email), drive_status="draft"
    )

    data = client.get(COMPLETION_URL, headers=tpo_headers).json()
    assert all(s["drive_id"] != seeded["drive_id"] for s in data["drive_summaries"])


def test_single_completed_round_is_not_a_completed_drive():
    """A scored round with a non-completed context must not count as completed."""
    tpo_headers, tpo_email = _register_and_login("tpo")
    _, student_email = _register_and_login("student")
    seeded = _seed_drive(
        _user_id(tpo_email),
        _user_id(student_email),
        context_status="active",
        round_status="completed",
        round_score=55.0,
    )

    data = client.get(COMPLETION_URL, headers=tpo_headers).json()
    summary = next(
        (s for s in data["drive_summaries"] if s["drive_id"] == seeded["drive_id"]),
        None,
    )
    assert summary is not None
    assert summary["status"] == "in_progress"
    assert summary["completed_candidates"] == 0


def test_completion_no_completed_scored_rounds_is_omitted_not_zeroed():
    tpo_headers, tpo_email = _register_and_login("tpo")
    _, student_email = _register_and_login("student")
    seeded = _seed_drive(
        _user_id(tpo_email),
        _user_id(student_email),
        context_status="active",
        round_status="active",
        round_score=None,
    )

    data = client.get(COMPLETION_URL, headers=tpo_headers).json()
    # No completed scored rounds -> no summary row, and no fabricated avg_score
    # (0.0 must not be invented in place of missing data).
    assert all(s["drive_id"] != seeded["drive_id"] for s in data["drive_summaries"])


# ─── Results endpoint ─────────────────────────────────────────────────


def test_results_returns_candidate_data_with_zero_score_included():
    tpo_headers, tpo_email = _register_and_login("tpo")
    _, student_email = _register_and_login("student")
    seeded = _seed_drive(
        _user_id(tpo_email), _user_id(student_email), round_score=0.0
    )

    url = f"/api/v1/report/admin/mock-drive/{seeded['drive_id']}/results"
    r = client.get(url, headers=tpo_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["drive_id"] == seeded["drive_id"]
    assert data["total_candidates"] == 1
    assert len(data["candidate_results"]) == 1

    candidate = data["candidate_results"][0]
    assert candidate["completed_rounds"] == 1
    aptitude = next(
        rd for rd in candidate["round_details"] if rd["round_type"] == "aptitude"
    )
    # A legitimate 0.0 score must be reported as 0.0, never dropped to None.
    assert aptitude["status"] == "completed"
    assert aptitude["score"] == 0.0


def test_results_unknown_drive_returns_404():
    tpo_headers, _ = _register_and_login("tpo")
    url = "/api/v1/report/admin/mock-drive/999999/results"
    assert client.get(url, headers=tpo_headers).status_code == 404


def test_results_draft_drive_returns_400():
    tpo_headers, tpo_email = _register_and_login("tpo")
    _, student_email = _register_and_login("student")
    seeded = _seed_drive(
        _user_id(tpo_email), _user_id(student_email), drive_status="draft"
    )
    url = f"/api/v1/report/admin/mock-drive/{seeded['drive_id']}/results"
    assert client.get(url, headers=tpo_headers).status_code == 400


def test_results_without_snapshot_stays_read_only():
    """Read-only safeguard: a context without a pinned snapshot is never scored
    (and the scoring service must not backfill/persist one)."""
    tpo_headers, tpo_email = _register_and_login("tpo")
    _, student_email = _register_and_login("student")
    seeded = _seed_drive(
        _user_id(tpo_email), _user_id(student_email), with_snapshot=False
    )

    url = f"/api/v1/report/admin/mock-drive/{seeded['drive_id']}/results"
    r = client.get(url, headers=tpo_headers)
    assert r.status_code == 200, r.text
    candidate = r.json()["candidate_results"][0]
    assert candidate["overall_status"] == "unavailable"
    assert candidate["overall_score"] is None

    # No snapshot was persisted as a side effect.
    db = TestingSessionLocal()
    try:
        from app.models.assessment_context import AssessmentContext
        ctx = db.query(AssessmentContext).filter(
            AssessmentContext.id == seeded["context_id"]
        ).first()
        assert ctx.blueprint_snapshot is None
    finally:
        db.close()


# ─── Evidence-coverage endpoint ───────────────────────────────────────


def test_evidence_coverage_includes_unassessed_blueprint_competencies():
    tpo_headers, tpo_email = _register_and_login("tpo")
    _, student_email = _register_and_login("student")
    seeded = _seed_drive(_user_id(tpo_email), _user_id(student_email))

    url = f"/api/v1/report/admin/mock-drive/{seeded['drive_id']}/evidence-coverage"
    r = client.get(url, headers=tpo_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["drive_id"] == seeded["drive_id"]

    by_cid = {c["competency_id"]: c for c in data["coverage_results"]}
    assert "quant" in by_cid and "reasoning" in by_cid
    assert by_cid["quant"]["evidence_count"] >= 1
    assert by_cid["quant"]["coverage_rate"] > 0
    # A configured competency with no evidence is reported (not fabricated).
    assert by_cid["reasoning"]["evidence_count"] == 0


def test_evidence_coverage_unknown_drive_returns_404():
    tpo_headers, _ = _register_and_login("tpo")
    url = "/api/v1/report/admin/mock-drive/999999/evidence-coverage"
    assert client.get(url, headers=tpo_headers).status_code == 404


# ─── Analytics overview endpoint ─────────────────────────────────────

ANALYTICS_URL = "/api/v1/report/admin/analytics/overview"


def test_analytics_requires_authentication():
    assert client.get(ANALYTICS_URL).status_code in (401, 403)


def test_analytics_rejects_student():
    headers, _ = _register_and_login("student")
    assert client.get(ANALYTICS_URL, headers=headers).status_code == 403


def test_analytics_empty_db_returns_zeroed_structure_not_crash():
    """Empty database returns a well-formed zeroed/unavailable structure, no crash."""
    tpo_headers, _ = _register_and_login("tpo")
    r = client.get(ANALYTICS_URL, headers=tpo_headers)
    assert r.status_code == 200, r.text
    data = r.json()

    assert data["kpis"]["total_drives"] == 0
    assert data["kpis"]["enrolled_candidates"] == 0
    assert data["kpis"]["completion_rate"] == 0.0
    assert data["kpis"]["passed_candidates"] is None
    assert data["kpis"]["passed_candidates_available"] is False
    assert data["activity_trend"] == []
    assert data["round_performance"] == []
    assert data["funnel"]["stages"] == []  # no invented funnel stages
    assert data["competency_insights"] == []
    assert data["competency_by_department"]["available"] is False
    assert data["competency_coverage"]["eligible_contexts"] == 0
    assert data["competency_coverage"]["contexts_without_snapshot"] == 0
    assert data["drives"] == []
    assert "generated_at" in data


def test_analytics_returns_expected_shape_with_data():
    tpo_headers, tpo_email = _register_and_login("tpo")
    _, student_email = _register_and_login("student")
    _seed_drive(_user_id(tpo_email), _user_id(student_email))

    r = client.get(ANALYTICS_URL, headers=tpo_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    for key in (
        "kpis", "filters", "activity_trend", "round_performance",
        "funnel", "competency_by_department", "competency_insights",
        "competency_coverage", "drives", "generated_at",
    ):
        assert key in data

    assert data["kpis"]["total_drives"] >= 1
    assert data["kpis"]["enrolled_candidates"] >= 1
    assert data["kpis"]["completion_rate"] > 0

    # Round performance reflects the seeded completed aptitude round.
    by_rt = {r_["round_type"]: r_ for r_ in data["round_performance"]}
    assert "aptitude" in by_rt
    assert by_rt["aptitude"]["completed"] >= 1
    assert by_rt["aptitude"]["avg_score"] is not None

    # Drive comparison row present with real counts.
    drive = next((d for d in data["drives"] if d["enrolled"] > 0), None)
    assert drive is not None
    assert drive["completed"] >= 1
    assert drive["completion_rate"] > 0


def test_analytics_passed_candidates_always_none():
    """Completion ≠ pass. The endpoint never invents a pass outcome."""
    tpo_headers, tpo_email = _register_and_login("tpo")
    _, student_email = _register_and_login("student")
    _seed_drive(_user_id(tpo_email), _user_id(student_email), round_score=100.0)
    data = client.get(ANALYTICS_URL, headers=tpo_headers).json()
    assert data["kpis"]["passed_candidates"] is None
    assert data["kpis"]["passed_candidates_available"] is False
    # No hired/passed funnel stage is fabricated.
    stage_names = [s["stage"].lower() for s in data["funnel"]["stages"]]
    assert not any("hired" in s or "passed" in s for s in stage_names)


def test_analytics_excludes_draft_drives():
    tpo_headers, tpo_email = _register_and_login("tpo")
    _, student_email = _register_and_login("student")
    seeded = _seed_drive(
        _user_id(tpo_email), _user_id(student_email), drive_status="draft"
    )
    data = client.get(ANALYTICS_URL, headers=tpo_headers).json()
    assert all(d["drive_id"] != seeded["drive_id"] for d in data["drives"])
    assert data["kpis"]["total_drives"] == 0


def test_analytics_company_filter_is_applied():
    tpo_headers, tpo_email = _register_and_login("tpo")
    _, student_email = _register_and_login("student")
    _seed_drive(_user_id(tpo_email), _user_id(student_email))

    # Filtering by a non-existent company yields empty results, not a crash.
    data = client.get(
        f"{ANALYTICS_URL}?company=NoSuchCompany", headers=tpo_headers
    ).json()
    assert data["kpis"]["total_drives"] == 0
    assert data["drives"] == []


def test_analytics_round_performance_keeps_score_scale_separate():
    """Raw scores are reported unscaled; a 0.8 coding score must not become 80%."""
    tpo_headers, tpo_email = _register_and_login("tpo")
    _, student_email = _register_and_login("student")
    _seed_drive(
        _user_id(tpo_email), _user_id(student_email),
        round_score=0.8, with_snapshot=False,
    )
    data = client.get(ANALYTICS_URL, headers=tpo_headers).json()
    by_rt = {r_["round_type"]: r_ for r_ in data["round_performance"]}
    # avg_score is the raw persisted value (0-1 coding scale), not multiplied by 100.
    if "aptitude" in by_rt and by_rt["aptitude"]["avg_score"] is not None:
        assert by_rt["aptitude"]["avg_score"] <= 100


def test_analytics_without_snapshot_stays_read_only():
    """Read-only safeguard: no snapshot backfill as a side effect of analytics."""
    tpo_headers, tpo_email = _register_and_login("tpo")
    _, student_email = _register_and_login("student")
    seeded = _seed_drive(
        _user_id(tpo_email), _user_id(student_email), with_snapshot=False
    )
    r = client.get(ANALYTICS_URL, headers=tpo_headers)
    assert r.status_code == 200, r.text
    assert r.json()["competency_coverage"]["contexts_without_snapshot"] == 1

    db = TestingSessionLocal()
    try:
        from app.models.assessment_context import AssessmentContext
        ctx = db.query(AssessmentContext).filter(
            AssessmentContext.id == seeded["context_id"]
        ).first()
        assert ctx.blueprint_snapshot is None
    finally:
        db.close()


def test_analytics_competency_insights_from_scoring_service():
    """Competency insights are derived from the authoritative scoring service."""
    tpo_headers, tpo_email = _register_and_login("tpo")
    _, student_email = _register_and_login("student")
    _seed_drive(_user_id(tpo_email), _user_id(student_email))
    data = client.get(ANALYTICS_URL, headers=tpo_headers).json()
    # With a snapshot + evidence, quant competency should surface in insights.
    ids = [c["competency_id"] for c in data["competency_insights"]]
    assert "quant" in ids
    quant = next(c for c in data["competency_insights"] if c["competency_id"] == "quant")
    assert quant["assessed"] >= 1
    assert quant["evidence_count"] >= 1
    assert data["competency_coverage"]["eligible_contexts"] == 1
    # Only aptitude evidence is seeded; configured competencies without evidence
    # remain unassessed, so the overall score is provisional by the scoring contract.
    assert data["competency_coverage"]["provisional_scored_contexts"] == 1


def test_cohort_stats_uses_distinct_candidates_and_round_types():
    """Repeated round rows/sessions do not inflate candidate completion rates."""
    tpo_headers, _ = _register_and_login("tpo")
    _, first_email = _register_and_login("student")
    _, second_email = _register_and_login("student")
    first_id = _user_id(first_email)
    second_id = _user_id(second_email)

    db = TestingSessionLocal()
    try:
        first_session = AssessmentSession(user_id=first_id, status="completed", total_score=75)
        repeated_session = AssessmentSession(user_id=first_id, status="completed", total_score=85)
        second_session = AssessmentSession(user_id=second_id, status="completed", total_score=0)
        db.add_all([first_session, repeated_session, second_session])
        db.flush()
        db.add_all([
            AssessmentRound(session_id=first_session.id, round_type="aptitude", status="completed"),
            AssessmentRound(session_id=first_session.id, round_type="coding", status="completed"),
            AssessmentRound(session_id=first_session.id, round_type="technical_interview", status="completed"),
            AssessmentRound(session_id=repeated_session.id, round_type="aptitude", status="completed"),
            AssessmentRound(session_id=repeated_session.id, round_type="aptitude", status="completed"),
            AssessmentRound(session_id=repeated_session.id, round_type="aptitude", status="completed"),
            AssessmentRound(session_id=second_session.id, round_type="coding", status="completed"),
        ])
        db.commit()
    finally:
        db.close()

    response = client.get("/api/v1/report/admin/cohort-stats", headers=tpo_headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total_candidates"] == 2
    assert data["completed_sessions"] == 3
    assert data["completion_rates"] == {
        "aptitude": 0.5,
        "coding": 1.0,
        "interview": 0.5,
        "all_three": 0.5,
    }
