"""Regression tests for the TPO Readiness Analytics endpoint (EDI5).

Covers ``GET /api/v1/report/admin/readiness/overview``:

* authorization mirrors the other admin/TPO report endpoints;
* every readiness score is derived from the authoritative competency scoring
  service over persisted, completed mock-drive attempts — never invented;
* EDI5 has no readiness threshold and no placement/offer records, so those two
  KPIs must always be explicitly ``available: false`` (never a fabricated 0);
* aggregates contain no candidate identifiers (no PII).

Runs against an isolated in-memory SQLite database with FastAPI dependency
overrides (mirroring ``tests/test_report_router.py``); it never touches the live
dev database.
"""

import uuid
from datetime import datetime

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
from app.models.assessment_context import (  # noqa: E402
    AssessmentContext,
    AssessmentPolicy,
)
from app.models.coding import CodingProblem, CodingSubmission  # noqa: E402
from app.models.mock_drive import MockDrive  # noqa: E402
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
READINESS_URL = "/api/v1/report/admin/readiness/overview"

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
    email = f"readiness_{role}_{uid}@test.com"
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


def _seed_attempt(
    tpo_id,
    student_id,
    *,
    is_correct=True,
    topic="Quant Apt",
    drive_status="published",
    with_snapshot=True,
    snapshot_competencies=None,
    drive_id=None,
    company=None,
    created_at=None,
    completed_at=None,
):
    """Seed one completed mock-drive attempt (drive + context + session + evidence).

    ``snapshot_competencies`` overrides the configured competencies baked into
    the pinned snapshot (defaults to ``COMPETENCIES``). Pass ``[]`` to seed a
    completed-but-unscorable context. ``drive_id`` reuses an existing drive;
    ``company`` sets the drive company name when a new drive is created.
    """
    db = TestingSessionLocal()
    try:
        student = db.query(User).filter(User.id == student_id).first()
        if not with_snapshot:
            snapshot = None
        elif snapshot_competencies is not None:
            snapshot = _snapshot(snapshot_competencies)
        else:
            snapshot = _snapshot(COMPETENCIES)

        existing_drive = None
        if drive_id is not None:
            existing_drive = db.query(MockDrive).filter(
                MockDrive.id == drive_id
            ).first()
        drive, ctx, session = _seed_context_session(
            db, student, snapshot, drive=existing_drive
        )
        drive.status = drive_status
        drive.created_by_id = tpo_id
        if company is not None:
            drive.company_name = company
            ctx.company_name = company


        round_ = AssessmentRound(
            session_id=session.id,
            round_type="aptitude",
            status="completed",
            score=80.0,
            max_questions=5,
        )
        db.add(round_)
        db.flush()
        _add_aptitude_attempt(db, round_.id, topic, is_correct=is_correct)
        if with_snapshot:
            map_session_evidence(db, session)
        ctx.status = "completed"
        if created_at is not None:
            ctx.created_at = created_at
        if completed_at is not None:
            ctx.completed_at = completed_at
        db.commit()
        return {
            "drive_id": drive.id,
            "context_id": ctx.id,
            "session_id": session.id,
        }
    finally:
        db.close()


# ─── Authorization ────────────────────────────────────────────────────


def test_readiness_requires_authentication():
    assert client.get(READINESS_URL).status_code in (401, 403)


def test_readiness_rejects_student():
    headers, _ = _register_and_login("student")
    assert client.get(READINESS_URL, headers=headers).status_code == 403


def test_readiness_allows_tpo():
    headers, _ = _register_and_login("tpo")
    assert client.get(READINESS_URL, headers=headers).status_code == 200


def test_readiness_allows_admin():
    headers, _ = _register_and_login("admin")
    assert client.get(READINESS_URL, headers=headers).status_code == 200


# ─── Empty state ──────────────────────────────────────────────────────


