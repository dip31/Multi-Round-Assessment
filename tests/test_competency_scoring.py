"""Phase 4 D1 — Competency Scoring focused tests.

Read-only derivation from persisted competency_evidence_mappings + pinned
blueprint snapshot. No scores are ever persisted; repeated reads are reproducible.

These 14 scenarios test the score_session_competencies function in
app/services/competency_scoring_service.py.

Test harness note: runs on in-memory SQLite; no application, frontend, DB,
schema, migration, or config changes were made. Tests reuse helpers from
tests/test_competency_mapping.py.
"""

from __future__ import annotations

import math
import uuid

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.models.assessment import AssessmentRound
from app.models.competency import CompetencyEvidenceMapping
from app.models.coding import CodingProblem, CodingSubmission
from app.models.user import User
from app.schemas.company_data import BlueprintCompetency, UpdateBlueprintRequest
from app.services import competency_mapping_service
from app.services.competency_scoring_service import (
    COMPETENCY_ASSESSED,
    COMPETENCY_NOT_ASSESSED,
    STATUS_FINAL,
    STATUS_PROVISIONAL,
    STATUS_UNAVAILABLE,
    score_session_competencies,
)
from app.services.assessment_blueprint_service import snapshot_company_blueprint
from app.services.company_blueprint_service import update_blueprint, approve_blueprint
from tests.test_competency_mapping import (
    _make_user,
    _competency,
    _make_blueprint,
    _snapshot,
    _seed_context_session,
    _add_aptitude_attempt,
    _coding_round,
    _add_coding_submission,
    map_session_evidence,
    TestingSessionLocal,
    engine,
    compile_jsonb_sqlite,
)


def _add_coding_submission(db, round_id, tags, score=100.0, status="accepted"):
    problem = CodingProblem(title="P", description="d", difficulty="medium")
    problem.tags_list = list(tags)
    db.add(problem)
    db.flush()
    submission = CodingSubmission(
        round_id=round_id,
        problem_id=problem.id,
        code="print(1)",
        language="python",
        status=status,
        score=score,
        execution_time=0.12,
        memory_used=2048,
    )
    db.add(submission)
    db.flush()
    return submission


# ── SQLite JSONB shim ─────────────────────────────────────────────────
@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "TEXT"


# ── Engine and session setup ──────────────────────────────────────────
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


event.listen(engine, "connect", lambda dbapi_connection, connection_record: None)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    """Create all tables and add default AssessmentPolicy once per module."""
    Base.metadata.create_all(bind=engine)
    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO assessment_policies (id, name, session_duration_minutes, "
                "round_duration_minutes, max_attempts, resume_allowed, exit_allowed, "
                "progression_mode, progression_config) VALUES "
                "(1, 'Legacy Practice Policy', 180, 30, NULL, 1, 1, 'sequential', "
                "'{\\\"rounds\\\": [\\\"aptitude\\\", \\\"coding\\\", \\\"interview\\\"]}')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO assessment_policies (id, name, session_duration_minutes, "
                "round_duration_minutes, max_attempts, resume_allowed, exit_allowed, "
                "progression_mode, progression_config) VALUES "
                "(2, 'Practice Policy', 180, 30, NULL, 1, 1, 'independent', '{}')"
            )
        )
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    """Create a fresh session for each test, isolated in a transaction."""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


# ══════════════════════════════════════════════════════════════════════
# D1 Scoring Scenarios
# ══════════════════════════════════════════════════════════════════════


def test_no_configured_competencies_unavailable(db_session):
    """No configured competencies → overall unavailable (reason: no_configured_competencies)."""
    tpo = _make_user(db_session, "tpo")
    bp = _make_blueprint(db_session, tpo)  # no competencies
    snapshot = snapshot_company_blueprint(bp)
    _, _, session = _seed_context_session(db_session, tpo, snapshot)
    result = score_session_competencies(db_session, session)
    assert result["overall_score_status"] == STATUS_UNAVAILABLE
    assert result["scoring_error"] == "no_configured_competencies"


def test_invalid_weights_not_summing_to_100_unavailable(db_session):
    """Weights that do not sum to 100 → overall unavailable + scoring_error."""
    tpo = _make_user(db_session, "tpo")
    from app.schemas.company_data import BlueprintCompetency
    competencies = [
        BlueprintCompetency(name="A", weight_pct=55, topics=["T1"]),
        BlueprintCompetency(name="B", weight_pct=30, topics=["T2"]),
    ]
    # Convert to dicts for _make_blueprint JSON storage
    comp_dicts = [{"name": c.name, "weight_pct": c.weight_pct, "topics": c.topics} for c in competencies]
    bp = _make_blueprint(db_session, tpo, competencies=comp_dicts)
    # Snapshot the blueprint - the pinned snapshot will contain the competencies
    # with weights that don't sum to 100, and the scoring service will detect this.
    snapshot = snapshot_company_blueprint(bp)
    _, _, session = _seed_context_session(db_session, tpo, snapshot)
    result = score_session_competencies(db_session, session)
    assert result["overall_score_status"] == STATUS_UNAVAILABLE
    assert result["scoring_error"].startswith("invalid_competency_weights")


