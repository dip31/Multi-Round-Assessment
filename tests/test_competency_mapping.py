"""Additive competency foundation tests (EDI5 Phase 4C Part 4).

Stage 1 - competency configuration on the blueprint:
  1. Legacy blueprints without competencies remain valid / unchanged.
  2. A configured competency set is persisted and survives approval + snapshot.
  3. Invalid competency configuration is rejected (weights, names, topics).

Stage 2 - evidence-to-competency mapping foundation:
  4. Only explicitly associated topics are mapped.
  5. Unmatched / taxonomy-style evidence gets no guessed mapping and no score.
  6. Reprocessing is idempotent (no duplicate mappings).
  7. Coding evidence maps via explicit problem tags.
  8. Candidate / session isolation is preserved.
  9. Existing pinned snapshots keep their original configuration after a live
     blueprint change, and no competency score is ever persisted.

Service-level tests over an in-memory SQLite database (never the live dev DB).
"""

import copy
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
from app.models.aptitude import (
    AptitudeAttempt,
    AptitudeQuestion,
    AptitudeRoundQuestion,
    AptitudeTopic,
)
from app.models.assessment import AssessmentRound, AssessmentSession
from app.models.assessment_context import AssessmentContext, AssessmentPolicy
from app.models.coding import CodingProblem, CodingSubmission
from app.models.company_data import CompanyBlueprint, CompanyPattern
from app.models.competency import CompetencyEvidenceMapping
from app.models.interview import InterviewSession, InterviewTurn
from app.models.mock_drive import MockDrive
from app.models.profile import StudentProfile
from app.models.user import User
from app.schemas.company_data import (
    BlueprintCompetency,
    UpdateBlueprintRequest,
    validate_competency_configuration,
)
from app.services import competency_mapping_service
from app.services.assessment_blueprint_service import snapshot_company_blueprint
from app.services.assessment_context_service import DEFAULT_PRACTICE_POLICY_ID
from app.services.company_blueprint_service import (
    approve_blueprint,
    generate_blueprint_from_pattern,
    update_blueprint,
)
from app.services.competency_mapping_service import (
    APTITUDE_EVIDENCE_TYPE,
    CODING_EVIDENCE_TYPE,
    MAPPING_STATUS_COMPLETED,
    MAPPING_STATUS_FAILED,
    MAPPING_STATUS_NOT_APPLICABLE,
    MAPPING_STATUS_PENDING,
    configured_competencies,
    finalize_session_competency_mapping,
    has_configured_competencies,
    map_session_evidence,
    match_competency_for_topic,
    reprocess_competency_mapping,
)
from app.services.mock_drive_service import (
    _finalize_mock_drive,
    _opportunistic_competency_mapping_retry,
    reprocess_mock_drive_competency_mappings,
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


@pytest.fixture
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


# ── Helpers ───────────────────────────────────────────────────────────

def _make_user(db, role="student"):
    user = User(
        name=f"{role.title()} {uuid.uuid4().hex[:6]}",
        email=f"{role}_{uuid.uuid4().hex[:8]}@college.edu",
        role=role,
        password_hash="pw",
    )
    db.add(user)
    db.flush()
    if role == "student":
        db.add(
            StudentProfile(
                user_id=user.id,
                cgpa=8.0,
                backlogs_count=0,
                department="Computer Science",
            )
        )
        db.flush()
    return user


def _competency(name, weight, topics, cid=None):
    return {"id": cid, "name": name, "weight_pct": weight, "topics": list(topics)}


def _make_blueprint(db, tpo, competencies=None, company=None, role="Engineer"):
    company = company or f"Comp{uuid.uuid4().hex[:6]}"
    blueprint_data = {
        "company_name": company,
        "target_role": role,
        "status": "approved",
        "version": 1,
        "rounds": [
            {"round_type": "aptitude", "round_order": 1, "question_count": 5},
            {"round_type": "coding", "round_order": 2, "question_count": 2},
        ],
    }
    if competencies is not None:
        blueprint_data["competencies"] = competencies
    bp = CompanyBlueprint(
        company_name=company,
        target_role=role,
        status="approved",
        version=1,
        blueprint_data=blueprint_data,
        confidence_level="medium",
        evidence_sources_count=0,
        created_by_id=tpo.id,
    )
    db.add(bp)
    db.flush()
    return bp


def _make_approved_pattern(db, tpo, company, role="Engineer", rounds=None):
    """Create an approved, evidence-derived pattern usable for recalculation.

    A non-LLM provenance keeps the standard blueprint generation path (the LLM
    path deliberately refuses to overwrite an existing blueprint with 409).
    """
    pattern_data = {
        "review_status": "approved",
        "confidence_level": "medium",
        "assessment_rounds": list(rounds or ["aptitude"]),
        "source_provenance": {
            "classification": "company_specific_historical_evidence",
            "selection_status": "role_compatible_evidence_found",
            "empirical_source_count": 1,
        },
    }
    pattern = CompanyPattern(
        company_name=company,
        target_role=role,
        pattern_data=pattern_data,
        source_count=1,
        created_by_id=tpo.id,
    )
    db.add(pattern)
    db.flush()
    return pattern


def _snapshot(competencies, version=1):
    return {
        "status": "approved",
        "blueprint_id": 1,
        "blueprint_version": version,
        "blueprint_data": {
            "rounds": [
                {"round_type": "aptitude", "round_order": 1, "question_count": 5},
                {"round_type": "coding", "round_order": 2, "question_count": 2},
            ],
            "competencies": competencies,
        },
    }


def _seed_context_session(db, student, snapshot, drive=None):
    if drive is None:
        drive = MockDrive(
            company_name=f"Drive {uuid.uuid4().hex[:6]}",
            target_role="Engineer",
            status="published",
            minimum_cgpa=0.0,
            maximum_backlogs=100,
            eligible_branches=[],
            selected_rounds={"aptitude": True, "coding": True},
            round_configurations={},
            blueprint_snapshot=snapshot,
            created_by_id=student.id,
        )
        db.add(drive)
        db.flush()
    ctx = AssessmentContext(
        mode="mock_drive",
        purpose="mock_drive",
        student_id=student.id,
        company_name=drive.company_name,
        target_role=drive.target_role,
        policy_id=DEFAULT_PRACTICE_POLICY_ID,
        mock_drive_id=drive.id,
        blueprint_snapshot=snapshot,
        status="active",
    )
    db.add(ctx)
    db.flush()
    session = AssessmentSession(
        user_id=student.id, context_id=ctx.id, status="in_progress"
    )
    db.add(session)
    db.flush()
    return drive, ctx, session


def _get_or_create_topic(db, name):
    topic = db.query(AptitudeTopic).filter(AptitudeTopic.name == name).first()
    if topic is None:
        topic = AptitudeTopic(name=name)
        db.add(topic)
        db.flush()
    return topic


def _add_aptitude_attempt(db, round_id, topic_name, is_correct=True):
    topic = _get_or_create_topic(db, topic_name)
    question = AptitudeQuestion(
        question_text=f"Q {topic_name}",
        option_a="1",
        option_b="2",
        option_c="3",
        option_d="4",
        correct_option="A",
        difficulty="easy",
        topic_id=topic.id,
    )
    db.add(question)
    db.flush()
    attempt = AptitudeAttempt(
        round_id=round_id,
        question_id=question.id,
        attempt_number=1,
        selected_option="A",
        is_correct=is_correct,
        response_time=3.5,
        difficulty="easy",
        reward=1.0,
    )
    db.add(attempt)
    db.flush()
    return attempt


def _add_coding_submission(db, round_id, tags):
    problem = CodingProblem(title="P", description="d", difficulty="medium")
    problem.tags_list = list(tags)
    db.add(problem)
    db.flush()
    submission = CodingSubmission(
        round_id=round_id,
        problem_id=problem.id,
        code="print(1)",
        language="python",
        status="accepted",
        score=100.0,
        execution_time=0.12,
        memory_used=2048,
    )
    db.add(submission)
    db.flush()
    return submission


def _aptitude_round(db, session):
    round_ = AssessmentRound(
        session_id=session.id, round_type="aptitude", status="active", max_questions=5
    )
    db.add(round_)
    db.flush()
    return round_


def _coding_round(db, session):
    round_ = AssessmentRound(
        session_id=session.id, round_type="coding", status="active", max_questions=2
    )
    db.add(round_)
    db.flush()
    return round_


# ══════════════════════════════════════════════════════════════════════
# Stage 1 - competency configuration
# ══════════════════════════════════════════════════════════════════════


def test_legacy_blueprint_without_competencies_is_valid(db_session):
    tpo = _make_user(db_session, "tpo")
    bp = _make_blueprint(db_session, tpo)
    assert "competencies" not in bp.blueprint_data
    snapshot = snapshot_company_blueprint(bp)
    assert configured_competencies(snapshot) == []

    # Editing an unrelated field must not inject or touch a competency block.
    updated = update_blueprint(
        db_session,
        bp.company_name,
        bp.target_role,
        UpdateBlueprintRequest(overall_difficulty="hard"),
        tpo.id,
    )
    assert updated.blueprint_data.get("overall_difficulty") == "hard"
    assert updated.version == 2
    assert "competencies" not in updated.blueprint_data


def test_configured_competencies_persist_through_approval_and_snapshot(db_session):
    tpo = _make_user(db_session, "tpo")
    bp = _make_blueprint(db_session, tpo)
    historical_snapshot = snapshot_company_blueprint(bp)
    payload = UpdateBlueprintRequest(
        competencies=[
            BlueprintCompetency(
                id="quant", name="Quantitative", weight_pct=60,
                topics=["Quantitative Aptitude"],
            ),
            BlueprintCompetency(
                name="Reasoning", weight_pct=40, topics=["Logical Reasoning"]
            ),
        ]
    )

    updated = update_blueprint(
        db_session, bp.company_name, bp.target_role, payload, tpo.id
    )
    assert updated.version == 2
    assert updated.blueprint_data["version"] == 2
    assert historical_snapshot["blueprint_version"] == 1
    assert configured_competencies(historical_snapshot) == []
    stored = updated.blueprint_data["competencies"]
    assert [c["name"] for c in stored] == ["Quantitative", "Reasoning"]
    assert [c["weight_pct"] for c in stored] == [60.0, 40.0]
    assert stored[0]["id"] == "quant"

    snapshot = snapshot_company_blueprint(updated)
    assert snapshot["blueprint_version"] == 2
    assert snapshot["blueprint_data"]["competencies"] == stored
    assert [c["name"] for c in configured_competencies(snapshot)] == [
        "Quantitative",
        "Reasoning",
    ]

    approved = approve_blueprint(
        db_session, bp.company_name, bp.target_role, "approved", "ok", tpo.id
    )
    assert approved.blueprint_data["competencies"] == stored


def test_invalid_competency_configuration_is_rejected():
    def build(competencies):
        return UpdateBlueprintRequest(competencies=competencies)

    # Weights that do not sum to 100%.
    with pytest.raises(ValidationError):
        build([
            BlueprintCompetency(name="A", weight_pct=50, topics=["T1"]),
            BlueprintCompetency(name="B", weight_pct=30, topics=["T2"]),
        ])

    # Non-positive / out-of-range weights.
    with pytest.raises(ValidationError):
        BlueprintCompetency(name="A", weight_pct=0, topics=["T1"])
    with pytest.raises(ValidationError):
        BlueprintCompetency(name="A", weight_pct=150, topics=["T1"])

    # Blank / duplicate topics and blank names.
    with pytest.raises(ValidationError):
        BlueprintCompetency(name="A", weight_pct=100, topics=["  "])
    with pytest.raises(ValidationError):
        BlueprintCompetency(name="A", weight_pct=100, topics=["T1", "t1"])
    with pytest.raises(ValidationError):
        BlueprintCompetency(name="   ", weight_pct=100, topics=["T1"])

    # Duplicate competency names / ids across the set.
    with pytest.raises(ValidationError):
        build([
            BlueprintCompetency(name="Dup", weight_pct=50, topics=["T1"]),
            BlueprintCompetency(name="dup", weight_pct=50, topics=["T2"]),
        ])
    with pytest.raises(ValidationError):
        build([
            BlueprintCompetency(id="x", name="A", weight_pct=50, topics=["T1"]),
            BlueprintCompetency(id="X", name="B", weight_pct=50, topics=["T2"]),
        ])

    # Empty configuration is not a valid competency set.
    with pytest.raises(ValidationError):
        build([])


def test_validate_helper_accepts_valid_sum():
    competencies = [
        BlueprintCompetency(name="A", weight_pct=70, topics=["T1"]),
        BlueprintCompetency(name="B", weight_pct=30, topics=["T2"]),
    ]
    assert validate_competency_configuration(competencies) == competencies


# ══════════════════════════════════════════════════════════════════════
# Stage 2 - evidence mapping
# ══════════════════════════════════════════════════════════════════════


def test_only_explicitly_associated_topics_are_mapped(db_session):
    student = _make_user(db_session)
    competencies = [_competency("Quantitative", 100, ["Quantitative Aptitude"])]
    snapshot = _snapshot(competencies)
    _, _, session = _seed_context_session(db_session, student, snapshot)
    round_ = _aptitude_round(db_session, session)

    matched = _add_aptitude_attempt(db_session, round_.id, "Quantitative Aptitude")
    _add_aptitude_attempt(db_session, round_.id, "Logical Reasoning")
    db_session.commit()

    created = map_session_evidence(db_session, session)

    assert len(created) == 1
    mapping = created[0]
    assert mapping.evidence_type == APTITUDE_EVIDENCE_TYPE
    assert mapping.evidence_id == matched.id
    assert mapping.competency_name == "Quantitative"
    assert mapping.competency_id == "Quantitative"
    assert mapping.candidate_id == student.id
    assert mapping.session_id == session.id
    assert mapping.source == "aptitude"
    assert mapping.blueprint_version == 1
    assert mapping.raw_metric["topic"] == "Quantitative Aptitude"


def test_unmatched_evidence_gets_no_guessed_mapping(db_session):
    student = _make_user(db_session)
    competencies = [_competency("DSA", 100, ["Dynamic Programming"])]
    snapshot = _snapshot(competencies)
    _, _, session = _seed_context_session(db_session, student, snapshot)

    # Taxonomy-category-style evidence must not be matched by category.
    assert match_competency_for_topic(competencies, "DSA") is None
    assert match_competency_for_topic(competencies, "Data Structures") is None
    assert match_competency_for_topic(competencies, None) is None

    apt_round = _aptitude_round(db_session, session)
    _add_aptitude_attempt(db_session, apt_round.id, "Graphs & Graph Algorithms")
    db_session.commit()

    created = map_session_evidence(db_session, session)
    assert created == []
    assert db_session.query(CompetencyEvidenceMapping).count() == 0


def test_reprocessing_does_not_create_duplicates(db_session):
    student = _make_user(db_session)
    snapshot = _snapshot([_competency("Quantitative", 100, ["Quant Apt"])])
    _, _, session = _seed_context_session(db_session, student, snapshot)
    round_ = _aptitude_round(db_session, session)
    _add_aptitude_attempt(db_session, round_.id, "Quant Apt")
    _add_aptitude_attempt(db_session, round_.id, "Quant Apt")
    db_session.commit()

    first = map_session_evidence(db_session, session)
    assert len(first) == 2
    second = map_session_evidence(db_session, session)
    assert second == []
    assert db_session.query(CompetencyEvidenceMapping).count() == 2


def test_coding_evidence_maps_by_explicit_tags(db_session):
    student = _make_user(db_session)
    snapshot = _snapshot([
        _competency("Algorithms", 60, ["Dynamic Programming"]),
        _competency("Programming", 40, ["Programming Languages"]),
    ])
    _, _, session = _seed_context_session(db_session, student, snapshot)
    round_ = _coding_round(db_session, session)
    submission = _add_coding_submission(
        db_session, round_.id, ["Dynamic Programming", "Arrays"]
    )
    db_session.commit()

    created = map_session_evidence(db_session, session)
    assert len(created) == 1
    mapping = created[0]
    assert mapping.evidence_type == CODING_EVIDENCE_TYPE
    assert mapping.evidence_id == submission.id
    assert mapping.competency_name == "Algorithms"
    assert mapping.raw_metric["status"] == "accepted"
    assert mapping.raw_metric["score"] == 100.0  # raw submission metric, not a competency score


def test_ambiguous_topic_is_left_unmapped(db_session):
    student = _make_user(db_session)
    competencies = [
        _competency("A", 50, ["Shared Topic"]),
        _competency("B", 50, ["Shared Topic"]),
    ]
    assert match_competency_for_topic(competencies, "Shared Topic") is None
    snapshot = _snapshot(competencies)
    _, _, session = _seed_context_session(db_session, student, snapshot)
    round_ = _aptitude_round(db_session, session)
    _add_aptitude_attempt(db_session, round_.id, "Shared Topic")
    db_session.commit()

    assert map_session_evidence(db_session, session) == []


def test_candidate_isolation_is_preserved(db_session):
    student_a = _make_user(db_session)
    student_b = _make_user(db_session)
    student_c = _make_user(db_session)
    competencies = [_competency("Quantitative", 100, ["Quantitative Aptitude"])]

    _, _, session_a = _seed_context_session(db_session, student_a, _snapshot(competencies))
    _, _, session_b = _seed_context_session(db_session, student_b, _snapshot(competencies))
    _, _, session_c = _seed_context_session(db_session, student_c, _snapshot([]))

    round_a = _aptitude_round(db_session, session_a)
    round_b = _aptitude_round(db_session, session_b)
    round_c = _aptitude_round(db_session, session_c)
    attempt_a = _add_aptitude_attempt(db_session, round_a.id, "Quantitative Aptitude")
    attempt_b = _add_aptitude_attempt(db_session, round_b.id, "Quantitative Aptitude")
    _add_aptitude_attempt(db_session, round_c.id, "Quantitative Aptitude")
    db_session.commit()

    created_a = map_session_evidence(db_session, session_a)
    created_b = map_session_evidence(db_session, session_b)
    created_c = map_session_evidence(db_session, session_c)

    assert len(created_a) == 1 and created_a[0].session_id == session_a.id
    assert len(created_b) == 1 and created_b[0].session_id == session_b.id
    assert created_c == []  # no configured competencies -> never mapped

    rows = db_session.query(CompetencyEvidenceMapping).all()
    a_rows = [r for r in rows if r.candidate_id == student_a.id]
    b_rows = [r for r in rows if r.candidate_id == student_b.id]
    assert {r.evidence_id for r in a_rows} == {attempt_a.id}
    assert {r.evidence_id for r in b_rows} == {attempt_b.id}
    assert all(r.session_id == session_a.id for r in a_rows)
    assert all(r.session_id == session_b.id for r in b_rows)
    # No mapping may cross candidates or sessions.
    assert not any(
        r.candidate_id == student_a.id and r.session_id != session_a.id for r in rows
    )


def test_no_competency_score_is_persisted(db_session):
    columns = set(CompetencyEvidenceMapping.__table__.columns.keys())
    assert "score" not in columns
    assert "competency_score" not in columns
    assert not hasattr(CompetencyEvidenceMapping(), "score")

    student = _make_user(db_session)
    snapshot = _snapshot([_competency("Quantitative", 100, ["Quant Apt"])])
    _, _, session = _seed_context_session(db_session, student, snapshot)
    round_ = _aptitude_round(db_session, session)
    _add_aptitude_attempt(db_session, round_.id, "Quant Apt")
    db_session.commit()

    mapping = map_session_evidence(db_session, session)[0]
    assert "competency_score" not in mapping.raw_metric
    assert set(mapping.raw_metric) == {
        "topic", "is_correct", "response_time", "difficulty", "reward", "attempt_number",
    }


def test_pinned_snapshot_keeps_original_config_after_live_change(db_session):
    tpo = _make_user(db_session, "tpo")
    student = _make_user(db_session)
    original = [_competency("Quantitative", 100, ["Quantitative Aptitude"])]
    bp = _make_blueprint(db_session, tpo, competencies=original)

    pinned = snapshot_company_blueprint(bp)
    _, ctx, session = _seed_context_session(db_session, student, pinned)
    round_ = _aptitude_round(db_session, session)
    _add_aptitude_attempt(db_session, round_.id, "Quantitative Aptitude")
    db_session.commit()

    # TPO changes the live blueprint's competencies afterwards.
    update_blueprint(
        db_session,
        bp.company_name,
        bp.target_role,
        UpdateBlueprintRequest(
            competencies=[
                BlueprintCompetency(
                    name="Reasoning", weight_pct=100, topics=["Logical Reasoning"]
                )
            ]
        ),
        tpo.id,
    )

    # The pinned snapshot is immutable and mapping still uses the pinned config.
    db_session.refresh(ctx)
    assert [c["name"] for c in ctx.blueprint_snapshot["blueprint_data"]["competencies"]] == [
        "Quantitative"
    ]
    created = map_session_evidence(db_session, session)
    assert len(created) == 1
    assert created[0].competency_name == "Quantitative"
    assert created[0].blueprint_version == 1


# ══════════════════════════════════════════════════════════════════════
# Follow-up: recalculation preservation + validation error handling
# ══════════════════════════════════════════════════════════════════════


def test_forced_recalculation_preserves_competencies_exactly(db_session):
    tpo = _make_user(db_session, "tpo")
    original = [
        _competency("Quantitative", 60, ["Quantitative Aptitude"], cid="quant"),
        _competency("Reasoning", 40, ["Logical Reasoning"], cid="reason"),
    ]
    bp = _make_blueprint(db_session, tpo, competencies=copy.deepcopy(original))
    _make_approved_pattern(db_session, tpo, bp.company_name, bp.target_role)

    recalced = generate_blueprint_from_pattern(
        db_session, bp.company_name, bp.target_role, tpo.id, force=True
    )

    # Same row, new version, reset to draft — but competencies intact verbatim.
    assert recalced.id == bp.id
    assert recalced.version == 2
    assert recalced.status == "draft"
    assert recalced.blueprint_data["competencies"] == original
    assert [c["id"] for c in recalced.blueprint_data["competencies"]] == ["quant", "reason"]
    assert [c["weight_pct"] for c in recalced.blueprint_data["competencies"]] == [60, 40]

    # Preserved through approval as well.
    approved = approve_blueprint(
        db_session, bp.company_name, bp.target_role, "approved", "ok", tpo.id
    )
    assert approved.blueprint_data["competencies"] == original


def test_forced_recalculation_does_not_mutate_pinned_snapshots(db_session):
    tpo = _make_user(db_session, "tpo")
    student = _make_user(db_session)
    original = [_competency("Quantitative", 100, ["Quantitative Aptitude"], cid="quant")]
    bp = _make_blueprint(db_session, tpo, competencies=copy.deepcopy(original))
    _make_approved_pattern(db_session, tpo, bp.company_name, bp.target_role)

    pinned = snapshot_company_blueprint(bp)
    pinned_copy = copy.deepcopy(pinned)
    _, ctx, _ = _seed_context_session(db_session, student, pinned)

    # The live blueprint's config changes, then the pattern is recalculated.
    update_blueprint(
        db_session,
        bp.company_name,
        bp.target_role,
        UpdateBlueprintRequest(
            competencies=[
                BlueprintCompetency(
                    name="Reasoning", weight_pct=100, topics=["Logical Reasoning"]
                )
            ]
        ),
        tpo.id,
    )
    recalced = generate_blueprint_from_pattern(
        db_session, bp.company_name, bp.target_role, tpo.id, force=True
    )

    # Recalculation preserved the (updated) live config ...
    assert recalced.blueprint_data["competencies"][0]["name"] == "Reasoning"

    # ... while the already-pinned snapshot is untouched.
    db_session.refresh(ctx)
    assert ctx.blueprint_snapshot == pinned_copy
    assert ctx.blueprint_snapshot["blueprint_data"]["competencies"][0]["name"] == "Quantitative"


def test_new_blueprint_generation_without_competencies_is_unchanged(db_session):
    tpo = _make_user(db_session, "tpo")
    company = f"Fresh{uuid.uuid4().hex[:6]}"
    _make_approved_pattern(db_session, tpo, company, role="Engineer")

    created = generate_blueprint_from_pattern(
        db_session, company, "Engineer", tpo.id, force=False
    )
    assert "competencies" not in created.blueprint_data

    # Recalculation still introduces no competency block for an unconfigured set.
    recalced = generate_blueprint_from_pattern(
        db_session, company, "Engineer", tpo.id, force=True
    )
    assert recalced.id == created.id
    assert recalced.version == 2
    assert "competencies" not in recalced.blueprint_data


def test_omitted_and_null_competencies_preserve_existing(db_session):
    tpo = _make_user(db_session, "tpo")
    original = [_competency("Quantitative", 100, ["Quantitative Aptitude"], cid="quant")]
    bp = _make_blueprint(db_session, tpo, competencies=copy.deepcopy(original))

    # Omitted -> preserved.
    omitted = update_blueprint(
        db_session,
        bp.company_name,
        bp.target_role,
        UpdateBlueprintRequest(overall_difficulty="hard"),
        tpo.id,
    )
    assert omitted.blueprint_data["competencies"] == original

    # Explicit null -> documented policy: preserve, never silently clear.
    explicit_null = update_blueprint(
        db_session,
        bp.company_name,
        bp.target_role,
        UpdateBlueprintRequest(blueprint_data={"competencies": None}),
        tpo.id,
    )
    assert explicit_null.blueprint_data["competencies"] == original


def test_empty_competencies_via_blueprint_data_is_rejected(db_session):
    tpo = _make_user(db_session, "tpo")
    original = [_competency("A", 100, ["T1"])]
    bp = _make_blueprint(db_session, tpo, competencies=copy.deepcopy(original))

    with pytest.raises(HTTPException) as exc:
        update_blueprint(
            db_session,
            bp.company_name,
            bp.target_role,
            UpdateBlueprintRequest(blueprint_data={"competencies": []}),
            tpo.id,
        )
    assert exc.value.status_code == 422
    # The rejected edit leaves the stored configuration intact.
    db_session.refresh(bp)
    assert bp.blueprint_data["competencies"] == original


@pytest.mark.parametrize("bad", [
    # Weights do not sum to 100.
    [{"name": "A", "weight_pct": 50, "topics": ["T1"]},
     {"name": "B", "weight_pct": 30, "topics": ["T2"]}],
    # Blank name.
    [{"name": "   ", "weight_pct": 100, "topics": ["T1"]}],
    # No topics.
    [{"name": "A", "weight_pct": 100, "topics": []}],
    # Duplicate topics.
    [{"name": "A", "weight_pct": 100, "topics": ["T1", "t1"]}],
    # Non-positive weight.
    [{"name": "A", "weight_pct": 0, "topics": ["T1"]}],
    # Malformed shapes.
    "not-a-list",
    {"name": "A"},
])
def test_invalid_competencies_via_blueprint_data_return_422_not_500(db_session, bad):
    tpo = _make_user(db_session, "tpo")
    company = f"Inv{uuid.uuid4().hex[:6]}"
    bp = _make_blueprint(db_session, tpo, company=company)

    with pytest.raises(HTTPException) as exc:
        update_blueprint(
            db_session,
            bp.company_name,
            bp.target_role,
            UpdateBlueprintRequest(blueprint_data={"competencies": bad}),
            tpo.id,
        )
    assert exc.value.status_code == 422
    assert "competency" in str(exc.value.detail).lower()


# ══════════════════════════════════════════════════════════════════════
# Follow-up: production activation via mock-drive finalization
# ══════════════════════════════════════════════════════════════════════


def test_mock_drive_finalization_invokes_competency_mapping(db_session):
    student = _make_user(db_session)
    competencies = [_competency("Quantitative", 100, ["Quantitative Aptitude"])]
    drive, ctx, session = _seed_context_session(db_session, student, _snapshot(competencies))
    round_ = _aptitude_round(db_session, session)
    matched = _add_aptitude_attempt(db_session, round_.id, "Quantitative Aptitude")
    _add_aptitude_attempt(db_session, round_.id, "Logical Reasoning")
    db_session.commit()

    _finalize_mock_drive(db_session, drive, ctx, session)

    # Completion side effects are preserved.
    db_session.refresh(session)
    db_session.refresh(ctx)
    assert session.status == "completed"
    assert ctx.status == "completed"

    # Only the explicitly matched evidence is mapped.
    mappings = db_session.query(CompetencyEvidenceMapping).all()
    assert len(mappings) == 1
    mapping = mappings[0]
    assert mapping.evidence_id == matched.id
    assert mapping.evidence_type == APTITUDE_EVIDENCE_TYPE
    assert mapping.candidate_id == student.id
    assert mapping.session_id == session.id
    assert mapping.round_id == round_.id
    assert mapping.competency_name == "Quantitative"


def test_repeated_mock_drive_finalization_creates_no_duplicates(db_session):
    student = _make_user(db_session)
    competencies = [_competency("Quantitative", 100, ["Quantitative Aptitude"])]
    drive, ctx, session = _seed_context_session(db_session, student, _snapshot(competencies))
    round_ = _aptitude_round(db_session, session)
    matched = _add_aptitude_attempt(db_session, round_.id, "Quantitative Aptitude")
    db_session.commit()

    _finalize_mock_drive(db_session, drive, ctx, session)
    _finalize_mock_drive(db_session, drive, ctx, session)
    _finalize_mock_drive(db_session, drive, ctx, session)

    rows = db_session.query(CompetencyEvidenceMapping).all()
    assert len(rows) == 1
    assert rows[0].evidence_id == matched.id


def test_mapping_failure_does_not_block_assessment_completion(monkeypatch):
    # Uses a real-commit session (not the rollback-based ``db_session`` fixture)
    # so the completion commit and the mapping-failure rollback behave as they
    # do in production.
    db = TestingSessionLocal()
    try:
        student = _make_user(db)
        competencies = [_competency("Quantitative", 100, ["Quantitative Aptitude"])]
        drive, ctx, session = _seed_context_session(db, student, _snapshot(competencies))
        round_ = _aptitude_round(db, session)
        _add_aptitude_attempt(db, round_.id, "Quantitative Aptitude")
        db.commit()

        def boom(*args, **kwargs):
            raise RuntimeError("simulated mapping failure")

        monkeypatch.setattr(competency_mapping_service, "map_session_evidence", boom)

        # Must not raise despite the injected failure.
        _finalize_mock_drive(db, drive, ctx, session)

        db.refresh(session)
        db.refresh(ctx)
        assert session.status == "completed"
        assert ctx.status == "completed"
        assert db.query(CompetencyEvidenceMapping).filter(
            CompetencyEvidenceMapping.session_id == session.id
        ).count() == 0
    finally:
        db.close()


def test_finalization_without_configured_competencies_maps_nothing(db_session):
    student = _make_user(db_session)
    drive, ctx, session = _seed_context_session(db_session, student, _snapshot([]))
    round_ = _aptitude_round(db_session, session)
    _add_aptitude_attempt(db_session, round_.id, "Quantitative Aptitude")
    db_session.commit()

    _finalize_mock_drive(db_session, drive, ctx, session)

    db_session.refresh(session)
    assert session.status == "completed"
    assert db_session.query(CompetencyEvidenceMapping).count() == 0


def test_finalization_of_blueprintless_assessment_is_compatible(db_session):
    student = _make_user(db_session)
    drive, ctx, session = _seed_context_session(db_session, student, None)
    round_ = _aptitude_round(db_session, session)
    _add_aptitude_attempt(db_session, round_.id, "Quantitative Aptitude")
    db_session.commit()

    _finalize_mock_drive(db_session, drive, ctx, session)

    db_session.refresh(session)
    assert session.status == "completed"
    assert db_session.query(CompetencyEvidenceMapping).count() == 0


def test_finalization_mapping_stays_candidate_isolated(db_session):
    student_a = _make_user(db_session)
    student_b = _make_user(db_session)
    competencies = [_competency("Quantitative", 100, ["Quantitative Aptitude"])]

    drive_a, ctx_a, session_a = _seed_context_session(
        db_session, student_a, _snapshot(competencies)
    )
    drive_b, ctx_b, session_b = _seed_context_session(
        db_session, student_b, _snapshot(competencies)
    )
    round_a = _aptitude_round(db_session, session_a)
    round_b = _aptitude_round(db_session, session_b)
    attempt_a = _add_aptitude_attempt(db_session, round_a.id, "Quantitative Aptitude")
    attempt_b = _add_aptitude_attempt(db_session, round_b.id, "Quantitative Aptitude")
    db_session.commit()

    _finalize_mock_drive(db_session, drive_a, ctx_a, session_a)
    _finalize_mock_drive(db_session, drive_b, ctx_b, session_b)

    rows = db_session.query(CompetencyEvidenceMapping).all()
    assert {r.candidate_id for r in rows} == {student_a.id, student_b.id}
    a_rows = [r for r in rows if r.candidate_id == student_a.id]
    b_rows = [r for r in rows if r.candidate_id == student_b.id]
    assert [r.evidence_id for r in a_rows] == [attempt_a.id]
    assert [r.evidence_id for r in b_rows] == [attempt_b.id]
    assert all(r.session_id == session_a.id for r in a_rows)
    assert all(r.session_id == session_b.id for r in b_rows)


# ══════════════════════════════════════════════════════════════════════
# Recovery & reliability (Phase 4C P1/P3/P5)
# ══════════════════════════════════════════════════════════════════════


def test_finalization_records_completed_mapping_status(db_session):
    student = _make_user(db_session)
    competencies = [_competency("Quantitative", 100, ["Quantitative Aptitude"])]
    drive, ctx, session = _seed_context_session(db_session, student, _snapshot(competencies))
    round_ = _aptitude_round(db_session, session)
    _add_aptitude_attempt(db_session, round_.id, "Quantitative Aptitude")
    db_session.commit()

    _finalize_mock_drive(db_session, drive, ctx, session)

    db_session.refresh(ctx)
    assert ctx.competency_mapping_status == MAPPING_STATUS_COMPLETED
    assert ctx.competency_mapping_error is None
    assert ctx.competency_mapping_attempted_at is not None
    assert ctx.competency_mapping_completed_at is not None


def test_finalization_of_blueprintless_drive_records_not_applicable(db_session):
    student = _make_user(db_session)
    drive, ctx, session = _seed_context_session(db_session, student, None)
    round_ = _aptitude_round(db_session, session)
    _add_aptitude_attempt(db_session, round_.id, "Quantitative Aptitude")
    db_session.commit()

    _finalize_mock_drive(db_session, drive, ctx, session)

    db_session.refresh(ctx)
    assert ctx.competency_mapping_status == MAPPING_STATUS_NOT_APPLICABLE
    assert db_session.query(CompetencyEvidenceMapping).filter(
        CompetencyEvidenceMapping.session_id == session.id
    ).count() == 0


def test_finalization_without_configured_competencies_records_not_applicable(db_session):
    student = _make_user(db_session)
    drive, ctx, session = _seed_context_session(db_session, student, _snapshot([]))
    round_ = _aptitude_round(db_session, session)
    _add_aptitude_attempt(db_session, round_.id, "Quantitative Aptitude")
    db_session.commit()

    _finalize_mock_drive(db_session, drive, ctx, session)

    db_session.refresh(ctx)
    assert ctx.competency_mapping_status == MAPPING_STATUS_NOT_APPLICABLE


def test_mapping_failure_records_durable_failed_status(monkeypatch):
    db = TestingSessionLocal()
    try:
        student = _make_user(db)
        competencies = [_competency("Quantitative", 100, ["Quantitative Aptitude"])]
        drive, ctx, session = _seed_context_session(db, student, _snapshot(competencies))
        round_ = _aptitude_round(db, session)
        _add_aptitude_attempt(db, round_.id, "Quantitative Aptitude")
        db.commit()

        def boom(*args, **kwargs):
            raise RuntimeError("simulated mapping failure")

        monkeypatch.setattr(competency_mapping_service, "map_session_evidence", boom)

        _finalize_mock_drive(db, drive, ctx, session)

        db.refresh(session)
        db.refresh(ctx)
        # Completion is never blocked and the failure is durably recorded.
        assert session.status == "completed"
        assert ctx.status == "completed"
        assert ctx.competency_mapping_status == MAPPING_STATUS_FAILED
        assert "RuntimeError" in (ctx.competency_mapping_error or "")
        assert ctx.competency_mapping_attempted_at is not None
        assert db.query(CompetencyEvidenceMapping).filter(
            CompetencyEvidenceMapping.session_id == session.id
        ).count() == 0
    finally:
        db.close()


def test_reprocess_completed_mapping_is_idempotent(db_session):
    student = _make_user(db_session)
    competencies = [_competency("Quantitative", 100, ["Quantitative Aptitude"])]
    drive, ctx, session = _seed_context_session(db_session, student, _snapshot(competencies))
    round_ = _aptitude_round(db_session, session)
    matched = _add_aptitude_attempt(db_session, round_.id, "Quantitative Aptitude")
    db_session.commit()

    _finalize_mock_drive(db_session, drive, ctx, session)
    scoped = db_session.query(CompetencyEvidenceMapping).filter(
        CompetencyEvidenceMapping.session_id == session.id
    )
    before = scoped.count()

    outcome = reprocess_competency_mapping(db_session, session)

    assert outcome["status"] == MAPPING_STATUS_COMPLETED
    assert outcome["reprocessed"] is False
    assert scoped.count() == before == 1
    assert scoped.one().evidence_id == matched.id


def test_reprocess_recovers_failed_mapping(monkeypatch):
    db = TestingSessionLocal()
    try:
        student = _make_user(db)
        competencies = [_competency("Quantitative", 100, ["Quantitative Aptitude"])]
        drive, ctx, session = _seed_context_session(db, student, _snapshot(competencies))
        round_ = _aptitude_round(db, session)
        matched = _add_aptitude_attempt(db, round_.id, "Quantitative Aptitude")
        db.commit()

        real_map = competency_mapping_service.map_session_evidence

        def boom(*args, **kwargs):
            raise RuntimeError("transient failure")

        monkeypatch.setattr(competency_mapping_service, "map_session_evidence", boom)
        _finalize_mock_drive(db, drive, ctx, session)
        db.refresh(ctx)
        assert ctx.competency_mapping_status == MAPPING_STATUS_FAILED

        # Recovery with a healthy mapping implementation.
        monkeypatch.setattr(competency_mapping_service, "map_session_evidence", real_map)
        outcome = reprocess_competency_mapping(db, session)

        assert outcome["status"] == MAPPING_STATUS_COMPLETED
        assert outcome["reprocessed"] is True
        rows = db.query(CompetencyEvidenceMapping).filter(
            CompetencyEvidenceMapping.session_id == session.id
        ).all()
        assert [r.evidence_id for r in rows] == [matched.id]
        db.refresh(ctx)
        assert ctx.competency_mapping_status == MAPPING_STATUS_COMPLETED
        assert ctx.competency_mapping_error is None
    finally:
        db.close()


def test_reprocess_skips_non_mock_drive_session(db_session):
    student = _make_user(db_session)
    session = AssessmentSession(user_id=student.id, context_id=None, status="completed")
    db_session.add(session)
    db_session.flush()

    outcome = reprocess_competency_mapping(db_session, session)

    assert outcome["status"] == "not_applicable"
    assert outcome["reason"] == "not_a_mock_drive_session"


def test_reprocess_skips_non_completed_mock_drive_session(db_session):
    student = _make_user(db_session)
    competencies = [_competency("Quantitative", 100, ["Quantitative Aptitude"])]
    drive, ctx, session = _seed_context_session(db_session, student, _snapshot(competencies))
    db_session.commit()

    outcome = reprocess_competency_mapping(db_session, session)

    assert outcome["status"] == "skipped"
    assert outcome["reason"] == "session_not_completed"


def test_batch_reprocess_recovers_pending_and_failed(db_session):
    competencies = [_competency("Quantitative", 100, ["Quantitative Aptitude"])]

    student_a = _make_user(db_session)
    drive, ctx_a, session_a = _seed_context_session(db_session, student_a, _snapshot(competencies))
    round_a = _aptitude_round(db_session, session_a)
    _add_aptitude_attempt(db_session, round_a.id, "Quantitative Aptitude")

    student_b = _make_user(db_session)
    drive_b, ctx_b, session_b = _seed_context_session(
        db_session, student_b, _snapshot(competencies), drive=drive
    )
    round_b = _aptitude_round(db_session, session_b)
    _add_aptitude_attempt(db_session, round_b.id, "Quantitative Aptitude")

    # Simulate two completed-but-unmapped contexts (e.g. crash before mapping).
    for ctx, session in ((ctx_a, session_a), (ctx_b, session_b)):
        ctx.status = "completed"
        ctx.competency_mapping_status = MAPPING_STATUS_PENDING
        session.status = "completed"
    db_session.commit()

    result = reprocess_mock_drive_competency_mappings(db_session, drive.id)

    assert result["examined"] == 2
    assert result["completed"] == 2
    assert result["failed"] == 0
    db_session.refresh(ctx_a)
    db_session.refresh(ctx_b)
    assert ctx_a.competency_mapping_status == MAPPING_STATUS_COMPLETED
    assert ctx_b.competency_mapping_status == MAPPING_STATUS_COMPLETED
    assert db_session.query(CompetencyEvidenceMapping).filter(
        CompetencyEvidenceMapping.session_id.in_([session_a.id, session_b.id])
    ).count() == 2


def test_mapping_failure_preserves_unrelated_pending_work(monkeypatch):
    """The savepoint isolates mapping writes: unrelated pending work survives."""
    db = TestingSessionLocal()
    try:
        student = _make_user(db)
        competencies = [_competency("Quantitative", 100, ["Quantitative Aptitude"])]
        drive, ctx, session = _seed_context_session(db, student, _snapshot(competencies))
        db.commit()

        session.status = "completed"
        ctx.status = "completed"
        ctx.competency_mapping_status = MAPPING_STATUS_PENDING
        db.commit()

        # Unrelated work staged in the same transaction before the attempt.
        unrelated = _make_user(db, "student")

        def boom(*args, **kwargs):
            raise RuntimeError("simulated mapping failure")

        monkeypatch.setattr(competency_mapping_service, "map_session_evidence", boom)
        finalize_session_competency_mapping(db, session)

        # Failure recorded, unrelated row persisted (not rolled back with it).
        db.refresh(ctx)
        assert ctx.competency_mapping_status == MAPPING_STATUS_FAILED
        check = TestingSessionLocal()
        try:
            assert check.query(User).filter(User.id == unrelated.id).first() is not None
        finally:
            check.close()
    finally:
        db.close()


# ── P3: mapping must not perturb scores, assignment or other evidence ──


def test_mapping_does_not_change_scores_or_question_assignment(db_session):
    student = _make_user(db_session)
    competencies = [_competency("Quantitative", 100, ["Quantitative Aptitude"])]
    drive, ctx, session = _seed_context_session(db_session, student, _snapshot(competencies))
    round_ = _aptitude_round(db_session, session)
    attempt = _add_aptitude_attempt(db_session, round_.id, "Quantitative Aptitude")

    topic = _get_or_create_topic(db_session, "Quantitative Aptitude")
    question = db_session.query(AptitudeQuestion).filter(
        AptitudeQuestion.topic_id == topic.id
    ).first()
    assignment = AptitudeRoundQuestion(
        round_id=round_.id, question_id=question.id, question_order=1
    )
    db_session.add(assignment)
    session.total_score = 42.0
    db_session.commit()

    _finalize_mock_drive(db_session, drive, ctx, session)

    db_session.refresh(session)
    db_session.refresh(attempt)
    db_session.refresh(assignment)
    assert session.total_score == 42.0
    assert attempt.is_correct is True
    assert assignment.question_id == question.id
    # Mapping never generates or reassigns assessment questions.
    assert db_session.query(AptitudeRoundQuestion).filter(
        AptitudeRoundQuestion.round_id == round_.id
    ).count() == 1
    assert db_session.query(CompetencyEvidenceMapping).filter(
        CompetencyEvidenceMapping.session_id == session.id
    ).count() == 1


def test_mapping_never_maps_interview_evidence(db_session):
    student = _make_user(db_session)
    competencies = [_competency("Communication", 100, ["Quantitative Aptitude"])]
    drive, ctx, session = _seed_context_session(db_session, student, _snapshot(competencies))

    interview_round = AssessmentRound(
        session_id=session.id, round_type="interview", status="active", max_questions=5
    )
    db_session.add(interview_round)
    db_session.flush()
    interview = InterviewSession(session_id=session.id, phase="HR")
    db_session.add(interview)
    db_session.flush()
    db_session.add(
        InterviewTurn(
            interview_id=interview.id,
            turn_number=1,
            question_text="Tell me about Quantitative Aptitude.",
            candidate_response="...",
        )
    )
    db_session.commit()

    _finalize_mock_drive(db_session, drive, ctx, session)

    db_session.refresh(ctx)
    # Competencies exist (so mapping is applicable) but interview evidence is
    # free-text and intentionally never guessed/mapped.
    assert ctx.competency_mapping_status == MAPPING_STATUS_COMPLETED
    assert db_session.query(CompetencyEvidenceMapping).filter(
        CompetencyEvidenceMapping.session_id == session.id
    ).count() == 0


def test_opportunistic_retry_recovers_pending_completed_context(db_session):
    student = _make_user(db_session)
    competencies = [_competency("Quantitative", 100, ["Quantitative Aptitude"])]
    drive, ctx, session = _seed_context_session(db_session, student, _snapshot(competencies))
    round_ = _aptitude_round(db_session, session)
    matched = _add_aptitude_attempt(db_session, round_.id, "Quantitative Aptitude")
    # A completed attempt whose finalizer crashed before mapping.
    session.status = "completed"
    ctx.status = "completed"
    ctx.competency_mapping_status = MAPPING_STATUS_PENDING
    db_session.commit()

    _opportunistic_competency_mapping_retry(db_session, ctx)

    db_session.refresh(ctx)
    assert ctx.competency_mapping_status == MAPPING_STATUS_COMPLETED
    rows = db_session.query(CompetencyEvidenceMapping).filter(
        CompetencyEvidenceMapping.session_id == session.id
    ).all()
    assert [r.evidence_id for r in rows] == [matched.id]


def test_reprocess_uses_pinned_snapshot_not_live_blueprint(db_session):
    tpo = _make_user(db_session, "tpo")
    student = _make_user(db_session)
    original = [_competency("Quantitative", 100, ["Quantitative Aptitude"])]
    bp = _make_blueprint(db_session, tpo, competencies=original)
    pinned = snapshot_company_blueprint(bp)
    _, ctx, session = _seed_context_session(db_session, student, pinned)
    round_ = _aptitude_round(db_session, session)
    _add_aptitude_attempt(db_session, round_.id, "Quantitative Aptitude")
    # Simulate a durable mapping failure on a completed attempt.
    session.status = "completed"
    ctx.status = "completed"
    ctx.competency_mapping_status = MAPPING_STATUS_FAILED
    ctx.competency_mapping_error = "transient failure"
    db_session.commit()

    # The live blueprint changes after the snapshot was pinned.
    update_blueprint(
        db_session,
        bp.company_name,
        bp.target_role,
        UpdateBlueprintRequest(
            competencies=[
                BlueprintCompetency(
                    name="Reasoning", weight_pct=100, topics=["Logical Reasoning"]
                )
            ]
        ),
        tpo.id,
    )

    outcome = reprocess_competency_mapping(db_session, session)

    assert outcome["status"] == MAPPING_STATUS_COMPLETED
    assert outcome["reprocessed"] is True
    rows = db_session.query(CompetencyEvidenceMapping).filter(
        CompetencyEvidenceMapping.session_id == session.id
    ).all()
    assert len(rows) == 1
    # Reprocessing re-runs mapping against the pinned snapshot, not the live
    # blueprint (which now only contains "Reasoning").
    assert rows[0].competency_name == "Quantitative"
    assert rows[0].blueprint_version == 1
    db_session.refresh(ctx)
    assert ctx.competency_mapping_status == MAPPING_STATUS_COMPLETED