def test_readiness_empty_db_returns_unavailable_not_zeroed():
    """With no scored attempts the KPIs must be unavailable, never a fake 0."""
    headers, _ = _register_and_login("tpo")
    r = client.get(READINESS_URL, headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()

    for key in (
        "generated_at", "filters_applied", "score_scale", "coverage",
        "kpis", "readiness_over_time", "readiness_distribution",
        "by_drive", "by_department", "skill_gaps", "insights", "filters",
    ):
        assert key in data

    avg = data["kpis"]["average_readiness"]
    assert avg["available"] is False
    assert avg["value"] is None  # not 0
    assert avg["attempts"] == 0
    assert avg["reason"]

    improvement = data["kpis"]["attempt_improvement"]
    assert improvement["available"] is False
    assert improvement["mean_delta"] is None  # not 0
    assert improvement["reason"]

    assert data["coverage"]["scored_attempts"] == 0
    assert data["coverage"]["completed_contexts"] == 0
    assert data["readiness_over_time"] == []
    assert data["readiness_distribution"]["total"] == 0
    assert data["skill_gaps"]["available"] is False
    assert data["skill_gaps"]["competencies"] == []
    assert data["insights"] == []


def test_readiness_scale_and_policy_version_reported():
    headers, _ = _register_and_login("tpo")
    data = client.get(READINESS_URL, headers=headers).json()
    assert data["score_scale"]["min"] == 0
    assert data["score_scale"]["max"] == 100
    assert "d1-v1" in data["score_scale"]["scoring_policy_versions"]


# ─── Scored data ──────────────────────────────────────────────────────


def test_readiness_computes_average_from_scored_attempts():
    tpo_headers, tpo_email = _register_and_login("tpo")
    _, student_email = _register_and_login("student")
    _seed_attempt(_user_id(tpo_email), _user_id(student_email), is_correct=True)

    data = client.get(READINESS_URL, headers=tpo_headers).json()
    avg = data["kpis"]["average_readiness"]
    # quant correct -> normalized 100 at 60% weight, reasoning unassessed -> 60.0.
    assert avg["available"] is True
    assert avg["value"] == 60.0
    assert avg["attempts"] == 1
    assert avg["eligible_candidates"] == 1
    assert data["coverage"]["scored_attempts"] == 1
    assert data["coverage"]["completed_contexts"] == 1


def test_readiness_legitimate_zero_score_is_kept():
    """An all-incorrect attempt is a real 0.0, not dropped to unavailable."""
    tpo_headers, tpo_email = _register_and_login("tpo")
    _, student_email = _register_and_login("student")
    _seed_attempt(_user_id(tpo_email), _user_id(student_email), is_correct=False)

    data = client.get(READINESS_URL, headers=tpo_headers).json()
    avg = data["kpis"]["average_readiness"]
    assert avg["available"] is True
    assert avg["value"] == 0.0
    assert data["coverage"]["scored_attempts"] == 1


def test_skill_gaps_include_supported_assessment_sources_and_unassessed_attempts():
    tpo_headers, tpo_email = _register_and_login("tpo")
    _, student_email = _register_and_login("student")
    _seed_attempt(_user_id(tpo_email), _user_id(student_email), is_correct=True)

    skill_gaps = client.get(READINESS_URL, headers=tpo_headers).json()["skill_gaps"]
    assert skill_gaps["assessment_types"] == ["aptitude", "coding"]

    overall_quant = next(
        row for row in skill_gaps["competencies"] if row["competency_id"] == "quant"
    )
    assert overall_quant["avg_score"] == 100.0
    assert overall_quant["assessment_types"] == ["aptitude"]

    aptitude_quant = next(
        row for row in skill_gaps["by_assessment_type"]["aptitude"]["competencies"]
        if row["competency_id"] == "quant"
    )
    assert aptitude_quant["assessed"] == 1
    assert aptitude_quant["candidates"] == 1
    assert aptitude_quant["evidence_count"] == 1

    coding_quant = next(
        row for row in skill_gaps["by_assessment_type"]["coding"]["unassessed"]
        if row["competency_id"] == "quant"
    )
    assert coding_quant["avg_score"] is None
    assert coding_quant["assessed"] == 0
    assert coding_quant["candidates"] == 1
    assert coding_quant["coverage_rate"] == 0.0


def test_coding_skill_gap_uses_persisted_scores_and_counts_attempt_once():
    tpo_headers, tpo_email = _register_and_login("tpo")
    _, student_email = _register_and_login("student")
    competencies = [
        {"id": "coding", "name": "Coding Proficiency", "weight_pct": 100, "topics": ["Arrays"]}
    ]
    seeded = _seed_attempt(
        _user_id(tpo_email), _user_id(student_email), topic="Unmapped aptitude topic",
        snapshot_competencies=competencies,
    )
    _, missing_result_email = _register_and_login("student")
    _seed_attempt(
        _user_id(tpo_email), _user_id(missing_result_email), topic="Unmapped aptitude topic",
        snapshot_competencies=competencies,
    )

    db = TestingSessionLocal()
    try:
        coding_round = AssessmentRound(
            session_id=seeded["session_id"], round_type="coding", status="completed", score=0.8
        )
        problem = CodingProblem(title="Arrays", description="Array task", difficulty="easy")
        problem.tags_list = ["Arrays"]
        db.add_all([coding_round, problem])
        db.flush()
        db.add_all([
            CodingSubmission(
                round_id=coding_round.id, problem_id=problem.id, code="solution",
                language="python", status="accepted", score=0.8,
            ),
            CodingSubmission(
                round_id=coding_round.id, problem_id=problem.id, code="solution retry",
                language="python", status="wrong_answer", score=0.4,
            ),
        ])
        db.flush()
        session = db.query(AssessmentSession).filter(
            AssessmentSession.id == seeded["session_id"]
        ).first()
        map_session_evidence(db, session)
        db.commit()
    finally:
        db.close()

    result = client.get(READINESS_URL, headers=tpo_headers).json()["skill_gaps"]
    coding_row = result["by_assessment_type"]["coding"]["competencies"][0]
    assert coding_row["competency_name"] == "Coding Proficiency"
    assert coding_row["avg_score"] == 60.0
    assert coding_row["gap_to_100"] == 40.0
    assert coding_row["assessed_attempts"] == 1
    assert coding_row["eligible_attempts"] == 2
    assert coding_row["coverage_percent"] == 50.0
    assert coding_row["evidence_items"] == 2
    assert coding_row["evidence_sources"] == ["coding"]

    combined_row = result["competencies"][0]
    assert combined_row["avg_score"] == 60.0
    assert combined_row["evidence_sources"] == ["coding"]

    aptitude_only = result["by_assessment_type"]["aptitude"]
    assert aptitude_only["competencies"] == []
    assert aptitude_only["unassessed"][0]["avg_score"] is None
    assert aptitude_only["unassessed"][0]["eligible_attempts"] == 2


def test_readiness_improvement_pairs_earliest_and_latest():
    tpo_headers, tpo_email = _register_and_login("tpo")
    _, student_email = _register_and_login("student")
    sid = _user_id(student_email)
    tpo_id = _user_id(tpo_email)

    _seed_attempt(
        tpo_id, sid, is_correct=False,
        completed_at=datetime(2026, 1, 5, 10, 0),
    )
    _seed_attempt(
        tpo_id, sid, is_correct=True,
        completed_at=datetime(2026, 2, 5, 10, 0),
    )

    data = client.get(READINESS_URL, headers=tpo_headers).json()
    improvement = data["kpis"]["attempt_improvement"]
    assert improvement["available"] is True
    assert improvement["students_compared"] == 1
    # earliest 0.0 -> latest 60.0
    assert improvement["mean_delta"] == 60.0
    assert improvement["improved"] == 1
    assert improvement["declined"] == 0
    assert improvement["unchanged"] == 0

    # Distribution covers both attempts (0-20 and 40-60 buckets).
    dist = data["readiness_distribution"]
    assert dist["total"] == 2
    assert sum(b["count"] for b in dist["buckets"]) == 2


def test_readiness_improvement_unavailable_for_single_attempt():
    tpo_headers, tpo_email = _register_and_login("tpo")
    _, student_email = _register_and_login("student")
    _seed_attempt(_user_id(tpo_email), _user_id(student_email))

    data = client.get(READINESS_URL, headers=tpo_headers).json()
    improvement = data["kpis"]["attempt_improvement"]
    assert improvement["available"] is False
    assert improvement["mean_delta"] is None
    assert improvement["students_compared"] == 0


def test_readiness_threshold_and_placement_always_unavailable():
    """Even with scored data, threshold + placement stay honestly unavailable."""
    tpo_headers, tpo_email = _register_and_login("tpo")
    _, student_email = _register_and_login("student")
    _seed_attempt(_user_id(tpo_email), _user_id(student_email))

    data = client.get(READINESS_URL, headers=tpo_headers).json()
    threshold = data["kpis"]["threshold_percentage"]
    placement = data["kpis"]["placement_rate"]

    assert threshold["available"] is False
    assert threshold["value"] is None
    assert threshold["reason"]
    assert placement["available"] is False
    assert placement["value"] is None
    assert placement["reason"]
    # No fabricated pass/placement insight sneaks in.
    assert all("placement" not in i["id"] for i in data["insights"])


# ─── Aggregates contain no candidate PII ──────────────────────────────


def test_readiness_response_contains_no_candidate_pii():
    tpo_headers, tpo_email = _register_and_login("tpo")
    _, student_email = _register_and_login("student")
    _seed_attempt(_user_id(tpo_email), _user_id(student_email))

    r = client.get(READINESS_URL, headers=tpo_headers)
    assert r.status_code == 200, r.text
    text = r.text
    assert student_email not in text
    assert "Test student" not in text
    # Aggregates only: no candidate result list.
    data = r.json()
    assert "candidate_results" not in data
    assert "candidates" not in data


# ─── Filtering / scoping is server-side ───────────────────────────────


def test_readiness_excludes_draft_drives():
    tpo_headers, tpo_email = _register_and_login("tpo")
    _, student_email = _register_and_login("student")
    seeded = _seed_attempt(
        _user_id(tpo_email), _user_id(student_email), drive_status="draft"
    )

    data = client.get(READINESS_URL, headers=tpo_headers).json()
    assert data["coverage"]["scored_attempts"] == 0
    assert all(d["drive_id"] != seeded["drive_id"] for d in data["by_drive"])


def test_readiness_company_filter_is_applied_server_side():
    tpo_headers, tpo_email = _register_and_login("tpo")
    _, student_email = _register_and_login("student")
    _seed_attempt(_user_id(tpo_email), _user_id(student_email))

    data = client.get(
        f"{READINESS_URL}?company=NoSuchCompany", headers=tpo_headers
    ).json()
    assert data["coverage"]["scored_attempts"] == 0
    assert data["kpis"]["average_readiness"]["available"] is False
    assert data["filters_applied"]["company"] == "NoSuchCompany"


def test_readiness_period_filter_excludes_old_attempts():
    tpo_headers, tpo_email = _register_and_login("tpo")
    _, student_email = _register_and_login("student")
    _seed_attempt(
        _user_id(tpo_email), _user_id(student_email),
        created_at=datetime(2020, 1, 1, 9, 0),
    )

    recent = client.get(f"{READINESS_URL}?period=7", headers=tpo_headers).json()
    assert recent["coverage"]["scored_attempts"] == 0

    all_time = client.get(f"{READINESS_URL}?period=all", headers=tpo_headers).json()
    assert all_time["coverage"]["scored_attempts"] == 1


# ─── Skill gaps ───────────────────────────────────────────────────────


def test_readiness_skill_gaps_from_configured_competencies():
    tpo_headers, tpo_email = _register_and_login("tpo")
    _, student_email = _register_and_login("student")
    # Only "Quant" has evidence; "Reasoning" is configured but unassessed.
    _seed_attempt(_user_id(tpo_email), _user_id(student_email), topic="Quant Apt")

    data = client.get(READINESS_URL, headers=tpo_headers).json()
    gaps = data["skill_gaps"]
    assert gaps["available"] is True

    assessed_ids = [c["competency_id"] for c in gaps["competencies"]]
    assert "quant" in assessed_ids
    quant = next(c for c in gaps["competencies"] if c["competency_id"] == "quant")
    assert quant["avg_score"] == 100.0
    assert quant["gap_to_100"] == 0.0
    assert quant["assessed"] == 1

    unassessed_ids = [c["competency_id"] for c in gaps["unassessed"]]
    assert "reasoning" in unassessed_ids
    reasoning = next(
        c for c in gaps["unassessed"] if c["competency_id"] == "reasoning"
    )
    assert reasoning["avg_score"] is None  # never zeroed
    assert reasoning["assessed"] == 0


def test_readiness_without_snapshot_not_scored():
    """Read-only safeguard: no snapshot -> completed but never scored."""
    tpo_headers, tpo_email = _register_and_login("tpo")
    _, student_email = _register_and_login("student")
    seeded = _seed_attempt(
        _user_id(tpo_email), _user_id(student_email), with_snapshot=False
    )

    data = client.get(READINESS_URL, headers=tpo_headers).json()
    assert data["coverage"]["completed_contexts"] == 1
    assert data["coverage"]["scored_attempts"] == 0
    assert data["kpis"]["average_readiness"]["available"] is False

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


# ─── Insights ─────────────────────────────────────────────────────────


def test_readiness_intelligence_uses_supported_data_and_not_legacy_findings():
    tpo_headers, tpo_email = _register_and_login("tpo")
    _, student_email = _register_and_login("student")
    _seed_attempt(_user_id(tpo_email), _user_id(student_email))

    data = client.get(READINESS_URL, headers=tpo_headers).json()
    assert data["insights"]
    ids = {ins["id"] for ins in data["insights"]}
    assert "overall-readiness" in ids
    assert "evidence-reliability" in ids
    assert not ids.intersection({
        "lowest-competency", "drive-completion-gap", "assessment-coverage-gap",
        "unscored-assessment-rounds", "multi-attempt-change",
        "repeat-assessment-change", "lowest-topic-accuracy",
    })
    for ins in data["insights"]:
        assert ins["category"] in {"overall", "competency", "cohort", "evidence", "trend"}
        assert ins["title"] and ins["summary"] and ins["evidence"]
        assert ins["sample_size"] >= 1
        assert ins["denominator"] >= ins["sample_size"]
        assert ins["metric"]
        assert ins["period"] == "all"
        if ins["action"]:
            assert ins["action"]["route"] in {"/tpo/analytics", "/tpo/students"}


def test_readiness_intelligence_omits_population_patterns_for_single_student():
    tpo_headers, tpo_email = _register_and_login("tpo")
    _, student_email = _register_and_login("student")
    _seed_attempt(_user_id(tpo_email), _user_id(student_email))

    data = client.get(READINESS_URL, headers=tpo_headers).json()
    ids = {ins["id"] for ins in data["insights"]}
    assert "competency-patterns" not in ids
    assert "department-readiness-pattern" not in ids


def test_readiness_intelligence_surfaces_repeated_competency_patterns():
    tpo_headers, tpo_email = _register_and_login("tpo")
    tpo_id = _user_id(tpo_email)
    student_ids = []
    for _ in range(2):
        _, email = _register_and_login("student")
        student_ids.append(_user_id(email))
    for student_id in student_ids:
        _seed_attempt(tpo_id, student_id, topic="Quant Apt")
        _seed_attempt(tpo_id, student_id, topic="Logical Reasoning")

    data = client.get(READINESS_URL, headers=tpo_headers).json()
    ids = {ins["id"] for ins in data["insights"]}
    assert "competency-patterns" in ids
    pattern = next(i for i in data["insights"] if i["id"] == "competency-patterns")
    assert "students" in pattern["summary"]
    assert pattern["sample_size"] >= 2


def test_readiness_intelligence_empty_scope_returns_no_findings():
    headers, _ = _register_and_login("tpo")
    data = client.get(f"{READINESS_URL}?company=NoSuchCompany", headers=headers).json()
    assert data["insights"] == []

# --- Chart datasets (consumed by the frontend visualizations) ---------


def test_readiness_over_time_bucket_from_scored_attempt():
    """The trend chart receives a real weekly bucket, not an empty array."""
    tpo_headers, tpo_email = _register_and_login("tpo")
    _, student_email = _register_and_login("student")
    _seed_attempt(
        _user_id(tpo_email), _user_id(student_email),
        is_correct=True, completed_at=datetime(2026, 3, 4, 10, 0),
    )

    data = client.get(READINESS_URL, headers=tpo_headers).json()
    series = data["readiness_over_time"]
    assert len(series) == 1
    point = series[0]
    # ISO week start (Monday) for 2026-03-04 is 2026-03-02.
    assert point["bucket_start"] == "2026-03-02"
    assert point["avg_readiness"] == 60.0
    assert point["attempts"] == 1
    assert point["candidates"] == 1


def test_readiness_distribution_buckets_match_attempts():
    """The distribution chart receives buckets whose counts sum to the total."""
    tpo_headers, tpo_email = _register_and_login("tpo")
    _, student_email = _register_and_login("student")
    sid = _user_id(student_email)
    tpo_id = _user_id(tpo_email)
    _seed_attempt(tpo_id, sid, is_correct=False,
                  completed_at=datetime(2026, 1, 5, 10, 0))
    _seed_attempt(tpo_id, sid, is_correct=True,
                  completed_at=datetime(2026, 2, 5, 10, 0))

    data = client.get(READINESS_URL, headers=tpo_headers).json()
    dist = data["readiness_distribution"]
    assert dist["total"] == 2
    assert sum(b["count"] for b in dist["buckets"]) == dist["total"]
    assert "not readiness categories" in dist["note"]


def test_readiness_department_chart_data_is_real():
    """Department readiness is derived from real profile departments."""
    tpo_headers, tpo_email = _register_and_login("tpo")
    _, student_email = _register_and_login("student")
    sid = _user_id(student_email)
    db = TestingSessionLocal()
    try:
        from app.models.profile import StudentProfile
        profile = (
            db.query(StudentProfile)
            .filter(StudentProfile.user_id == sid)
            .first()
        )
        profile.department = "Electrical Engineering"
        db.commit()
    finally:
        db.close()

    _seed_attempt(_user_id(tpo_email), sid, is_correct=True)

    data = client.get(READINESS_URL, headers=tpo_headers).json()
    depts = data["by_department"]
    assert len(depts) == 1
    assert depts[0]["department"] == "Electrical Engineering"
    assert depts[0]["avg_readiness"] == 60.0
    assert depts[0]["candidates"] == 1


def _set_department(student_id, department):
    """Point a student's profile at a real department (or None to blank it)."""
    db = TestingSessionLocal()
    try:
        from app.models.profile import StudentProfile
        profile = (
            db.query(StudentProfile)
            .filter(StudentProfile.user_id == student_id)
            .first()
        )
        profile.department = department
        db.commit()
    finally:
        db.close()


def test_readiness_department_chart_renders_multiple_departments_as_separate_bars():
    """Two scored departments must yield two independent department rows.

    Regression for EDI5: the chart must never collapse a multi-department
    cohort into one bar. Each row keeps its own candidates/attempts/average.
    """
    tpo_headers, tpo_email = _register_and_login("tpo")
    tpo_id = _user_id(tpo_email)

    _, s1 = _register_and_login("student")
    _, s2 = _register_and_login("student")
    sid1, sid2 = _user_id(s1), _user_id(s2)
    _set_department(sid1, "Computer Science")
    _set_department(sid2, "Electronics & Communication")

    _seed_attempt(tpo_id, sid1, is_correct=True)   # Computer Science -> 60.0
    _seed_attempt(tpo_id, sid2, is_correct=False)  # E&C -> 0.0

    depts = client.get(READINESS_URL, headers=tpo_headers).json()["by_department"]
    by_name = {d["department"]: d for d in depts}
    assert set(by_name) == {"Computer Science", "Electronics & Communication"}
    assert by_name["Computer Science"]["avg_readiness"] == 60.0
    assert by_name["Computer Science"]["candidates"] == 1
    assert by_name["Electronics & Communication"]["avg_readiness"] == 0.0
    assert by_name["Electronics & Communication"]["candidates"] == 1
    # Rows are returned in a stable, name-sorted order.
    assert [d["department"] for d in depts] == sorted(by_name)


def test_readiness_department_average_weights_multiple_candidates_in_a_department():
    """Several candidates in one department average, not overwrite, their scores."""
    tpo_headers, tpo_email = _register_and_login("tpo")
    tpo_id = _user_id(tpo_email)

    _, s1 = _register_and_login("student")
    _, s2 = _register_and_login("student")
    sid1, sid2 = _user_id(s1), _user_id(s2)
    _set_department(sid1, "Mechanical")
    _set_department(sid2, "Mechanical")

    _seed_attempt(tpo_id, sid1, is_correct=True)   # 60.0
    _seed_attempt(tpo_id, sid2, is_correct=False)  # 0.0

    depts = client.get(READINESS_URL, headers=tpo_headers).json()["by_department"]
    assert len(depts) == 1
    assert depts[0]["department"] == "Mechanical"
    assert depts[0]["candidates"] == 2
    assert depts[0]["attempts"] == 2
    assert depts[0]["avg_readiness"] == 30.0  # (60 + 0) / 2


def test_readiness_department_excludes_completed_but_unscored_contexts():
    """A completed context with no configured competencies produces no bar.

    This is the EDI5 root-cause guard: readiness is competency-derived, so a
    completed-but-unscored drive must not appear as a department (and must
    never be silently rendered as a fabricated 0).
    """
    tpo_headers, tpo_email = _register_and_login("tpo")
    tpo_id = _user_id(tpo_email)

    _, s1 = _register_and_login("student")
    _, s2 = _register_and_login("student")
    sid1, sid2 = _user_id(s1), _user_id(s2)
    _set_department(sid1, "Scored Dept")
    _set_department(sid2, "Unscored Dept")

    _seed_attempt(tpo_id, sid1, is_correct=True)
    # Snapshot present but carries no configured competencies -> not scorable.
    _seed_attempt(
        tpo_id, sid2, with_snapshot=True, snapshot_competencies=[],
    )

    data = client.get(READINESS_URL, headers=tpo_headers).json()
    by_name = {d["department"]: d for d in data["by_department"]}
    assert set(by_name) == {"Scored Dept"}
    assert data["coverage"]["completed_contexts"] == 2
    assert data["coverage"]["scored_attempts"] == 1


def test_readiness_department_reports_blank_department_as_unspecified():
    """A scored candidate without a profile department is grouped, not dropped.

    ``student_profiles.department`` is NOT NULL, so an unset department is an
    empty string; the router maps that to the ``Unspecified`` bucket.
    """
    tpo_headers, tpo_email = _register_and_login("tpo")
    _, student_email = _register_and_login("student")
    sid = _user_id(student_email)
    _set_department(sid, "")

    _seed_attempt(_user_id(tpo_email), sid, is_correct=True)

    depts = client.get(READINESS_URL, headers=tpo_headers).json()["by_department"]
    assert len(depts) == 1
    assert depts[0]["department"] == "Unspecified"
    assert depts[0]["avg_readiness"] == 60.0


def test_readiness_department_contexts_are_attempts_not_candidates():
    """Repeated attempts by one candidate stay one candidate, two attempts."""
    tpo_headers, tpo_email = _register_and_login("tpo")
    tpo_id = _user_id(tpo_email)
    _, student_email = _register_and_login("student")
    sid = _user_id(student_email)
    _set_department(sid, "Civil")

    _seed_attempt(tpo_id, sid, is_correct=True)   # 60.0
    _seed_attempt(tpo_id, sid, is_correct=False)  # 0.0

    depts = client.get(READINESS_URL, headers=tpo_headers).json()["by_department"]
    assert len(depts) == 1
    assert depts[0]["candidates"] == 1
    assert depts[0]["attempts"] == 2
    assert depts[0]["avg_readiness"] == 30.0


def test_readiness_department_filtered_scope_updates_every_row():
    """The department chart is filter-responsive: a scoped company drops rows."""
    tpo_headers, tpo_email = _register_and_login("tpo")
    tpo_id = _user_id(tpo_email)
    _, s1 = _register_and_login("student")
    _, s2 = _register_and_login("student")
    sid1, sid2 = _user_id(s1), _user_id(s2)
    _set_department(sid1, "Alpha Dept")
    _set_department(sid2, "Beta Dept")

    # Two different companies so a company filter narrows the department set.
    _seed_activity_drive(tpo_id, status="published", company="Acme")
    db = TestingSessionLocal()
    try:
        from app.models.mock_drive import MockDrive

        acme = db.query(MockDrive).filter(MockDrive.company_name == "Acme").first()
        other = MockDrive(
            company_name="Globex", target_role="Engineer", status="published",
            minimum_cgpa=0.0, maximum_backlogs=100, eligible_branches=[],
            selected_rounds={"aptitude": True}, round_configurations={},
            created_by_id=tpo_id,
        )
        db.add(other)
        db.flush()
        acme_id, other_id = acme.id, other.id
    finally:
        db.close()

    _seed_attempt(tpo_id, sid1, is_correct=True, drive_id=acme_id, company="Acme")
    _seed_attempt(tpo_id, sid2, is_correct=True, drive_id=other_id, company="Globex")

    all_rows = client.get(READINESS_URL, headers=tpo_headers).json()["by_department"]
    assert {d["department"] for d in all_rows} == {"Alpha Dept", "Beta Dept"}

    filtered = client.get(
        f"{READINESS_URL}?company=Acme", headers=tpo_headers
    ).json()
    assert {d["department"] for d in filtered["by_department"]} == {"Alpha Dept"}
    assert filtered["filters_applied"]["company"] == "Acme"


def test_readiness_unscored_context_does_not_mutate_pinned_snapshot():
    """Readiness reads must never rewrite or backfill a pinned snapshot.

    Regression for EDI5: querying the overview leaves each context's pinned
    blueprint snapshot byte-for-byte identical (no silent competency backfill).
    """
    import copy

    tpo_headers, tpo_email = _register_and_login("tpo")
    _, student_email = _register_and_login("student")
    sid = _user_id(student_email)
    seeded = _seed_attempt(
        _user_id(tpo_email), sid, with_snapshot=True, snapshot_competencies=[],
    )

    db = TestingSessionLocal()
    try:
        ctx = db.query(AssessmentContext).filter(
            AssessmentContext.id == seeded["context_id"]
        ).first()
        before = copy.deepcopy(ctx.blueprint_snapshot)
    finally:
        db.close()

    assert client.get(READINESS_URL, headers=tpo_headers).status_code == 200

    db = TestingSessionLocal()
    try:
        ctx = db.query(AssessmentContext).filter(
            AssessmentContext.id == seeded["context_id"]
        ).first()
        assert ctx.blueprint_snapshot == before
    finally:
        db.close()



def test_readiness_by_drive_is_not_truncated_for_the_table():
    """The API returns every filtered drive; the frontend limits visible rows."""
    tpo_headers, tpo_email = _register_and_login("tpo")
    _, student_email = _register_and_login("student")
    tpo_id = _user_id(tpo_email)
    sid = _user_id(student_email)
    for _ in range(12):
        _seed_attempt(tpo_id, sid)

    data = client.get(READINESS_URL, headers=tpo_headers).json()
    assert len(data["by_drive"]) >= 12
    assert all("drive_id" in d for d in data["by_drive"])




# --- Drive activity analytics (no competency evidence required) ---
#
# These cover the `drive_activity` block: mock-drive statuses, participant
# completion buckets and persisted event timestamps. None of it may be
# derived from, or substituted for, a readiness/competency score.


def _seed_activity_drive(tpo_id, *, status="published", company="Acme", role="Engineer"):
    db = TestingSessionLocal()
    try:
        drive = MockDrive(
            company_name=company,
            target_role=role,
            status=status,
            minimum_cgpa=0.0,
            maximum_backlogs=100,
            eligible_branches=[],
            selected_rounds={"aptitude": True},
            round_configurations={},
            created_by_id=tpo_id,
        )
        db.add(drive)
        db.commit()
        return drive.id
    finally:
        db.close()


def _seed_activity_context(
    drive_id,
    student_id,
    *,
    status="active",
    created_at=None,
    completed_at=None,
):
    db = TestingSessionLocal()
    try:
        ctx = AssessmentContext(
            mode="mock_drive",
            purpose="mock_drive",
            student_id=student_id,
            policy_id=1,
            mock_drive_id=drive_id,
            status=status,
        )
        db.add(ctx)
        db.flush()
        db.add(AssessmentSession(
            user_id=student_id, context_id=ctx.id, status="in_progress",
        ))
        if created_at is not None:
            ctx.created_at = created_at
        if completed_at is not None:
            ctx.completed_at = completed_at
        db.commit()
        return ctx.id
    finally:
        db.close()


def test_drive_activity_structure_and_empty_db_has_no_fabricated_values():
    """An empty catalogue yields an empty activity block - never fake counts."""
    headers, _ = _register_and_login("tpo")
    r = client.get(READINESS_URL, headers=headers)
    assert r.status_code == 200, r.text
    act = r.json()["drive_activity"]

    for key in (
        "available", "note", "definitions", "status_distribution",
        "kpis", "by_drive", "over_time",
    ):
        assert key in act

    assert act["available"] is False
    assert act["status_distribution"]["rows"] == []
    assert act["status_distribution"]["total"] == 0
    assert act["by_drive"] == []
    assert act["over_time"]["points"] == []

    kpis = act["kpis"]
    assert kpis["drives_in_scope"] == 0
    assert kpis["participants_enrolled"] == 0
    assert kpis["participants_completed"] == 0
    assert kpis["completion_rate"] is None  # unavailable, not 0.0
    assert act["definitions"]["completion_rate"]
    # No readiness/competency value is smuggled into the activity block.
    assert "avg_readiness" not in str(act)
    assert "overall_score" not in str(act)


def test_drive_activity_status_distribution_is_derived_from_drive_status():
    """Status counts come from mock_drives.status, not names or timestamps."""
    headers, email = _register_and_login("tpo")
    tpo_id = _user_id(email)
    _seed_activity_drive(tpo_id, status="published", company="Alpha")
    _seed_activity_drive(tpo_id, status="draft", company="Beta")
    _seed_activity_drive(tpo_id, status="completed", company="Alpha")

    act = client.get(READINESS_URL, headers=headers).json()["drive_activity"]
    sd = act["status_distribution"]
    rows = {r["status"]: r for r in sd["rows"]}

    assert sd["total"] == 3
    assert sd["analysed"] == 2      # published + completed
    assert sd["excluded"] == 1      # draft, documented as excluded elsewhere
    # Only statuses that actually exist in the data are returned.
    assert set(rows) == {"draft", "published", "completed"}
    assert rows["draft"]["drives"] == 1
    assert rows["draft"]["analysed"] is False
    assert rows["published"]["drives"] == 1
    assert rows["published"]["analysed"] is True
    assert rows["completed"]["drives"] == 1
    assert rows["draft"]["pct"] == 33.3
    # Drives in scope everywhere else still excludes drafts.
    assert act["kpis"]["drives_in_scope"] == 2


def test_drive_activity_counts_participants_not_repeated_attempts():
    """Completion buckets are mutually exclusive and participant-based."""
    headers, email = _register_and_login("tpo")
    tpo_id = _user_id(email)
    _, s1 = _register_and_login("student")
    _, s2 = _register_and_login("student")
    _, s3 = _register_and_login("student")
    drive = _seed_activity_drive(tpo_id, status="published")

    _seed_activity_context(drive, _user_id(s1), status="completed",
                           completed_at=datetime(2026, 4, 6, 10, 0))
    _seed_activity_context(drive, _user_id(s2), status="active")
    _seed_activity_context(drive, _user_id(s3), status="cancelled")

    act = client.get(READINESS_URL, headers=headers).json()["drive_activity"]
    row = act["by_drive"][0]
    assert row["contexts"] == 3
    assert row["participants"] == 3
    assert row["completed_participants"] == 1
    assert row["in_progress_participants"] == 1
    assert row["not_started_participants"] == 1
    assert (
        row["completed_participants"]
        + row["in_progress_participants"]
        + row["not_started_participants"]
        == row["participants"]
    )
    assert row["completed_contexts"] == 1
    assert row["active_contexts"] == 1
    assert row["cancelled_contexts"] == 1
    # The same three buckets are reported globally.
    kpis = act["kpis"]
    assert kpis["participants_enrolled"] == 3
    assert kpis["participants_completed"] == 1
    assert kpis["participants_in_progress"] == 1
    assert kpis["participants_not_started"] == 1


def test_drive_activity_completion_rate_uses_the_right_denominator():
    """Repeated attempts by one candidate never inflate the denominator."""
    headers, email = _register_and_login("tpo")
    tpo_id = _user_id(email)
    _, s1 = _register_and_login("student")
    _, s2 = _register_and_login("student")
    drive = _seed_activity_drive(tpo_id, status="published")

    # Three attempts from two people: the denominator must stay 2, not 3.
    _seed_activity_context(drive, _user_id(s1), status="completed",
                           completed_at=datetime(2026, 4, 6, 10, 0))
    _seed_activity_context(drive, _user_id(s1), status="completed",
                           completed_at=datetime(2026, 4, 7, 10, 0))
    _seed_activity_context(drive, _user_id(s2), status="active")

    act = client.get(READINESS_URL, headers=headers).json()["drive_activity"]
    row = act["by_drive"][0]
    assert row["contexts"] == 3
    assert row["participants"] == 2
    assert row["completed_participants"] == 1
    assert row["completion_rate"] == 50.0  # 1 of 2 people, not 2 of 3 attempts

    kpis = act["kpis"]
    assert kpis["participants_enrolled"] == 2
    assert kpis["participants_completed"] == 1
    assert kpis["contexts"] == 3
    assert kpis["completion_rate"] == 50.0


def test_drive_activity_completion_rate_is_unavailable_at_zero_denominator():
    """No participants means no rate - never a fabricated 0%."""
    headers, email = _register_and_login("tpo")
    _seed_activity_drive(_user_id(email), status="published", company="NoTraffic")

    act = client.get(READINESS_URL, headers=headers).json()["drive_activity"]
    row = act["by_drive"][0]
    assert row["contexts"] == 0
    assert row["participants"] == 0
    assert row["completion_rate"] is None
    assert act["kpis"]["participants_enrolled"] == 0
    assert act["kpis"]["completion_rate"] is None
    assert act["over_time"]["points"] == []


def test_drive_activity_over_time_uses_persisted_event_timestamps():
    """Each series is bucketed by the timestamp of the event it counts."""
    headers, email = _register_and_login("tpo")
    tpo_id = _user_id(email)
    _, s1 = _register_and_login("student")
    drive = _seed_activity_drive(tpo_id, status="published")
    _seed_activity_context(drive, _user_id(s1), status="completed",
                           created_at=datetime(2026, 3, 2, 9, 0),
                           completed_at=datetime(2026, 3, 4, 10, 0))
    # A drive with no contexts must not manufacture a bucket.
    _seed_activity_drive(tpo_id, status="published", company="NoTraffic")

    ot = client.get(READINESS_URL, headers=headers).json()["drive_activity"]["over_time"]
    assert ot["granularity"] == "daily"  # 3-day span
    assert [
        (p["bucket_start"], p["registrations"], p["completions"])
        for p in ot["points"]
    ] == [
        ("2026-03-02", 1, 0),  # registration on created_at
        ("2026-03-04", 0, 1),  # completion on completed_at
    ]
    # Empty days between the two events are never interpolated.
    assert all(p["registrations"] or p["completions"] for p in ot["points"])
    assert len(ot["points"]) == 2


def test_drive_activity_over_time_switches_to_weekly_for_wide_spans():
    """Bucket width follows the real span of the data, not a guess."""
    headers, email = _register_and_login("tpo")
    tpo_id = _user_id(email)
    _, s1 = _register_and_login("student")
    _, s2 = _register_and_login("student")
    drive = _seed_activity_drive(tpo_id, status="published")
    _seed_activity_context(drive, _user_id(s1), created_at=datetime(2026, 1, 5, 9, 0))
    _seed_activity_context(drive, _user_id(s2), created_at=datetime(2026, 7, 6, 9, 0))

    ot = client.get(READINESS_URL, headers=headers).json()["drive_activity"]["over_time"]
    assert ot["granularity"] == "weekly"  # 183-day span
    assert [p["bucket_start"] for p in ot["points"]] == ["2026-01-05", "2026-07-06"]
    assert [p["registrations"] for p in ot["points"]] == [1, 1]
    assert "never interpolated" in ot["note"]


def test_drive_activity_period_filter_bounds_the_time_series():
    headers, email = _register_and_login("tpo")
    _, s1 = _register_and_login("student")
    drive = _seed_activity_drive(_user_id(email), status="published")
    _seed_activity_context(drive, _user_id(s1), status="completed",
                           created_at=datetime(2020, 1, 1, 9, 0),
                           completed_at=datetime(2020, 1, 2, 9, 0))

    recent = client.get(f"{READINESS_URL}?period=7", headers=headers).json()["drive_activity"]
    assert recent["over_time"]["points"] == []
    assert recent["kpis"]["participants_enrolled"] == 0
    assert recent["by_drive"][0]["participants"] == 0

    all_time = client.get(f"{READINESS_URL}?period=all", headers=headers).json()["drive_activity"]
    assert [p["bucket_start"] for p in all_time["over_time"]["points"]] == [
        "2020-01-01", "2020-01-02",
    ]
    assert all_time["kpis"]["participants_enrolled"] == 1
    assert all_time["by_drive"][0]["participants"] == 1


def test_drive_activity_filters_apply_to_every_activity_aggregate():
    headers, email = _register_and_login("tpo")
    tpo_id = _user_id(email)
    _, s1 = _register_and_login("student")
    alpha = _seed_activity_drive(tpo_id, status="published", company="Alpha")
    _seed_activity_drive(tpo_id, status="draft", company="Beta")
    _seed_activity_context(alpha, _user_id(s1), status="completed",
                           completed_at=datetime(2026, 6, 1, 10, 0))

    filtered = client.get(f"{READINESS_URL}?company=Alpha", headers=headers).json()
    act = filtered["drive_activity"]
    assert filtered["filters_applied"]["company"] == "Alpha"
    assert act["status_distribution"]["total"] == 1
    assert [r["status"] for r in act["status_distribution"]["rows"]] == ["published"]
    assert [r["company_name"] for r in act["by_drive"]] == ["Alpha"]
    assert act["kpis"]["drives_in_scope"] == 1
    assert act["kpis"]["participants_enrolled"] == 1
    assert act["over_time"]["points"] != []

    # A company with no drives empties every activity aggregate consistently.
    empty = client.get(f"{READINESS_URL}?company=Nope", headers=headers).json()["drive_activity"]
    assert empty["status_distribution"]["rows"] == []
    assert empty["by_drive"] == []
    assert empty["over_time"]["points"] == []
    assert empty["kpis"]["participants_enrolled"] == 0
    assert empty["kpis"]["completion_rate"] is None

    # The documented draft policy: drafts stay out of the analysed set.
    draft_only = client.get(
        f"{READINESS_URL}?drive_status=draft", headers=headers
    ).json()["drive_activity"]
    assert [r["status"] for r in draft_only["status_distribution"]["rows"]] == ["draft"]
    assert draft_only["by_drive"] == []
    assert draft_only["kpis"]["drives_in_scope"] == 0


def test_drive_activity_is_available_while_readiness_stays_unavailable():
    """Category 1 works with zero competency evidence; categories 2 and 3 do not."""
    headers, email = _register_and_login("tpo")
    tpo_id = _user_id(email)
    _, s1 = _register_and_login("student")
    drive = _seed_activity_drive(tpo_id, status="active", company="Solo")
    _seed_activity_context(drive, _user_id(s1), status="completed",
                           completed_at=datetime(2026, 5, 4, 10, 0))

    data = client.get(READINESS_URL, headers=headers).json()

    act = data["drive_activity"]
    assert act["available"] is True
    assert act["status_distribution"]["total"] == 1
    assert act["kpis"]["participants_completed"] == 1
    assert act["kpis"]["completion_rate"] == 100.0
    assert act["over_time"]["points"] != []

    # Competency-derived analytics remain honestly unavailable.
    assert data["coverage"]["scored_attempts"] == 0
    assert data["kpis"]["average_readiness"]["available"] is False
    assert data["kpis"]["average_readiness"]["value"] is None
    assert data["kpis"]["attempt_improvement"]["available"] is False
    assert data["readiness_over_time"] == []
    assert data["readiness_distribution"]["total"] == 0
    assert data["by_department"] == []
    assert data["skill_gaps"]["available"] is False
    assert data["kpis"]["threshold_percentage"]["available"] is False
    assert data["kpis"]["placement_rate"]["available"] is False


# --- EDI5 follow-up: coverage counters, dynamic reasons, by-drive, and
#     the persisted assessment_performance block -------------------------


def test_readiness_coverage_counters_track_snapshot_competencies_and_mappings():
    """The coverage block exposes the evidence funnel, never more than completed."""
    headers, email = _register_and_login("tpo")
    _, s1 = _register_and_login("student")
    _seed_attempt(_user_id(email), _user_id(s1), is_correct=True)

    cov = client.get(READINESS_URL, headers=headers).json()["coverage"]
    assert cov["completed_contexts"] == 1
    assert cov["contexts_with_snapshot"] == 1
    assert cov["contexts_with_configured_competencies"] == 1
    assert cov["contexts_with_evidence_mappings"] == 1
    # The funnel can only narrow, never widen.
    assert (
        cov["contexts_with_evidence_mappings"]
        <= cov["contexts_with_configured_competencies"]
        <= cov["contexts_with_snapshot"]
        <= cov["completed_contexts"]
    )


def test_readiness_reason_reports_missing_snapshot_with_real_counts():
    headers, email = _register_and_login("tpo")
    _, s1 = _register_and_login("student")
    _seed_attempt(_user_id(email), _user_id(s1), with_snapshot=False)

    data = client.get(READINESS_URL, headers=headers).json()
    assert data["coverage"]["contexts_with_snapshot"] == 0
    reason = data["kpis"]["average_readiness"]["reason"]
    assert "pinned blueprint snapshot" in reason
    assert "1 completed mock-drive attempt(s)" in reason


def test_readiness_reason_reports_snapshot_without_configured_competencies():
    headers, email = _register_and_login("tpo")
    _, s1 = _register_and_login("student")
    _seed_attempt(_user_id(email), _user_id(s1), with_snapshot=True)
    db = TestingSessionLocal()
    try:
        ctx = db.query(AssessmentContext).first()
        ctx.blueprint_snapshot = _snapshot([])  # snapshot with no competencies
        db.commit()
    finally:
        db.close()

    data = client.get(READINESS_URL, headers=headers).json()
    cov = data["coverage"]
    assert cov["contexts_with_snapshot"] == 1
    assert cov["contexts_with_configured_competencies"] == 0
    reason = data["kpis"]["average_readiness"]["reason"]
    assert "configure any competency" in reason
    assert "missing configured competencies" in reason


def test_readiness_reason_reports_missing_evidence_mappings():
    """Configured competencies but no mapped evidence -> mappings reason."""
    headers, email = _register_and_login("tpo")
    _, s1 = _register_and_login("student")
    sid = _user_id(s1)
    tpo_id = _user_id(email)
    db = TestingSessionLocal()
    try:
        student = db.query(User).filter(User.id == sid).first()
        drive, ctx, sess = _seed_context_session(db, student, _snapshot(COMPETENCIES))
        drive.status = "published"
        drive.created_by_id = tpo_id
        round_ = AssessmentRound(
            session_id=sess.id, round_type="aptitude", status="completed",
            score=80.0, max_questions=5,
        )
        db.add(round_)
        db.flush()
        _add_aptitude_attempt(db, round_.id, "Quant Apt", is_correct=True)
        # Deliberately no map_session_evidence call: configured, unmapped.
        ctx.status = "completed"
        db.commit()
    finally:
        db.close()

    data = client.get(READINESS_URL, headers=headers).json()
    cov = data["coverage"]
    assert cov["completed_contexts"] == 1
    assert cov["contexts_with_snapshot"] == 1
    assert cov["contexts_with_configured_competencies"] == 1
    assert cov["contexts_with_evidence_mappings"] == 0
    reason = data["kpis"]["average_readiness"]["reason"]
    assert "missing evidence mappings" in reason


def test_readiness_by_drive_separates_participants_from_contexts():
    """enrolled/completed are distinct participants; contexts are attempts."""
    headers, email = _register_and_login("tpo")
    tpo_id = _user_id(email)
    _, s1 = _register_and_login("student")
    sid = _user_id(s1)
    seeded = _seed_attempt(tpo_id, sid)
    _seed_second_context_on_same_drive(seeded["drive_id"], sid)
    _seed_activity_drive(tpo_id, status="published", company="NoTraffic")

    rows = client.get(READINESS_URL, headers=headers).json()["by_drive"]
    by_id = {r["drive_id"]: r for r in rows}

    scored = by_id[seeded["drive_id"]]
    assert scored["contexts"] == 2          # two attempt contexts
    assert scored["enrolled"] == 1          # one distinct participant
    assert scored["completed"] == 1
    assert scored["completed_contexts"] == 2
    assert scored["completion_rate"] == 100.0
    assert scored["scored_attempts"] == 1   # only the seeded round has evidence
    assert scored["scored_candidates"] == 1
    assert scored["avg_readiness"] == 60.0

    empty = next(
        r for r in rows
        if r["company_name"] == "NoTraffic"
    )
    assert empty["contexts"] == 0
    assert empty["enrolled"] == 0
    assert empty["completion_rate"] is None  # unavailable, never 0
    assert empty["avg_readiness"] is None    # no score, never a fabricated 0
    assert empty["scored_attempts"] == 0


def test_readiness_zero_participant_drive_is_reported_not_hidden():
    """Zero-participant drives stay in by_drive (frontend hides, API does not)."""
    headers, email = _register_and_login("tpo")
    _seed_activity_drive(_user_id(email), status="published", company="EmptyCo")

    rows = client.get(READINESS_URL, headers=headers).json()["by_drive"]
    empty = next(r for r in rows if r["company_name"] == "EmptyCo")
    assert empty["enrolled"] == 0
    assert empty["contexts"] == 0
    assert empty["completion_rate"] is None
    assert empty["avg_readiness"] is None
    assert empty["scored_attempts"] == 0


# --- assessment_performance block (persisted, already served) -----------


def test_assessment_performance_block_on_empty_db_is_honestly_unavailable():
    headers, _ = _register_and_login("tpo")
    ap = client.get(READINESS_URL, headers=headers).json()["assessment_performance"]

    assert ap["available"] is False
    assert "assessment_performance" in ap["note"] or "persisted" in ap["note"]
    for key in ("summary", "components", "progress", "topic_performance", "definitions"):
        assert key in ap
    assert ap["components"].keys() == {"aptitude", "coding", "interview"}
    for comp in ap["components"].values():
        assert comp["available"] is False
        assert comp["rounds_with_valid_scores"] == 0
        assert comp["reason"]  # never a silent zero
    cov = ap["summary"]["evidence_coverage"]
    assert cov["available"] is False
    assert cov["numerator"] == 0
    assert cov["denominator"] == 0
    assert cov["value"] is None
    assert cov["by_type"] == [] or all(
        r["completed_rounds"] == 0 for r in cov["by_type"]
    )
    assert ap["progress"]["available"] is False
    assert ap["progress"]["points"] == []
    assert ap["topic_performance"]["available"] is False
    assert ap["topic_performance"]["rows"] == []


def test_assessment_performance_reports_aptitude_from_graded_responses():
    headers, email = _register_and_login("tpo")
    _, s1 = _register_and_login("student")
    _seed_attempt(_user_id(email), _user_id(s1), is_correct=True)

    ap = client.get(READINESS_URL, headers=headers).json()["assessment_performance"]
    apt = ap["components"]["aptitude"]
    assert apt["available"] is True
    assert apt["completed_rounds"] == 1
    assert apt["rounds_with_results"] == 1
    assert apt["rounds_with_valid_scores"] == 1
    assert apt["candidates"] == 1
    assert apt["avg_score"] == 100.0  # 1/1 graded correct
    cov = ap["summary"]["evidence_coverage"]
    assert cov["available"] is True
    assert cov["numerator"] == 1
    assert cov["denominator"] == 1
    assert cov["value"] == 100.0
    # Aptitude is 0-100 accuracy; coding and interview stay unavailable and
    # are never averaged into the aptitude figure.
    assert ap["components"]["coding"]["available"] is False
    assert ap["components"]["interview"]["available"] is False
    scale = apt["scale"]
    assert scale["min"] == 0
    assert scale["max"] == 100


def test_assessment_performance_topic_performance_from_graded_responses():
    headers, email = _register_and_login("tpo")
    _, s1 = _register_and_login("student")
    _seed_attempt(
        _user_id(email), _user_id(s1), is_correct=True, topic="Quant Apt"
    )

    tp = client.get(
        READINESS_URL, headers=headers
    ).json()["assessment_performance"]["topic_performance"]
    assert tp["available"] is True
    assert tp["assessment_type"] == "aptitude"
    rows = {r["topic"]: r for r in tp["rows"]}
    assert "Quant Apt" in rows
    assert rows["Quant Apt"]["responses"] == 1
    assert rows["Quant Apt"]["correct"] == 1
    assert rows["Quant Apt"]["accuracy"] == 100.0


def test_assessment_performance_includes_active_contexts_unlike_readiness():
    """Performance covers active + completed contexts; readiness does not."""
    headers, email = _register_and_login("tpo")
    tpo_id = _user_id(email)
    _, s1 = _register_and_login("student")
    sid = _user_id(s1)
    drive_id = _seed_activity_drive(tpo_id, status="published", company="Mixed")
    # Active context with a completed graded round.
    db = TestingSessionLocal()
    try:
        ctx = AssessmentContext(
            mode="mock_drive", purpose="mock_drive", student_id=sid,
            mock_drive_id=drive_id, policy_id=1, status="active",
        )
        db.add(ctx)
        db.flush()
        sess = AssessmentSession(user_id=sid, context_id=ctx.id, status="in_progress")
        db.add(sess)
        db.flush()
        rnd = AssessmentRound(
            session_id=sess.id, round_type="aptitude", status="completed",
            score=80.0, max_questions=5,
        )
        db.add(rnd)
        db.flush()
        _add_aptitude_attempt(db, rnd.id, "Mixed Topic", is_correct=True)
        db.commit()
    finally:
        db.close()

    data = client.get(READINESS_URL, headers=headers).json()
    ap = data["assessment_performance"]
    assert ap["components"]["aptitude"]["completed_rounds"] == 1
    assert ap["components"]["aptitude"]["available"] is True
    assert ap["summary"]["evidence_coverage"]["numerator"] == 1
    # Readiness scoring stays unavailable: the context was never completed.
    assert data["coverage"]["completed_contexts"] == 0
    assert data["kpis"]["average_readiness"]["available"] is False


def _seed_second_context_on_same_drive(drive_id, student_id):
    """One more completed context on an existing drive for a known student."""
    db = TestingSessionLocal()
    try:
        ctx = AssessmentContext(
            mode="mock_drive", purpose="mock_drive", student_id=student_id,
            mock_drive_id=drive_id, policy_id=1, status="completed",
        )
        db.add(ctx)
        db.flush()
        db.add(AssessmentSession(
            user_id=student_id, context_id=ctx.id, status="in_progress",
        ))
        db.commit()
        return ctx.id
    finally:
        db.close()


# --- EDI5 KPI follow-up classification (attempt-level, never candidates) ---


FOLLOWUP_REASON_KEYS = (
    "missing_pinned_snapshot",
    "no_configured_competencies",
    "no_mapped_evidence",
    "no_usable_score",
    "scoring_error",
)


def _reason_total(bd):
    return sum(bd[key] for key in FOLLOWUP_REASON_KEYS)


def test_followup_breakdown_shape_on_empty_db():
    """Every follow-up category is present as an int plus one shared definition."""
    headers, _ = _register_and_login("tpo")
    cov = client.get(READINESS_URL, headers=headers).json()["coverage"]

    assert cov["candidates_with_completed_no_usable_score"] == 0
    assert cov["rounds_needing_followup"] == 0
    breakdown = cov["followup_breakdown"]
    assert breakdown["completed_attempts_needing_followup"] == 0
    assert breakdown["definition"]
    for key in FOLLOWUP_REASON_KEYS:
        assert breakdown[key] == 0, key
        assert isinstance(breakdown[key], int)


def test_followup_classifies_missing_snapshot_as_a_single_attempt():
    """A completed context without a snapshot is one missing_pinned_snapshot."""
    headers, email = _register_and_login("tpo")
    _, s1 = _register_and_login("student")
    _seed_attempt(_user_id(email), _user_id(s1), with_snapshot=False)

    cov = client.get(READINESS_URL, headers=headers).json()["coverage"]
    bd = cov["followup_breakdown"]
    assert bd["missing_pinned_snapshot"] == 1
    # Exactly one reason per attempt: the other buckets stay empty.
    assert _reason_total(bd) == 1
    assert cov["rounds_needing_followup"] == 1
    assert bd["completed_attempts_needing_followup"] == 1
    assert cov["candidates_with_completed_no_usable_score"] == 1


def test_followup_classifies_snapshot_without_competencies():
    """Pinned snapshot that configures no competencies -> config follow-up."""
    headers, email = _register_and_login("tpo")
    _, s1 = _register_and_login("student")
    _seed_attempt(
        _user_id(email), _user_id(s1),
        with_snapshot=True, snapshot_competencies=[],
    )

    bd = client.get(READINESS_URL, headers=headers).json()["coverage"]["followup_breakdown"]
    assert bd["no_configured_competencies"] == 1
    assert bd["missing_pinned_snapshot"] == 0
    assert bd["no_mapped_evidence"] == 0
    assert bd["scoring_error"] == 0


def test_followup_classifies_configured_but_unmapped_evidence():
    """Configured competencies with no mapped evidence -> no_mapped_evidence."""
    headers, email = _register_and_login("tpo")
    _, s1 = _register_and_login("student")
    sid = _user_id(s1)
    tpo_id = _user_id(email)
    db = TestingSessionLocal()
    try:
        student = db.query(User).filter(User.id == sid).first()
        drive, ctx, sess = _seed_context_session(db, student, _snapshot(COMPETENCIES))
        drive.status = "published"
        drive.created_by_id = tpo_id
        round_ = AssessmentRound(
            session_id=sess.id, round_type="aptitude", status="completed",
            score=80.0, max_questions=5,
        )
        db.add(round_)
        db.flush()
        _add_aptitude_attempt(db, round_.id, "Quant Apt", is_correct=True)
        # Deliberately no map_session_evidence call.
        ctx.status = "completed"
        db.commit()
    finally:
        db.close()

    bd = client.get(READINESS_URL, headers=headers).json()["coverage"]["followup_breakdown"]
    assert bd["no_mapped_evidence"] == 1
    assert bd["no_configured_competencies"] == 0


def test_followup_counts_attempts_not_candidates():
    """Two completed contexts for one candidate -> rounds=2, candidates=1."""
    headers, email = _register_and_login("tpo")
    tpo_id = _user_id(email)
    _, s1 = _register_and_login("student")
    sid = _user_id(s1)
    seeded = _seed_attempt(tpo_id, sid, with_snapshot=False)
    _seed_second_context_on_same_drive(seeded["drive_id"], sid)

    cov = client.get(READINESS_URL, headers=headers).json()["coverage"]
    assert cov["completed_contexts"] == 2
    assert cov["rounds_needing_followup"] == 2          # attempts, not people
    assert cov["candidates_with_completed_no_usable_score"] == 1
    assert cov["followup_breakdown"]["missing_pinned_snapshot"] == 2


def test_followup_scored_context_is_not_counted_as_needing_followup():
    headers, email = _register_and_login("tpo")
    _, s1 = _register_and_login("student")
    _seed_attempt(_user_id(email), _user_id(s1), is_correct=True)

    cov = client.get(READINESS_URL, headers=headers).json()["coverage"]
    assert cov["rounds_needing_followup"] == 0
    assert cov["candidates_with_completed_no_usable_score"] == 0
    assert _reason_total(cov["followup_breakdown"]) == 0


def test_followup_breakdown_always_sums_to_rounds_needing_followup():
    """Each needing attempt lands in exactly one bucket; buckets never overlap."""
    headers, email = _register_and_login("tpo")
    tpo_id = _user_id(email)
    _, s_ok = _register_and_login("student")
    _, s_nosnap = _register_and_login("student")
    _, s_nocomp = _register_and_login("student")

    _seed_attempt(tpo_id, _user_id(s_ok), is_correct=True)
    _seed_attempt(tpo_id, _user_id(s_nosnap), with_snapshot=False)
    _seed_attempt(tpo_id, _user_id(s_nocomp), with_snapshot=True)
    db = TestingSessionLocal()
    try:
        ctx = (
            db.query(AssessmentContext)
            .filter(AssessmentContext.status == "completed")
            .order_by(AssessmentContext.id.desc())
            .first()
        )
        ctx.blueprint_snapshot = _snapshot([])
        db.commit()
    finally:
        db.close()

    cov = client.get(READINESS_URL, headers=headers).json()["coverage"]
    bd = cov["followup_breakdown"]
    assert _reason_total(bd) == cov["rounds_needing_followup"] == 2
    assert bd["completed_attempts_needing_followup"] == 2
    assert cov["completed_contexts"] == 3


def test_candidates_needing_assessment_counts_only_completed_candidates():
    """A candidate with only an in-progress context is not "needing assessment"."""
    headers, email = _register_and_login("tpo")
    tpo_id = _user_id(email)
    _, s_completed = _register_and_login("student")
    _, s_pending = _register_and_login("student")
    seeded = _seed_attempt(tpo_id, _user_id(s_completed), with_snapshot=False)

    # A second candidate with an in-progress (never completed) context.
    db = TestingSessionLocal()
    try:
        ctx = AssessmentContext(
            mode="mock_drive", purpose="mock_drive", student_id=_user_id(s_pending),
            mock_drive_id=seeded["drive_id"], policy_id=1, status="active",
        )
        db.add(ctx)
        db.commit()
    finally:
        db.close()

    cov = client.get(READINESS_URL, headers=headers).json()["coverage"]
    assert cov["students_with_contexts"] == 2
    assert cov["completed_contexts"] == 1
    # Only the candidate who actually completed an attempt is counted.
    assert cov["candidates_with_completed_no_usable_score"] == 1
    assert cov["rounds_needing_followup"] == 1


def test_followup_fields_are_consistent_with_evidence_coverage():
    headers, email = _register_and_login("tpo")
    tpo_id = _user_id(email)
    _, s1 = _register_and_login("student")
    _seed_attempt(tpo_id, _user_id(s1), with_snapshot=False)

    data = client.get(READINESS_URL, headers=headers).json()
    cov = data["coverage"]
    score_cov = data["assessment_performance"]["summary"]["evidence_coverage"]
    # Coverage denominator counts completed rounds (attempts) in scope.
    assert score_cov["denominator"] == cov["completed_contexts"]
    assert cov["rounds_needing_followup"] == (
        cov["completed_contexts"] - cov["scored_attempts"]
        if cov["scored_attempts"] <= cov["completed_contexts"]
        else 0
    )