def test_negative_weight_unavailable(db_session):
    """Negative weight → overall unavailable + scoring_error."""
    tpo = _make_user(db_session, "tpo")
    competencies = [
        {"name": "A", "weight_pct": -10, "topics": ["T1"]},
        {"name": "B", "weight_pct": 110, "topics": ["T2"]},
    ]
    bp = _make_blueprint(db_session, tpo, competencies=competencies)
    _, _, session = _seed_context_session(db_session, tpo, snapshot_company_blueprint(bp))
    result = score_session_competencies(db_session, session)
    assert result["overall_score_status"] == STATUS_UNAVAILABLE


def test_all_competencies_assessed_final(db_session):
    """All configured competencies have countable evidence → overall final."""
    tpo = _make_user(db_session, "tpo")
    competencies = [
        _competency("Quantitative", 60, ["Quant Apt"], cid="quant"),
        _competency("Reasoning", 40, ["Logical Reasoning"], cid="reason"),
    ]
    snapshot = _snapshot(competencies)
    _, _, session = _seed_context_session(db_session, tpo, snapshot)
    round_ = AssessmentRound(
        session_id=session.id, round_type="aptitude", status="active", max_questions=5
    )
    db_session.add(round_)
    db_session.flush()
    _add_aptitude_attempt(db_session, round_.id, "Quant Apt", is_correct=True)
    _add_aptitude_attempt(db_session, round_.id, "Logical Reasoning", is_correct=True)
    map_session_evidence(db_session, session)
    db_session.commit()
    result = score_session_competencies(db_session, session)
    assert result["overall_score_status"] == STATUS_FINAL
    assert result["overall_score"] is not None
    assert result["required_competency_count"] == 2
    assert result["assessed_competency_count"] == 2


def test_some_competencies_missing_provisional(db_session):
    """Some competencies missing countable evidence → overall provisional."""
    tpo = _make_user(db_session, "tpo")
    competencies = [
        _competency("Quantitative", 60, ["Quant Apt"], cid="quant"),
        _competency("Reasoning", 40, ["Logical Reasoning"], cid="reason"),
    ]
    snapshot = _snapshot(competencies)
    _, _, session = _seed_context_session(db_session, tpo, snapshot)
    round_ = AssessmentRound(
        session_id=session.id, round_type="aptitude", status="active", max_questions=5
    )
    db_session.add(round_)
    db_session.flush()
    _add_aptitude_attempt(db_session, round_.id, "Quant Apt", is_correct=True)
    map_session_evidence(db_session, session)
    db_session.commit()
    result = score_session_competencies(db_session, session)
    assert result["overall_score_status"] == STATUS_PROVISIONAL
    assert result["required_competency_count"] == 2
    assert result["assessed_competency_count"] == 1
    assert result["overall_score"] is not None


def test_no_competencies_assessed_unavailable(db_session):
    """No configured competencies have countable evidence → overall unavailable."""
    tpo = _make_user(db_session, "tpo")
    competencies = [_competency("Quantitative", 100, ["Quant Apt"], cid="quant")]
    snapshot = _snapshot(competencies)
    _, _, session = _seed_context_session(db_session, tpo, snapshot)
    round_ = AssessmentRound(
        session_id=session.id, round_type="aptitude", status="active", max_questions=5
    )
    db_session.add(round_)
    db_session.flush()
    _add_aptitude_attempt(db_session, round_.id, "Bad Topic", is_correct=True)
    map_session_evidence(db_session, session)
    db_session.commit()
    result = score_session_competencies(db_session, session)
    assert result["overall_score_status"] == STATUS_UNAVAILABLE


def test_aptitude_is_correct_true_one_hundred(db_session):
    """Aptitude is_correct=true → normalized_score = 100.0."""
    tpo = _make_user(db_session, "tpo")
    competencies = [_competency("Quant", 100, ["Quant Apt"], cid="q")]
    snapshot = _snapshot(competencies)
    _, _, session = _seed_context_session(db_session, tpo, snapshot)
    round_ = AssessmentRound(
        session_id=session.id, round_type="aptitude", status="active", max_questions=5
    )
    db_session.add(round_)
    db_session.flush()
    _add_aptitude_attempt(db_session, round_.id, "Quant Apt", is_correct=True)
    map_session_evidence(db_session, session)
    db_session.commit()
    result = score_session_competencies(db_session, session)
    comp = result["competencies"][0]
    assert comp["normalized_score"] == 100.0
    assert comp["status"] == COMPETENCY_ASSESSED


def test_aptitude_is_correct_false_zero(db_session):
    """Aptitude is_correct=false → normalized_score = 0.0."""
    tpo = _make_user(db_session, "tpo")
    competencies = [_competency("Quant", 100, ["Quant Apt"], cid="q")]
    snapshot = _snapshot(competencies)
    _, _, session = _seed_context_session(db_session, tpo, snapshot)
    round_ = AssessmentRound(
        session_id=session.id, round_type="aptitude", status="active", max_questions=5
    )
    db_session.add(round_)
    db_session.flush()
    _add_aptitude_attempt(db_session, round_.id, "Quant Apt", is_correct=False)
    map_session_evidence(db_session, session)
    db_session.commit()
    result = score_session_competencies(db_session, session)
    comp = result["competencies"][0]
    assert comp["normalized_score"] == 0.0
    assert comp["status"] == COMPETENCY_ASSESSED


def test_coding_accepted_score_normalized(db_session):
    """Coding submission with accepted status → normalized_score = score*100."""
    tpo = _make_user(db_session, "tpo")
    competencies = [_competency("Algorithms", 100, ["Dynamic Programming"], cid="alg")]
    snapshot = _snapshot(competencies)
    _, _, session = _seed_context_session(db_session, tpo, snapshot)
    round_ = _coding_round(db_session, session)
    _add_coding_submission(db_session, round_.id, ["Dynamic Programming"], score=0.75)
    map_session_evidence(db_session, session)
    db_session.commit()
    result = score_session_competencies(db_session, session)
    comp = result["competencies"][0]
    assert comp["normalized_score"] == 75.0
    assert comp["status"] == COMPETENCY_ASSESSED


def test_coding_internal_error_excluded(db_session):
    """Coding submission with internal_error status → excluded (None), not countable."""
    tpo = _make_user(db_session, "tpo")
    competencies = [_competency("Algorithms", 100, ["Dynamic Programming"], cid="alg")]
    snapshot = _snapshot(competencies)
    _, _, session = _seed_context_session(db_session, tpo, snapshot)
    round_ = _coding_round(db_session, session)
    _add_coding_submission(db_session, round_.id, ["Dynamic Programming"], status="internal_error", score=100.0)
    map_session_evidence(db_session, session)
    db_session.commit()
    result = score_session_competencies(db_session, session)
    comp = result["competencies"][0]
    assert comp["status"] == COMPETENCY_NOT_ASSESSED
    assert comp["normalized_score"] is None
    assert comp["evidence_count"] == 0


def test_coding_running_excluded(db_session):
    """Coding submission with running status → excluded (None), not countable."""
    tpo = _make_user(db_session, "tpo")
    competencies = [_competency("Algorithms", 100, ["Dynamic Programming"], cid="alg")]
    snapshot = _snapshot(competencies)
    _, _, session = _seed_context_session(db_session, tpo, snapshot)
    round_ = _coding_round(db_session, session)
    _add_coding_submission(db_session, round_.id, ["Dynamic Programming"], status="running", score=100.0)
    map_session_evidence(db_session, session)
    db_session.commit()
    result = score_session_competencies(db_session, session)
    comp = result["competencies"][0]
    assert comp["status"] == COMPETENCY_NOT_ASSESSED
    assert comp["normalized_score"] is None
    assert comp["evidence_count"] == 0


def test_coding_zero_score_assessed(db_session):
    """Coding submission with score=0 → assessed with normalized_score = 0.0."""
    tpo = _make_user(db_session, "tpo")
    competencies = [_competency("Algorithms", 100, ["Dynamic Programming"], cid="alg")]
    snapshot = _snapshot(competencies)
    _, _, session = _seed_context_session(db_session, tpo, snapshot)
    round_ = _coding_round(db_session, session)
    _add_coding_submission(db_session, round_.id, ["Dynamic Programming"], score=0.0)
    map_session_evidence(db_session, session)
    db_session.commit()
    result = score_session_competencies(db_session, session)
    comp = result["competencies"][0]
    assert comp["status"] == COMPETENCY_ASSESSED
    assert comp["normalized_score"] == 0.0


def test_multiple_evidence_averaged(db_session):
    """Multiple countable evidence rows for same competency → average normalized score."""
    tpo = _make_user(db_session, "tpo")
    competencies = [_competency("Quant", 100, ["Quant Apt"], cid="q")]
    snapshot = _snapshot(competencies)
    _, _, session = _seed_context_session(db_session, tpo, snapshot)
    round_ = AssessmentRound(
        session_id=session.id, round_type="aptitude", status="active", max_questions=5
    )
    db_session.add(round_)
    db_session.flush()
    _add_aptitude_attempt(db_session, round_.id, "Quant Apt", is_correct=True)
    _add_aptitude_attempt(db_session, round_.id, "Quant Apt", is_correct=False)
    map_session_evidence(db_session, session)
    db_session.commit()
    result = score_session_competencies(db_session, session)
    comp = result["competencies"][0]
    assert comp["normalized_score"] == 50.0
    assert comp["evidence_count"] == 2


def test_interview_evidence_never_mapped(db_session):
    """Interview evidence intentionally never mapped to competencies."""
    tpo = _make_user(db_session, "tpo")
    competencies = [_competency("Communication", 100, ["Quant Apt"], cid="comm")]
    snapshot = _snapshot(competencies)
    _, _, session = _seed_context_session(db_session, tpo, snapshot)
    round_ = AssessmentRound(
        session_id=session.id, round_type="aptitude", status="active", max_questions=5
    )
    db_session.add(round_)
    db_session.flush()
    from app.models.interview import InterviewSession, InterviewTurn
    interview = InterviewSession(session_id=session.id, phase="HR")
    db_session.add(interview)
    db_session.flush()
    db_session.add(
        InterviewTurn(
            interview_id=interview.id,
            turn_number=1,
            question_text="Tell me about Quant Aptitude.",
            candidate_response="...",
        )
    )
    db_session.commit()
    result = score_session_competencies(db_session, session)
    comp = result["competencies"][0]
    assert comp["status"] == COMPETENCY_NOT_ASSESSED
    assert comp["normalized_score"] is None
    assert comp["evidence_count"] == 0


def test_weighted_aggregation_correctness(db_session):
    """Overall score computed from weighted assessed competencies only."""
    tpo = _make_user(db_session, "tpo")
    competencies = [
        _competency("Quant", 60, ["Quant Apt"], cid="quant"),
        _competency("Reasoning", 40, ["Logical Reasoning"], cid="reason"),
    ]
    snapshot = _snapshot(competencies)
    _, _, session = _seed_context_session(db_session, tpo, snapshot)
    round_ = AssessmentRound(
        session_id=session.id, round_type="aptitude", status="active", max_questions=5
    )
    db_session.add(round_)
    db_session.flush()
    _add_aptitude_attempt(db_session, round_.id, "Quant Apt", is_correct=True)  # 100
    map_session_evidence(db_session, session)
    db_session.commit()
    result = score_session_competencies(db_session, session)
    assert result["overall_score_status"] == STATUS_PROVISIONAL
    assert result["overall_score"] == 60.0


def test_evidence_not_redistributed_into_provisional(db_session):
    """Missing evidence weights are not redistributed into provisional overall score."""
    tpo = _make_user(db_session, "tpo")
    competencies = [
        _competency("Quant", 60, ["Quant Apt"], cid="quant"),
        _competency("Reasoning", 40, ["Logical Reasoning"], cid="reason"),
    ]
    snapshot = _snapshot(competencies)
    _, _, session = _seed_context_session(db_session, tpo, snapshot)
    round_ = AssessmentRound(
        session_id=session.id, round_type="aptitude", status="active", max_questions=5
    )
    db_session.add(round_)
    db_session.flush()
    _add_aptitude_attempt(db_session, round_.id, "Quant Apt", is_correct=True)  # Quant = 100
    map_session_evidence(db_session, session)
    db_session.commit()
    result = score_session_competencies(db_session, session)
    assert result["overall_score_status"] == STATUS_PROVISIONAL
    assert result["overall_score"] == 60.0  # NOT 100.0 (weights not redistributed)


def test_scoring_policy_version_constant(db_session):
    """Scoring policy version exposed for reproducibility."""
    tpo = _make_user(db_session, "tpo")
    competencies = [_competency("Quant", 100, ["Quant Apt"], cid="q")]
    snapshot = _snapshot(competencies)
    _, _, session = _seed_context_session(db_session, tpo, snapshot)
    round_ = AssessmentRound(
        session_id=session.id, round_type="aptitude", status="active", max_questions=5
    )
    db_session.add(round_)
    db_session.flush()
    _add_aptitude_attempt(db_session, round_.id, "Quant Apt", is_correct=True)
    map_session_evidence(db_session, session)
    db_session.commit()
    result = score_session_competencies(db_session, session)
    assert result["scoring_policy_version"] == "d1-v1"


def test_pinned_snapshot_immutability(db_session):
    """Live blueprint change does not affect pinned snapshot scoring."""
    tpo = _make_user(db_session, "tpo")
    original = [_competency("Quant", 100, ["Quant Apt"], cid="quant")]
    bp = _make_blueprint(db_session, tpo, competencies=original)
    pinned = snapshot_company_blueprint(bp)
    _, _, session = _seed_context_session(db_session, tpo, pinned)
    round_ = AssessmentRound(
        session_id=session.id, round_type="aptitude", status="active", max_questions=5
    )
    db_session.add(round_)
    db_session.flush()
    _add_aptitude_attempt(db_session, round_.id, "Quant Apt", is_correct=True)
    map_session_evidence(db_session, session)
    db_session.commit()

    # TPO changes the live blueprint
    from app.schemas.company_data import UpdateBlueprintRequest, BlueprintCompetency
    update_blueprint(
        db_session,
        bp.company_name,
        bp.target_role,
        UpdateBlueprintRequest(
            competencies=[
                BlueprintCompetency(name="Reasoning", weight_pct=100, topics=["Logical"])
            ]
        ),
        tpo.id,
    )

    # Re-score using the same session - should still use pinned snapshot
    result = score_session_competencies(db_session, session)
    comp_names = [c["competency_name"] for c in result["competencies"]]
    assert "Quant" in comp_names
    assert "Reasoning" not in comp_names


def test_missing_competencies_listed(db_session):
    """Missing competency names are listed in the result."""
    tpo = _make_user(db_session, "tpo")
    competencies = [
        _competency("Quant", 60, ["Quant Apt"], cid="quant"),
        _competency("Reasoning", 40, ["Logical Reasoning"], cid="reason"),
    ]
    snapshot = _snapshot(competencies)
    _, _, session = _seed_context_session(db_session, tpo, snapshot)
    round_ = AssessmentRound(
        session_id=session.id, round_type="aptitude", status="active", max_questions=5
    )
    db_session.add(round_)
    db_session.flush()
    _add_aptitude_attempt(db_session, round_.id, "Quant Apt", is_correct=True)
    map_session_evidence(db_session, session)
    db_session.commit()
    result = score_session_competencies(db_session, session)
    assert "Reasoning" in result["missing_competencies"]
    assert "Quant" not in result["missing_competencies"]


def test_empty_competencies_returns_unavailable(db_session):
    """Empty competencies list → overall unavailable."""
    tpo = _make_user(db_session, "tpo")
    bp = _make_blueprint(db_session, tpo)  # no competencies
    snapshot = snapshot_company_blueprint(bp)
    _, _, session = _seed_context_session(db_session, tpo, snapshot)
    result = score_session_competencies(db_session, session)
    assert result["overall_score_status"] == STATUS_UNAVAILABLE
    assert result["scoring_error"] == "no_configured_competencies"


def test_coding_score_clamped_0_to_100(db_session):
    """Coding score clamped to [0, 100] even if raw fraction outside range."""
    tpo = _make_user(db_session, "tpo")
    competencies = [_competency("Algorithms", 100, ["Dynamic Programming"], cid="alg")]
    snapshot = _snapshot(competencies)
    _, _, session = _seed_context_session(db_session, tpo, snapshot)
    round_ = _coding_round(db_session, session)
    _add_coding_submission(db_session, round_.id, ["Dynamic Programming"], score=1.5)
    map_session_evidence(db_session, session)
    db_session.commit()
    result = score_session_competencies(db_session, session)
    comp = result["competencies"][0]
    assert comp["normalized_score"] == 100.0


def test_coding_negative_score_clamped(db_session):
    """Coding negative raw score clamped to 0.0."""
    tpo = _make_user(db_session, "tpo")
    competencies = [_competency("Algorithms", 100, ["Dynamic Programming"], cid="alg")]
    snapshot = _snapshot(competencies)
    _, _, session = _seed_context_session(db_session, tpo, snapshot)
    round_ = _coding_round(db_session, session)
    _add_coding_submission(db_session, round_.id, ["Dynamic Programming"], score=-0.5)
    map_session_evidence(db_session, session)
    db_session.commit()
    result = score_session_competencies(db_session, session)
    comp = result["competencies"][0]
    assert comp["normalized_score"] == 0.0
