"""Blueprint question-pool generation: deterministic tests, no live LLM calls.

Covers the full pre-candidate pipeline (generate -> validate -> persist ->
complete), the Phase 4C pool-only scoping, the interview clone (NO candidate-time
LLM), the publish gate, reported statuses, and provenance columns.
"""

import hashlib

import pytest
from types import SimpleNamespace
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

from app.database.base import Base
from app.models import user as _user_model  # noqa: F401
from app.models.user import User
from app.models.assessment import AssessmentRound, AssessmentSession
from app.models.assessment_context import AssessmentContext, AssessmentPolicy
from app.models.aptitude import AptitudeQuestion, AptitudeRoundQuestion, AptitudeTopic
from app.models.coding import CodingProblem, CodingTestCase
from app.models.company_data import CompanyBlueprint
from app.models.mock_drive import MockDrive
from app.models.question_pool_generation import GeneratedQuestionPool, POOL_BATCH_SIZES
from app.services.assessment_blueprint_service import snapshot_company_blueprint
from app.services.groq_service import GroqService
from app.services.mock_drive_service import publish_mock_drive
from app.services.question_pool_generation_service import (
    POOL_SIZES,
    QuestionPoolGenerationService,
    pool_batch_plan,
    question_pool_generation_service,
)


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "TEXT"


# ── Fixtures & helpers ───────────────────────────────────────────────

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


APTITUDE_TOPICS = [
    {"topic": "Cloud Fundamentals", "weight_pct": 20},
    {"topic": "Computer Networks", "weight_pct": 15},
    {"topic": "Operating Systems", "weight_pct": 15},
    {"topic": "Scripting & Automation", "weight_pct": 20},
    {"topic": "Security Fundamentals", "weight_pct": 15},
    {"topic": "Cost Optimization", "weight_pct": 15},
]
DIFFICULTY = {"easy": 0.25, "medium": 0.5, "hard": 0.25}


def aptitude_round(question_count=25):
    return {
        "round_type": "aptitude",
        "question_count": question_count,
        "time_limit_minutes": 30,
        "topics": APTITUDE_TOPICS,
        "difficulty_distribution": DIFFICULTY,
    }


def coding_round(question_count=3):
    return {
        "round_type": "coding",
        "question_count": question_count,
        "time_limit_minutes": 60,
        "topics": [
            {"topic": "Cloud Fundamentals", "weight_pct": 60},
            {"topic": "Scripting & Automation", "weight_pct": 40},
        ],
        "difficulty_distribution": DIFFICULTY,
    }


def technical_interview_round(question_count=8):
    return {
        "round_type": "technical_interview",
        "question_count": question_count,
        "time_limit_minutes": 30,
        "topics": [
            {"topic": "Cloud Architecture", "weight_pct": 60},
            {"topic": "System Design", "weight_pct": 40},
        ],
        "difficulty_distribution": DIFFICULTY,
    }


def make_blueprint(db, company="Acme", role="Cloud Engineer", rounds=None, approve=True):
    rounds = rounds or [aptitude_round(), coding_round(), technical_interview_round()]
    blueprint = CompanyBlueprint(
        company_name=company,
        target_role=role,
        status="draft",
        version=1,
        confidence_level="high",
        evidence_sources_count=0,
        blueprint_data={
            "status": "draft",
            "company_name": company,
            "target_role": role,
            "rounds": rounds,
            "source_provenance": {
                "classification": "llm_role_assessment",
                "selection_status": "role_assessment_generated",
                "empirical_source_count": 0,
            },
        },
        created_by_id=1,
    )
    db.add(blueprint)
    db.commit()
    db.refresh(blueprint)
    if approve:
        blueprint.status = "approved"
        db.commit()
        db.refresh(blueprint)
    return blueprint


def make_env(db, blueprint, enabled_rounds=None):
    """Create user + drive + policy + context + session under an approved blueprint."""
    user = db.query(User).filter(User.id == 1).first()
    if user is None:
        user = User(id=1, email="student@example.test", name="Student", password_hash="x", role="student")
        db.add(user)

    enabled_rounds = enabled_rounds or [
        item["round_type"] for item in (blueprint.blueprint_data or {}).get("rounds", [])
    ]
    drive = MockDrive(
        company_name=blueprint.company_name,
        target_role=blueprint.target_role,
        status="draft",
        blueprint_id=blueprint.id,
        blueprint_version=blueprint.version,
        selected_rounds={round_type: True for round_type in enabled_rounds},
        created_by_id=1,
    )
    db.add(drive)
    db.commit()
    db.refresh(drive)

    policy = AssessmentPolicy(name="pool-test-policy")
    db.add(policy)
    db.commit()
    db.refresh(policy)

    base_snapshot = snapshot_company_blueprint(blueprint)
    context = AssessmentContext(
        mode="mock_drive",
        student_id=user.id,
        mock_drive_id=drive.id,
        policy_id=policy.id,
        status="active",
        blueprint_snapshot=dict(base_snapshot, enabled_rounds=enabled_rounds),
    )
    db.add(context)
    db.commit()
    db.refresh(context)

    session = AssessmentSession(user_id=user.id, context_id=context.id, status="in_progress")
    db.add(session)
    db.commit()
    db.refresh(session)
    return SimpleNamespace(user=user, drive=drive, policy=policy, context=context, session=session)


def active_aptitude_round(db, session):
    round_obj = AssessmentRound(
        session_id=session.id, round_type="aptitude", status="active"
    )
    db.add(round_obj)
    db.commit()
    db.refresh(round_obj)
    return round_obj


def _batch_offset(spec):
    """Global index of this batch's first schedule slot (0 for a full request)."""
    return int(spec.get("position_offset") or 0)


def make_aptitude_items(spec):
    topics = spec["topics"]
    offset = _batch_offset(spec)
    positions = spec.get("positions") or [
        {"topic": topics[(offset + i) % len(topics)], "difficulty": "medium"}
        for i in range(spec["pool_size"])
    ]
    items = []
    for index, position in enumerate(positions, start=offset + 1):
        items.append(
            {
                "question_text": f"Aptitude Q{index}: {position['topic']}?",
                "option_a": "a1", "option_b": "b1", "option_c": "c1", "option_d": "d1",
                "correct_option": "A",
                "difficulty": position.get("difficulty") or "medium",
                "topic": position["topic"],
                "explanation": "Correct answer justification.",
            }
        )
    return items


def make_coding_items(spec):
    topics = spec["topics"]
    offset = _batch_offset(spec)
    positions = spec.get("positions") or [
        {"topic": topics[(offset + i) % len(topics)], "difficulty": "medium"}
        for i in range(spec["pool_size"])
    ]
    items = []
    for index, position in enumerate(positions, start=offset + 1):
        items.append(
            {
                "title": f"Problem {index}",
                "description": f"Solve for {position['topic']}.",
                "difficulty": position.get("difficulty") or "medium",
                "topic": position["topic"],
                "constraints": "1 <= n <= 100",
                "input_format": "one integer",
                "output_format": "one integer",
                "test_cases": [
                    {"input_data": "2", "expected_output": "4", "is_hidden": False},
                    {"input_data": "3", "expected_output": "9", "is_hidden": True},
                    {"input_data": "4", "expected_output": "16", "is_hidden": True},
                ],
            }
        )
    return items


def make_interview_items(spec):
    topics = spec["topics"]
    difficulties = ["EASY", "MEDIUM", "HARD"]
    offset = _batch_offset(spec)
    items = []
    for local in range(spec["pool_size"]):
        index = offset + local
        topic = topics[index % len(topics)]
        items.append(
            {
                "question": f"Question {index + 1} about {topic}?",
                "difficulty": difficulties[index % 3],
                "topic": topic,
                "phase": spec["phase"],
                "expected_answer": "- covers core concept\n- gives concrete example",
                "evaluation_criteria": "Check depth and role-relevance.",
            }
        )
    return items


class FakePoolGenerator:
    """Deterministic pool LLM; identical shape to the real Groq methods."""

    def __init__(self, aptitude=None, coding=None, interview=None):
        self.aptitude = aptitude or make_aptitude_items
        self.coding = coding or make_coding_items
        self.interview = interview or make_interview_items
        self.calls = {"aptitude": 0, "coding": 0, "interview": 0}
        self.specs = {"aptitude": [], "coding": [], "interview": []}

    def generate_aptitude_question_pool(self, spec):
        self.calls["aptitude"] += 1
        self.specs["aptitude"].append(dict(spec))
        return self.aptitude(spec)

    def generate_coding_problem_pool(self, spec):
        self.calls["coding"] += 1
        self.specs["coding"].append(dict(spec))
        return self.coding(spec)

    def generate_interview_question_pool(self, spec):
        self.calls["interview"] += 1
        self.specs["interview"].append(dict(spec))
        return self.interview(spec)


# ── Validation primitives ────────────────────────────────────────────

def test_aptitude_validation_rejects_wrong_topic_or_count():
    from app.services.question_pool_validation import validate_aptitude_pool

    spec = {
        "pool_size": 2,
        "topics": ["Cloud Fundamentals", "Security Fundamentals"],
        "positions": [
            {"topic": "Cloud Fundamentals", "difficulty": "medium"},
            {"topic": "Security Fundamentals", "difficulty": "hard"},
        ],
    }
    good = [
        {"question_text": "a", "option_a": "1", "option_b": "2", "option_c": "3", "option_d": "4",
         "correct_option": "A", "difficulty": "medium", "topic": "Cloud Fundamentals"},
        {"question_text": "b", "option_a": "1", "option_b": "2", "option_c": "3", "option_d": "4",
         "correct_option": "B", "difficulty": "hard", "topic": "Security Fundamentals"},
    ]
    assert validate_aptitude_pool(good, spec) == (True, [])

    wrong_topic = [
        {"question_text": "a", "option_a": "1", "option_b": "2", "option_c": "3", "option_d": "4",
         "correct_option": "A", "difficulty": "medium", "topic": "Data Structures & Algorithms"},
        {"question_text": "b", "option_a": "1", "option_b": "2", "option_c": "3", "option_d": "4",
         "correct_option": "B", "difficulty": "hard", "topic": "Security Fundamentals"},
    ]
    ok, reasons = validate_aptitude_pool(wrong_topic, spec)
    assert not ok
    assert any("not in blueprint topics" in reason for reason in reasons)

    short = good[:1]
    ok, reasons = validate_aptitude_pool(short, spec)
    assert not ok
    assert any("expected exactly 2 items" in reason for reason in reasons)


def test_coding_validation_requires_visible_and_hidden_cases():
    from app.services.question_pool_validation import validate_coding_pool

    spec = {
        "pool_size": 1,
        "topics": ["Cloud Fundamentals"],
        "positions": [{"topic": "Cloud Fundamentals", "difficulty": "easy"}],
    }
    item = {
        "title": "T", "description": "D", "difficulty": "easy", "topic": "Cloud Fundamentals",
        "constraints": "x", "input_format": "i", "output_format": "o",
        "test_cases": [{"input_data": "1", "expected_output": "1", "is_hidden": False}],
    }
    ok, reasons = validate_coding_pool([item], spec)
    assert not ok
    assert any("at least 2 test cases" in reason for reason in reasons)

    item["test_cases"].append({"input_data": "2", "expected_output": "4", "is_hidden": True})
    assert validate_coding_pool([item], spec) == (True, [])


def test_interview_validation_requires_phase_and_expected_answer():
    from app.services.question_pool_validation import validate_interview_pool

    spec = {"pool_size": 2, "phase": "TECHNICAL", "topics": ["Cloud Architecture", "System Design"]}
    good = [
        {"question": "q1", "difficulty": "EASY", "topic": "Cloud Architecture", "phase": "TECHNICAL",
         "expected_answer": "x", "evaluation_criteria": "y"},
        {"question": "q2", "difficulty": "MEDIUM", "topic": "System Design", "phase": "TECHNICAL",
         "expected_answer": "x", "evaluation_criteria": "y"},
    ]
    assert validate_interview_pool(good, spec) == (True, [])

    wrong_phase = [dict(item) for item in good]
    wrong_phase[0]["phase"] = "HR"
    ok, reasons = validate_interview_pool(wrong_phase, spec)
    assert not ok
    assert any("phase must be TECHNICAL" in reason for reason in reasons)


# ── Generation + persistence ─────────────────────────────────────────

def test_generate_aptitude_pool_persists_and_scope_excludes_seeded(db):
    blueprint = make_blueprint(db)
    pool_gen = QuestionPoolGenerationService(llm_generator=FakePoolGenerator())
    result = pool_gen.generate_for_blueprint(db, blueprint, created_by_id=1)

    aptitude_status = next(item for item in result["rounds"] if item["round_type"] == "aptitude")
    assert aptitude_status["status"] == "complete"
    assert aptitude_status["validated_count"] == POOL_SIZES["aptitude"]

    registry = (
        db.query(GeneratedQuestionPool)
        .filter(GeneratedQuestionPool.blueprint_id == blueprint.id,
                GeneratedQuestionPool.round_type == "aptitude")
        .one()
    )
    assert registry.status == "complete"
    assert registry.validated_count == POOL_SIZES["aptitude"]

    rows = (
        db.query(AptitudeQuestion)
        .filter(AptitudeQuestion.blueprint_id == blueprint.id,
                AptitudeQuestion.blueprint_version == blueprint.version,
                AptitudeQuestion.source == "llm_generated")
        .all()
    )
    assert len(rows) == POOL_SIZES["aptitude"]
    assert all(row.blueprint_id == blueprint.id and row.source == "llm_generated" for row in rows)
    assert all(row.company_name == blueprint.company_name for row in rows)
    assert db.query(AptitudeTopic).filter(AptitudeTopic.name == "Cloud Fundamentals").one()

    # A seeded question for the same blueprint topic must NOT leak into selection.
    seeded_topic = db.query(AptitudeTopic).filter(AptitudeTopic.name == "Cloud Fundamentals").one()
    seeded = AptitudeQuestion(
        question_text="SEEDED question", option_a="1", option_b="2", option_c="3", option_d="4",
        correct_option="A", difficulty="medium", topic_id=seeded_topic.id, is_active=True,
        source=None,
    )
    db.add(seeded)
    db.commit()

    snapshot = snapshot_company_blueprint(blueprint)
    scope = pool_gen.aptitude_pool_scope(db, snapshot)
    assert scope is not None
    assert seeded.id not in scope

    round_config = next(
        item for item in blueprint.blueprint_data["rounds"] if item["round_type"] == "aptitude"
    )
    from app.modules.aptitude.routers.aptitude_router import _select_blueprint_aptitude_questions

    selected = _select_blueprint_aptitude_questions(db, round_config, question_ids=scope)
    assert len(selected) == round_config["question_count"]
    assert all(question.id in scope for question in selected)
    assert all(seeded.id != question.id for question in selected)


def test_generate_coding_pool_persists_test_cases_and_scopes_selection(db):
    blueprint = make_blueprint(db)
    pool_gen = QuestionPoolGenerationService(llm_generator=FakePoolGenerator())
    result = pool_gen.generate_for_blueprint(db, blueprint, created_by_id=1)
    coding_status = next(item for item in result["rounds"] if item["round_type"] == "coding")
    assert coding_status["status"] == "complete"

    problems = (
        db.query(CodingProblem)
        .filter(CodingProblem.blueprint_id == blueprint.id, CodingProblem.source == "llm_generated")
        .all()
    )
    assert len(problems) == POOL_SIZES["coding"]
    for problem in problems:
        assert len(problem.tags_list) == 1
        assert problem.tags_list[0] in {"Cloud Fundamentals", "Scripting & Automation"}
        assert len(problem.test_cases) == 3
        assert any(not case.is_hidden for case in problem.test_cases)
        assert any(case.is_hidden for case in problem.test_cases)

    snapshot = snapshot_company_blueprint(blueprint)
    scope = pool_gen.coding_pool_scope(db, snapshot)
    round_config = next(
        item for item in blueprint.blueprint_data["rounds"] if item["round_type"] == "coding"
    )
    from app.modules.coding.services.coding_service import _select_blueprint_coding_problems

    selected = _select_blueprint_coding_problems(db, None, round_config, problem_ids=scope)
    assert len(selected) == round_config["question_count"]
    assert all(problem.id in scope for problem in selected)


def test_interview_pool_clones_without_candidate_time_llm_and_skips_rephrase_marker(db):
    blueprint = make_blueprint(db)
    fake = FakePoolGenerator()
    pool_gen = QuestionPoolGenerationService(llm_generator=fake)
    result = pool_gen.generate_for_blueprint(db, blueprint, created_by_id=1)
    interview_status = next(
        item for item in result["rounds"] if item["round_type"] == "technical_interview"
    )
    assert interview_status["status"] == "complete"

    env = make_env(db, blueprint)
    from app.modules.interview.routers.interview_router import (
        _generate_question_pool_for_session,
    )

    before = dict(fake.calls)
    pool, count, blueprint_backed = _generate_question_pool_for_session(
        db, env.session.id, skills=[], projects={}, interview_type="technical"
    )
    after = dict(fake.calls)
    # NO LLM call happened at candidate time (clone path).
    assert before == after
    assert blueprint_backed is True
    assert count == 8
    assert len(pool) == 8
    assert all(item.get("role") == "Cloud Engineer" for item in pool)
    assert all(item.get("blueprint_pool") is True for item in pool)
    assert all(item.get("phase") == "TECHNICAL" for item in pool)


def test_full_phase4c_assignments_use_generated_pool_for_aptitude(db):
    blueprint = make_blueprint(db)
    pool_gen = QuestionPoolGenerationService(llm_generator=FakePoolGenerator())
    pool_gen.generate_for_blueprint(db, blueprint, created_by_id=1)

    env = make_env(db, blueprint)
    round_obj = active_aptitude_round(db, env.session)

    from app.modules.aptitude.routers.aptitude_router import (
        _ensure_blueprint_aptitude_assignments,
    )

    round_config = next(
        item for item in blueprint.blueprint_data["rounds"] if item["round_type"] == "aptitude"
    )
    assignments, questions = _ensure_blueprint_aptitude_assignments(
        db, round_obj, round_config
    )
    assert len(assignments) == round_config["question_count"]
    assert len(questions) == round_config["question_count"]
    assert all(question.source == "llm_generated" for question in questions)
    assert all(question.blueprint_id == blueprint.id for question in questions)

    round_questions = (
        db.query(AptitudeRoundQuestion)
        .filter(AptitudeRoundQuestion.round_id == round_obj.id)
        .order_by(AptitudeRoundQuestion.question_order.asc())
        .all()
    )
    assert len(round_questions) == round_config["question_count"]
    assert [item.question_order for item in round_questions] == list(range(1, round_config["question_count"] + 1))


# ── Failure safety ───────────────────────────────────────────────────

def test_generic_topic_substitution_fails_pool_and_blocks_publish(db):
    blueprint = make_blueprint(db)

    def bad_aptitude(spec):
        items = make_aptitude_items(spec)
        items[0]["topic"] = "Data Structures & Algorithms"
        return items

    pool_gen = QuestionPoolGenerationService(
        llm_generator=FakePoolGenerator(aptitude=bad_aptitude)
    )
    result = pool_gen.generate_for_blueprint(db, blueprint, created_by_id=1)
    aptitude_status = next(item for item in result["rounds"] if item["round_type"] == "aptitude")
    assert aptitude_status["status"] == "incomplete"
    # Nothing was persisted for the failed pool.
    assert (
        db.query(AptitudeQuestion)
        .filter(AptitudeQuestion.source == "llm_generated")
        .count()
        == 0
    )

    env = make_env(db, blueprint)
    with pytest.raises(HTTPException) as exc:
        publish_mock_drive(db, env.drive.id)
    errors = exc.value.detail["errors"]
    assert any("aptitude" in error.lower() and "generate" in error.lower() for error in errors)


def test_regeneration_is_idempotent_for_complete_pool(db):
    blueprint = make_blueprint(db)
    for _ in range(2):
        QuestionPoolGenerationService(llm_generator=FakePoolGenerator()).generate_for_blueprint(db, blueprint, created_by_id=1)
    assert (
        db.query(AptitudeQuestion)
        .filter(AptitudeQuestion.source == "llm_generated", AptitudeQuestion.blueprint_id == blueprint.id)
        .count()
        == POOL_SIZES["aptitude"]
    )


def test_generation_requires_approved_blueprint(db):
    blueprint = make_blueprint(db, approve=False)
    with pytest.raises(HTTPException) as exc:
        QuestionPoolGenerationService(llm_generator=FakePoolGenerator()).generate_for_blueprint(
            db, blueprint, created_by_id=1
        )
    assert exc.value.status_code == 422


# ── Publish gate ─────────────────────────────────────────────────────

def test_publish_requires_generated_pool_for_interview_round(db):
    blueprint = make_blueprint(db)
    env = make_env(db, blueprint)
    with pytest.raises(HTTPException) as exc:
        publish_mock_drive(db, env.drive.id)
    errors = exc.value.detail["errors"]
    assert any("technical_interview" in error for error in errors)
    assert env.drive.status == "draft"

    env2 = make_env(db, blueprint)
    QuestionPoolGenerationService(llm_generator=FakePoolGenerator()).generate_for_blueprint(
        db, blueprint, created_by_id=1
    )
    published = publish_mock_drive(
        db, db.query(MockDrive).filter(MockDrive.id == env2.drive.id).first().id
    )
    assert published.status == "published"


def test_seeded_satisfiable_aptitude_round_publishes_without_pool(db):
    blueprint = make_blueprint(db, rounds=[{
        "round_type": "aptitude",
        "question_count": 1,
        "time_limit_minutes": 30,
        "topics": [{"topic": "Cloud Fundamentals", "weight_pct": 100}],
        "difficulty_distribution": {},
    }])
    topic = AptitudeTopic(name="Cloud Fundamentals")
    db.add(topic)
    db.flush()
    db.add(AptitudeQuestion(
        question_text="q", option_a="1", option_b="2", option_c="3", option_d="4",
        correct_option="A", difficulty="medium", topic_id=topic.id, is_active=True, source=None,
    ))
    db.commit()

    env = make_env(db, blueprint, enabled_rounds=["aptitude"])
    published = publish_mock_drive(
        db, db.query(MockDrive).filter(MockDrive.id == env.drive.id).first().id
    )
    assert published.status == "published"


def test_legacy_evidence_blueprint_publishes_interview_round_without_pool(db):
    """G2: evidence blueprint with interview round now requires a pool (no longer ungated)."""
    blueprint = make_blueprint(db, rounds=[technical_interview_round()])
    blueprint.blueprint_data = {
        **blueprint.blueprint_data,
        "source_provenance": {
            "classification": "evidence_pattern",
            "selection_status": "role_compatible_evidence_found",
            "empirical_source_count": 2,
        },
    }
    db.commit()
    db.refresh(blueprint)

    env = make_env(db, blueprint, enabled_rounds=["technical_interview"])
    drive = db.query(MockDrive).filter(MockDrive.id == env.drive.id).first()

    # Without pool → should now fail with 422
    from fastapi import HTTPException
    try:
        publish_mock_drive(db, drive.id)
        assert False, "Expected HTTPException 422"
    except HTTPException as e:
        assert e.status_code == 422
        assert "technical_interview question pool must be generated" in str(e.detail)


def test_legacy_evidence_blueprint_publishes_interview_round_with_pool(db):
    """G2: evidence blueprint with interview round + pool → publishes 200."""
    blueprint = make_blueprint(db, rounds=[technical_interview_round()])
    blueprint.blueprint_data = {
        **blueprint.blueprint_data,
        "source_provenance": {
            "classification": "evidence_pattern",
            "selection_status": "role_compatible_evidence_found",
            "empirical_source_count": 2,
        },
    }
    db.commit()
    db.refresh(blueprint)

    # Seed a complete interview pool
    from app.models.question_pool_generation import GeneratedQuestionPool, POOL_STATUS_COMPLETE
    pool = GeneratedQuestionPool(
        blueprint_id=blueprint.id,
        blueprint_version=blueprint.version,
        company_name=blueprint.company_name,
        target_role=blueprint.target_role,
        round_type="technical_interview",
        status=POOL_STATUS_COMPLETE,
        required_count=10,
        validated_count=10,
        content=[{"id": "q1", "question": "Q", "phase": "TECHNICAL", "difficulty": "MEDIUM"}],
    )
    db.add(pool)
    db.commit()

    env = make_env(db, blueprint, enabled_rounds=["technical_interview"])
    drive = db.query(MockDrive).filter(MockDrive.id == env.drive.id).first()

    published = publish_mock_drive(db, drive.id)
    assert published.status == "published"


def test_pool_status_listing_reports_each_round(db):
    blueprint = make_blueprint(db)
    service = question_pool_generation_service
    statuses = service.list_pool_statuses(db, blueprint)
    assert [item["round_type"] for item in statuses] == [
        "aptitude", "coding", "technical_interview"
    ]
    assert all(item["status"] == "not_generated" and item["validated_count"] == 0 for item in statuses)

    QuestionPoolGenerationService(llm_generator=FakePoolGenerator()).generate_for_blueprint(
        db, blueprint, created_by_id=1
    )
    statuses = service.list_pool_statuses(db, blueprint)
    assert all(item["status"] == "complete" for item in statuses)
    assert all(item["generated"] is True for item in statuses)
    assert [item["validated_count"] for item in statuses] == [30, 10, 10]


# ── Groq method contract ─────────────────────────────────────────────

def test_groq_pool_methods_raise_on_malformed_output():
    class BadCompletions:
        def create(self, **kwargs):
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="not json"))])

    service = GroqService.__new__(GroqService)
    service.client = SimpleNamespace(chat=SimpleNamespace(completions=BadCompletions()))

    with pytest.raises(RuntimeError):
        service.generate_aptitude_question_pool({
            "company_name": "Acme", "target_role": "Cloud Engineer",
            "pool_size": 2, "positions": [{"topic": "T", "difficulty": "easy"}] * 2,
        })


def test_safe_json_never_turns_prose_into_content():
    from app.services.groq_service import _safe_json

    # Pure prose (no JSON at all) is never content.
    assert _safe_json("not json") is None
    assert _safe_json("") is None
    # Braces that are not JSON stay unparseable.
    assert _safe_json("The answer is {obviously} not JSON.") is None
    # A payload wrapped in prose/fences is recovered as JSON only.
    wrapped = 'Sure, here are the questions:\n```json\n{"questions": [{"q": 1}]}\n```'
    assert _safe_json(wrapped) == {"questions": [{"q": 1}]}
    trailing = 'Here you go {"problems": []} - let me know!'
    assert _safe_json(trailing) == {"problems": []}
    # Plain JSON is unchanged.
    assert _safe_json('{"a": 1}') == {"a": 1}


def test_groq_pool_method_recovers_json_wrapped_in_prose():
    import json as jsonlib

    item = {
        "question_text": "What does TCP guarantee?",
        "option_a": "a", "option_b": "b", "option_c": "c", "option_d": "d",
        "correct_option": "A", "difficulty": "easy", "topic": "T",
        "explanation": "Because of the handshake.",
    }
    content = "Certainly!\n" + jsonlib.dumps({"questions": [item]})

    class ProseCompletions:
        def create(self, **kwargs):
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
            )

    service = GroqService.__new__(GroqService)
    service.client = SimpleNamespace(chat=SimpleNamespace(completions=ProseCompletions()))
    result = service.generate_aptitude_question_pool({
        "company_name": "Acme", "target_role": "Cloud Engineer",
        "pool_size": 1, "positions": [{"topic": "T", "difficulty": "easy"}],
    })
    assert result == [item]


def test_generated_question_id_is_md5_and_content_is_pool_sized(db):
    blueprint = make_blueprint(db)
    pool_gen = QuestionPoolGenerationService(llm_generator=FakePoolGenerator())
    pool_gen.generate_for_blueprint(db, blueprint, created_by_id=1)
    registry = (
        db.query(GeneratedQuestionPool)
        .filter(GeneratedQuestionPool.blueprint_id == blueprint.id,
                GeneratedQuestionPool.round_type == "technical_interview")
        .one()
    )
    assert len(registry.content) == POOL_SIZES["technical_interview"]
    for item in registry.content:
        assert item["id"] == hashlib.md5(item["question"].encode("utf-8")).hexdigest()[:12]


# ── Bounded provider batching ────────────────────────────────────────

def test_pool_batch_plan_is_bounded_and_sums_to_pool_size():
    assert POOL_SIZES == {
        "aptitude": 30, "coding": 10, "technical_interview": 10, "hr_interview": 10,
    }
    assert pool_batch_plan("aptitude", POOL_SIZES["aptitude"]) == [10, 10, 10]
    assert pool_batch_plan("coding", POOL_SIZES["coding"]) == [5, 5]
    assert pool_batch_plan("technical_interview", POOL_SIZES["technical_interview"]) == [5, 5]
    assert pool_batch_plan("hr_interview", POOL_SIZES["hr_interview"]) == [5, 5]
    assert pool_batch_plan("aptitude", 4) == [4]
    assert pool_batch_plan("aptitude", 12) == [10, 2]
    assert pool_batch_plan("aptitude", 0) == []
    assert pool_batch_plan("aptitude", -1) == []

    for round_type, size in POOL_SIZES.items():
        plan = pool_batch_plan(round_type, size)
        assert sum(plan) == size
        assert all(0 < chunk <= POOL_BATCH_SIZES[round_type] for chunk in plan)


def test_generation_requests_bounded_batches_with_sliced_schedules(db):
    blueprint = make_blueprint(db)
    fake = FakePoolGenerator()
    QuestionPoolGenerationService(llm_generator=fake).generate_for_blueprint(
        db, blueprint, created_by_id=1
    )

    # Aptitude 30 -> three 10-item calls, each with its slice of the schedule
    # and the global offset of that slice.
    aptitude_specs = fake.specs["aptitude"]
    assert [spec["pool_size"] for spec in aptitude_specs] == [10, 10, 10]
    assert [spec["position_offset"] for spec in aptitude_specs] == [0, 10, 20]
    assert [len(spec["positions"]) for spec in aptitude_specs] == [10, 10, 10]
    reassembled = [pos for spec in aptitude_specs for pos in spec["positions"]]
    assert len(reassembled) == 30
    assert all(0 < spec["pool_size"] <= POOL_BATCH_SIZES["aptitude"] for spec in aptitude_specs)

    # Coding 10 -> two 5-item calls.
    coding_specs = fake.specs["coding"]
    assert [spec["pool_size"] for spec in coding_specs] == [5, 5]
    assert [spec["position_offset"] for spec in coding_specs] == [0, 5]
    assert [len(spec["positions"]) for spec in coding_specs] == [5, 5]

    # Technical interview 10 -> two 5-item calls, each carrying its slice of the
    # topic schedule (every configured topic scheduled at least once).
    interview_specs = fake.specs["interview"]
    assert [spec["pool_size"] for spec in interview_specs] == [5, 5]
    assert [spec["position_offset"] for spec in interview_specs] == [0, 5]
    assert [len(spec["positions"]) for spec in interview_specs] == [5, 5]
    interview_positions = [pos for spec in interview_specs for pos in spec["positions"]]
    assert len(interview_positions) == 10
    assert {pos["topic"] for pos in interview_positions} == {"Cloud Architecture", "System Design"}
    assert all(spec["phase"] == "TECHNICAL" for spec in interview_specs)

    assert fake.calls == {"aptitude": 3, "coding": 2, "interview": 2}


def test_provider_error_in_a_later_batch_fails_round_without_partial_rows(db):
    blueprint = make_blueprint(db)

    def flaky(spec):
        if _batch_offset(spec) >= 10:
            raise RuntimeError("Aptitude pool generation failed: provider timeout")
        return make_aptitude_items(spec)

    pool_gen = QuestionPoolGenerationService(
        llm_generator=FakePoolGenerator(aptitude=flaky)
    )
    result = pool_gen.generate_for_blueprint(db, blueprint, created_by_id=1)
    aptitude_status = next(r for r in result["rounds"] if r["round_type"] == "aptitude")
    assert aptitude_status["status"] == "failed"
    assert "provider timeout" in aptitude_status["generation_error"]

    registry = (
        db.query(GeneratedQuestionPool)
        .filter(GeneratedQuestionPool.blueprint_id == blueprint.id,
                GeneratedQuestionPool.round_type == "aptitude")
        .one()
    )
    assert registry.status == "failed"
    assert registry.validated_count == 0
    assert (
        db.query(AptitudeQuestion)
        .filter(AptitudeQuestion.source == "llm_generated")
        .count() == 0
    )


# ── Exact pool size enforcement ──────────────────────────────────────

def test_aptitude_over_delivery_trims_to_exact_requested_size(db):
    # LLM returns 36 for a 30-slot schedule (with 5 stray duplicates + 1
    # unrelated generic topic). The pool must persist EXACTLY 30 schedule-valid
    # questions and never pull the unrelated topic in.
    blueprint = make_blueprint(db)

    def over_deliver(spec):
        items = make_aptitude_items(spec)
        extra = [dict(items[0]) for _ in range(5)]
        extra.append({
            "question_text": "generic DSA question",
            "option_a": "a", "option_b": "b", "option_c": "c", "option_d": "d",
            "correct_option": "A", "difficulty": "easy",
            "topic": "Data Structures & Algorithms",
        })
        return items + extra

    pool_gen = QuestionPoolGenerationService(
        llm_generator=FakePoolGenerator(aptitude=over_deliver)
    )
    result = pool_gen.generate_for_blueprint(db, blueprint, created_by_id=1)
    aptitude_status = next(r for r in result["rounds"] if r["round_type"] == "aptitude")
    assert aptitude_status["status"] == "complete"
    assert aptitude_status["required_count"] == POOL_SIZES["aptitude"] == 30
    assert aptitude_status["validated_count"] == 30

    persisted = (
        db.query(AptitudeQuestion)
        .filter(AptitudeQuestion.blueprint_id == blueprint.id,
                AptitudeQuestion.source == "llm_generated")
        .all()
    )
    assert len(persisted) == 30
    assert all(row.difficulty in {"easy", "medium", "hard"} for row in persisted)

    registry = (
        db.query(GeneratedQuestionPool)
        .filter(GeneratedQuestionPool.blueprint_id == blueprint.id,
                GeneratedQuestionPool.round_type == "aptitude")
        .one()
    )
    assert registry.status == "complete"
    assert registry.validated_count == 30

    topic_names = [row.topic.name for row in persisted]
    assert "Data Structures & Algorithms" not in topic_names


def test_coding_over_delivery_trims_to_exact_requested_size(db):
    blueprint = make_blueprint(db)

    def over_deliver(spec):
        items = make_coding_items(spec)
        return items + [dict(items[0]) for _ in range(2)]

    pool_gen = QuestionPoolGenerationService(
        llm_generator=FakePoolGenerator(coding=over_deliver)
    )
    result = pool_gen.generate_for_blueprint(db, blueprint, created_by_id=1)
    coding_status = next(r for r in result["rounds"] if r["round_type"] == "coding")
    assert coding_status["status"] == "complete"
    assert coding_status["validated_count"] == POOL_SIZES["coding"] == 10

    problems = (
        db.query(CodingProblem)
        .filter(CodingProblem.blueprint_id == blueprint.id,
                CodingProblem.source == "llm_generated")
        .all()
    )
    assert len(problems) == 10


def test_interview_pool_over_delivery_trims_to_exact_requested_size(db):
    blueprint = make_blueprint(db)

    def over_deliver(spec):
        items = make_interview_items(spec)
        return items + [dict(items[0]) for _ in range(2)]

    pool_gen = QuestionPoolGenerationService(
        llm_generator=FakePoolGenerator(interview=over_deliver)
    )
    result = pool_gen.generate_for_blueprint(db, blueprint, created_by_id=1)
    interview_status = next(
        r for r in result["rounds"] if r["round_type"] == "technical_interview"
    )
    assert interview_status["status"] == "complete"
    assert interview_status["validated_count"] == POOL_SIZES["technical_interview"] == 10

    registry = (
        db.query(GeneratedQuestionPool)
        .filter(GeneratedQuestionPool.blueprint_id == blueprint.id,
                GeneratedQuestionPool.round_type == "technical_interview")
        .one()
    )
    assert len(registry.content) == 10


def test_short_delivery_fails_without_partial_pool(db):
    # Every 10-item batch returns one item short, so the 30-slot grade can
    # never be filled. Generation must fail cleanly and NO row may be persisted
    # (no partial/executable pool).
    blueprint = make_blueprint(db)

    def short_deliver(spec):
        return make_aptitude_items(spec)[:-1]

    pool_gen = QuestionPoolGenerationService(
        llm_generator=FakePoolGenerator(aptitude=short_deliver)
    )
    result = pool_gen.generate_for_blueprint(db, blueprint, created_by_id=1)
    aptitude_status = next(r for r in result["rounds"] if r["round_type"] == "aptitude")
    assert aptitude_status["status"] == "incomplete"
    assert "expected exactly 30 items, got 27" in aptitude_status["generation_error"]

    registry = (
        db.query(GeneratedQuestionPool)
        .filter(GeneratedQuestionPool.blueprint_id == blueprint.id,
                GeneratedQuestionPool.round_type == "aptitude")
        .one()
    )
    assert registry.status == "incomplete"
    assert registry.validated_count == 0
    assert registry.generation_error
    assert (
        db.query(AptitudeQuestion)
        .filter(AptitudeQuestion.source == "llm_generated")
        .count() == 0
    )


def test_selection_primitive_is_deterministic_and_schedule_preserving():
    from app.services.question_pool_validation import select_deterministic_pool

    spec = {
        "pool_size": 4,
        "topics": ["T1", "T2"],
        "positions": [
            {"topic": "T1", "difficulty": "easy"},
            {"topic": "T1", "difficulty": "hard"},
            {"topic": "T2", "difficulty": "easy"},
            {"topic": "T2", "difficulty": "hard"},
        ],
    }
    items = []
    for idx, position in enumerate(spec["positions"], start=1):
        items.append({
            "question_text": f"q{idx}", "option_a": "a", "option_b": "b",
            "option_c": "c", "option_d": "d", "correct_option": "A",
            "difficulty": position["difficulty"], "topic": position["topic"],
        })
    over = items + [dict(items[0])] + [dict(items[1])]
    trimmed = select_deterministic_pool(over, spec)
    assert len(trimmed) == 4
    assert trimmed == items  # stable first-match order keeps the scheduled subset
    assert select_deterministic_pool(over, spec) == trimmed  # deterministic


def test_deduplicate_pool_drops_repeats_keeps_order_and_empty_keys():
    from app.services.question_pool_validation import deduplicate_pool

    aptitude_items = [
        {"question_text": "  What is TCP?  "},
        {"question_text": "what is tcp?"},          # repeat (trim + casefold)
        {"question_text": "What is UDP?"},
        {"question_text": ""},                      # unusable text is kept as-is
        {"question_text": ""},
    ]
    kept = deduplicate_pool(aptitude_items, "aptitude")
    assert [item["question_text"] for item in kept] == [
        "  What is TCP?  ", "What is UDP?", "", "",
    ]

    coding_items = [
        {"title": "Two Sum"},
        {"title": "  two sum "},                    # repeat
        {"title": "LRU Cache"},
    ]
    assert [item["title"] for item in deduplicate_pool(coding_items, "coding")] == [
        "Two Sum", "LRU Cache",
    ]

    interview_items = [
        {"question": "How would you index this table?"},
        {"question": "  how would you index this table? "},   # repeat
        {"question": "Describe a safe rollback."},
    ]
    assert len(deduplicate_pool(interview_items, "technical_interview")) == 2
    assert len(deduplicate_pool(interview_items, "hr_interview")) == 2

    # Unknown round types are returned unchanged (nothing to key on).
    assert deduplicate_pool(coding_items, "mystery_round") == coding_items


def test_historical_blueprint_pool_exact_counts_and_blueprint_coding_topic(db):
    # Reproduces the reported blueprint shape (Barclays / Database tester):
    # Aptitude 30, Coding 10, Technical Interview 10, Coding topic exactly
    # "Software Engineering & Design Patterns". No generic topics, no leaks.
    # The candidate-facing coding round stays question_count=5: the validated
    # pool size (10) is strictly larger and never changes what a candidate sees.
    blueprint = make_blueprint(db, company="Barclays", role="Database tester", rounds=[
        {
            "round_type": "aptitude", "question_count": 30, "time_limit_minutes": 60,
            "topics": [{"topic": "SQL & Querying", "weight_pct": 100}],
            "difficulty_distribution": {"easy": 0.25, "medium": 0.5, "hard": 0.25},
        },
        {
            "round_type": "coding", "question_count": 5, "time_limit_minutes": 90,
            "topics": [{"topic": "Software Engineering & Design Patterns", "weight_pct": 100}],
            "difficulty_distribution": {"easy": 0.25, "medium": 0.5, "hard": 0.25},
        },
        {
            "round_type": "technical_interview", "question_count": 10, "time_limit_minutes": 45,
            "topics": [{"topic": "Software Engineering & Design Patterns", "weight_pct": 100}],
            "difficulty_distribution": {"easy": 0.33, "medium": 0.34, "hard": 0.33},
        },
    ])
    pool_gen = QuestionPoolGenerationService(llm_generator=FakePoolGenerator())
    result = pool_gen.generate_for_blueprint(db, blueprint, created_by_id=1)
    statuses = {r["round_type"]: r for r in result["rounds"]}
    assert statuses["aptitude"]["status"] == "complete"
    assert statuses["aptitude"]["validated_count"] == 30
    assert statuses["coding"]["status"] == "complete"
    assert statuses["coding"]["validated_count"] == 10
    assert statuses["technical_interview"]["status"] == "complete"
    assert statuses["technical_interview"]["validated_count"] == 10

    aptitude = (db.query(AptitudeQuestion)
                .filter(AptitudeQuestion.blueprint_id == blueprint.id,
                        AptitudeQuestion.source == "llm_generated")
                .all())
    assert len(aptitude) == 30
    assert all(q.topic.name == "SQL & Querying" for q in aptitude)

    coding = (db.query(CodingProblem)
              .filter(CodingProblem.blueprint_id == blueprint.id,
                      CodingProblem.source == "llm_generated")
              .all())
    assert len(coding) == 10
    assert all(problem.tags_list == ["Software Engineering & Design Patterns"] for problem in coding)
    assert all(problem.tags == ["Software Engineering & Design Patterns"] for problem in coding)

    registry_counts = {
        row.round_type: row.validated_count
        for row in db.query(GeneratedQuestionPool)
        .filter(GeneratedQuestionPool.blueprint_id == blueprint.id)
        .all()
    }
    assert registry_counts == {"aptitude": 30, "coding": 10, "technical_interview": 10}

    # Candidate-facing coding round is untouched by the pool size.
    coding_round = next(
        r for r in blueprint.blueprint_data["rounds"] if r["round_type"] == "coding"
    )
    assert coding_round["question_count"] == 5


# ── Coding tags persistence boundary ─────────────────────────────────

def test_coding_tags_persist_as_lists_not_json_strings(db):
    blueprint = make_blueprint(db)
    pool_gen = QuestionPoolGenerationService(llm_generator=FakePoolGenerator())
    pool_gen.generate_for_blueprint(db, blueprint, created_by_id=1)

    problems = (
        db.query(CodingProblem)
        .filter(CodingProblem.blueprint_id == blueprint.id,
                CodingProblem.source == "llm_generated")
        .all()
    )
    assert problems
    for problem in problems:
        # ORM attribute is a real Python list, never a JSON-encoded string.
        assert isinstance(problem.tags, list)
        assert len(problem.tags) == 1
        assert problem.tags == problem.tags_list

    # PostgreSQL boundary: the value handed to psycopg2 is a genuine list (a
    # text[] array literal), NOT '["..."]' JSON text.
    from sqlalchemy.dialects import postgresql
    col = CodingProblem.__table__.c.tags
    bind = col.type.bind_processor(postgresql.dialect())
    assert bind(["Software Engineering & Design Patterns"]) == [
        "Software Engineering & Design Patterns",
    ]
    assert bind(["SQL & Querying", "Software Engineering & Design Patterns"]) == [
        "SQL & Querying",
        "Software Engineering & Design Patterns",
    ]
    assert bind([]) == []
    assert bind(None) is None


def test_coding_pool_persists_explicit_multi_tags(db):
    blueprint = make_blueprint(db)

    def tagged_coding(spec):
        items = make_coding_items(spec)
        for index, item in enumerate(items):
            item["tags"] = [item["topic"]] if index % 2 else ["SQL & Querying", "Software Engineering & Design Patterns"]
        return items

    pool_gen = QuestionPoolGenerationService(
        llm_generator=FakePoolGenerator(coding=tagged_coding)
    )
    pool_gen.generate_for_blueprint(db, blueprint, created_by_id=1)
    problems = (
        db.query(CodingProblem)
        .filter(CodingProblem.blueprint_id == blueprint.id,
                CodingProblem.source == "llm_generated")
        .order_by(CodingProblem.id)
        .all()
    )
    assert len(problems) == POOL_SIZES["coding"]
    assert any(len(problem.tags_list) == 2 for problem in problems)
    assert any(len(problem.tags_list) == 1 for problem in problems)
    allowed = {"Cloud Fundamentals", "Scripting & Automation", "SQL & Querying", "Software Engineering & Design Patterns"}
    assert all(set(problem.tags_list) <= allowed for problem in problems)
    assert all(isinstance(problem.tags, list) for problem in problems)


def test_coding_tags_single_multi_empty_model_roundtrip(db):
    cases = [
        ["Software Engineering & Design Patterns"],
        ["SQL & Querying", "Software Engineering & Design Patterns"],
        [],
    ]
    for tags in cases:
        problem = CodingProblem(title="t", description="d", tags=tags)
        db.add(problem)
        db.commit()
        db.refresh(problem)
        assert problem.tags == tags
        assert problem.tags_list == tags

# -- Drive-facing question counts (UI "Generated Question Pool") -------

def test_drive_question_count_selects_from_validated_pool_without_regeneration(db):
    """Drive counts (15, then 20) select from the reusable validated aptitude
    pool of 30. The drive count never resizes the pool: rows, registry row,
    internal capacities, and LLM call count all stay exactly as they are."""
    fake = FakePoolGenerator()
    blueprint = make_blueprint(db, rounds=[aptitude_round()])
    pool_gen = QuestionPoolGenerationService(llm_generator=fake)
    result = pool_gen.generate_for_blueprint(db, blueprint, created_by_id=1)

    apt_status = next(item for item in result["rounds"] if item["round_type"] == "aptitude")
    assert apt_status["status"] == "complete"
    assert apt_status["required_count"] == 30
    assert apt_status["validated_count"] == 30

    # The internal pool-status payload the UI consumes still reports capacity 30.
    statuses = {
        item["round_type"]: item
        for item in question_pool_generation_service.list_pool_statuses(db, blueprint)
    }
    assert statuses["aptitude"]["pool_size"] == 30
    assert statuses["aptitude"]["validated_count"] == 30
    # Internal validated pool sizes are untouched by any drive-facing change.
    assert POOL_SIZES == {
        "aptitude": 30,
        "coding": 10,
        "technical_interview": 10,
        "hr_interview": 10,
    }

    registry = (
        db.query(GeneratedQuestionPool)
        .filter(GeneratedQuestionPool.blueprint_id == blueprint.id,
                GeneratedQuestionPool.round_type == "aptitude")
        .one()
    )
    registry_before = (
        registry.status, registry.required_count, registry.validated_count, registry.updated_at,
    )
    pool_ids_before = sorted(
        row.id for row in db.query(AptitudeQuestion).filter(
            AptitudeQuestion.blueprint_id == blueprint.id,
            AptitudeQuestion.source == "llm_generated",
        )
    )
    calls_before = fake.calls["aptitude"]
    assert calls_before > 0

    snapshot = snapshot_company_blueprint(blueprint)
    scope = pool_gen.aptitude_pool_scope(db, snapshot)
    assert scope is not None
    round_config = next(
        item for item in blueprint.blueprint_data["rounds"] if item["round_type"] == "aptitude"
    )
    from app.modules.aptitude.routers.aptitude_router import _select_blueprint_aptitude_questions

    for drive_count in (15, 20):
        drive_round_config = {**round_config, "question_count": drive_count}
        selected = _select_blueprint_aptitude_questions(db, drive_round_config, question_ids=scope)
        assert len(selected) == drive_count
        assert all(question.id in scope for question in selected)

    db.refresh(registry)
    assert (
        registry.status,
        registry.required_count,
        registry.validated_count,
        registry.updated_at,
    ) == registry_before
    assert sorted(
        row.id for row in db.query(AptitudeQuestion).filter(
            AptitudeQuestion.blueprint_id == blueprint.id,
            AptitudeQuestion.source == "llm_generated",
        )
    ) == pool_ids_before
    assert fake.calls["aptitude"] == calls_before


# ── Interview topic coverage (bounded top-up) ────────────────────────

ELUSIVE_TOPIC = "Test reporting and metrics"


def three_topic_interview_round():
    """A technical_interview round with more topics than a single 5-item batch."""
    return {
        "round_type": "technical_interview",
        "question_count": 10,
        "time_limit_minutes": 30,
        "topics": [
            {"topic": "Python testing frameworks (pytest/unittest)", "weight_pct": 40},
            {"topic": "API testing with requests", "weight_pct": 30},
            {"topic": ELUSIVE_TOPIC, "weight_pct": 30},
        ],
        "difficulty_distribution": DIFFICULTY,
    }


def _interview_item(topic, question):
    return {
        "question": question,
        "difficulty": "MEDIUM",
        "topic": topic,
        "phase": "TECHNICAL",
        "expected_answer": "- covers the concept\n- example",
        "evaluation_criteria": "Grade depth and role relevance.",
    }


def test_interview_topic_coverage_is_case_insensitive():
    from app.services.question_pool_validation import (
        missing_interview_topics,
        validate_interview_pool,
    )

    spec = {
        "pool_size": 2,
        "phase": "TECHNICAL",
        "topics": [ELUSIVE_TOPIC, "API testing with requests"],
    }
    items = [
        _interview_item("test REPORTING and metrics", "How do you report flaky-test metrics?"),
        _interview_item("API TESTING WITH REQUESTS", "How do you mock HTTP in pytest?"),
    ]
    assert validate_interview_pool(items, spec) == (True, [])
    assert missing_interview_topics(items, spec) == []


def test_interview_missing_topic_reported_with_original_case():
    from app.services.question_pool_validation import (
        missing_interview_topics,
        validate_interview_pool,
    )

    spec = {
        "pool_size": 2,
        "phase": "TECHNICAL",
        "topics": ["Python testing frameworks (pytest/unittest)", ELUSIVE_TOPIC],
    }
    items = [
        _interview_item("Python testing frameworks (pytest/unittest)", "How do you structure fixtures?"),
        _interview_item("Python testing frameworks (pytest/unittest)", "How do you parametrize tests?"),
    ]
    assert missing_interview_topics(items, spec) == [ELUSIVE_TOPIC]
    ok, reasons = validate_interview_pool(items, spec)
    assert not ok
    assert any(
        "no question authored for topic(s): " + ELUSIVE_TOPIC in reason
        for reason in reasons
    )


def test_interview_topic_topup_authors_missing_topic(db):
    def selective(spec):
        items = make_interview_items(spec)
        if spec["pool_size"] == 1:
            return items  # focused top-up authors the single requested topic
        # Normal batches never author the elusive topic.
        for item in items:
            if item["topic"] == ELUSIVE_TOPIC:
                item["topic"] = "Python testing frameworks (pytest/unittest)"
        return items

    fake = FakePoolGenerator(interview=selective)
    blueprint = make_blueprint(db, rounds=[three_topic_interview_round()])
    result = QuestionPoolGenerationService(llm_generator=fake).generate_for_blueprint(
        db, blueprint, created_by_id=1
    )
    status = next(r for r in result["rounds"] if r["round_type"] == "technical_interview")
    assert status["status"] == "complete"
    assert status["validated_count"] == 10

    registry = (
        db.query(GeneratedQuestionPool)
        .filter(GeneratedQuestionPool.blueprint_id == blueprint.id,
                GeneratedQuestionPool.round_type == "technical_interview")
        .one()
    )
    assert registry.status == "complete"
    topics = [item["topic"] for item in registry.content]
    assert len(topics) == 10
    assert ELUSIVE_TOPIC in topics
    # A bounded, topic-specific retry was issued for the missing topic.
    assert sum(1 for spec in fake.specs["interview"] if spec["pool_size"] == 1) == 1
    assert any(
        spec["pool_size"] == 1 and spec["topics"] == [ELUSIVE_TOPIC]
        for spec in fake.specs["interview"]
    )


def test_interview_topic_topup_exhaustion_keeps_pool_incomplete(db):
    def selective(spec):
        if spec["pool_size"] == 1:
            # Malformed focused retry: right topic, missing required fields.
            return [{
                "question": "How do you report test metrics?",
                "difficulty": "MEDIUM",
                "topic": spec["topics"][0],
                "phase": spec["phase"],
            }]
        items = make_interview_items(spec)
        for item in items:
            if item["topic"] == ELUSIVE_TOPIC:
                item["topic"] = "Python testing frameworks (pytest/unittest)"
        return items

    fake = FakePoolGenerator(interview=selective)
    blueprint = make_blueprint(db, rounds=[three_topic_interview_round()])
    result = QuestionPoolGenerationService(llm_generator=fake).generate_for_blueprint(
        db, blueprint, created_by_id=1
    )
    status = next(r for r in result["rounds"] if r["round_type"] == "technical_interview")
    assert status["status"] == "incomplete"
    assert ELUSIVE_TOPIC in status["generation_error"]
    assert "failed validation" in status["generation_error"]

    registry = (
        db.query(GeneratedQuestionPool)
        .filter(GeneratedQuestionPool.blueprint_id == blueprint.id,
                GeneratedQuestionPool.round_type == "technical_interview")
        .one()
    )
    assert registry.status == "incomplete"
    assert registry.validated_count == 0
    assert not registry.content  # no partial pool, no false "complete"
    assert any(spec["pool_size"] == 1 for spec in fake.specs["interview"])


def test_interview_label_case_variation_still_completes(db):
    def cased(spec):
        items = make_interview_items(spec)
        for item in items:
            item["topic"] = item["topic"].upper()
        return items

    fake = FakePoolGenerator(interview=cased)
    blueprint = make_blueprint(db, rounds=[technical_interview_round()])
    result = QuestionPoolGenerationService(llm_generator=fake).generate_for_blueprint(
        db, blueprint, created_by_id=1
    )
    status = next(r for r in result["rounds"] if r["round_type"] == "technical_interview")
    assert status["status"] == "complete"
    assert status["validated_count"] == 10
    # No top-up was needed: case-different labels are still treated as covered.
    assert all(spec["pool_size"] != 1 for spec in fake.specs["interview"])


# ── Topic-label case/whitespace drift in aptitude & coding pools ──────

def _case_drift(factory):
    """Wrap a deterministic generator so topics come back lowercased (as many
    providers do), while otherwise staying schedule-compliant."""

    def wrapped(spec):
        items = factory(spec)
        for item in items:
            topic = item.get("topic")
            if isinstance(topic, str):
                item["topic"] = topic.lower()
        return items

    return wrapped


def test_case_drifted_topic_labels_still_generate_complete_pools(db):
    """A provider echoing the approved aptitude/coding topics with different
    capitalization must not fail the pool: the item topic is canonicalized to
    the approved label before validation/persistence, so those rounds complete
    and no near-duplicate topic row is created."""
    blueprint = make_blueprint(db)
    fake = FakePoolGenerator(
        aptitude=_case_drift(make_aptitude_items),
        coding=_case_drift(make_coding_items),
    )
    result = QuestionPoolGenerationService(llm_generator=fake).generate_for_blueprint(
        db, blueprint, created_by_id=1
    )
    assert all(round_result["status"] == "complete" for round_result in result["rounds"])

    approved_topics = {item["topic"] for item in APTITUDE_TOPICS}
    persisted_topics = {row.name for row in db.query(AptitudeTopic).all()}
    assert approved_topics <= persisted_topics
    assert not any(name == name.lower() for name in persisted_topics)

    rows = (
        db.query(AptitudeQuestion)
        .filter(AptitudeQuestion.blueprint_id == blueprint.id,
                AptitudeQuestion.source == "llm_generated")
        .all()
    )
    assert len(rows) == POOL_SIZES["aptitude"]
    assert {row.topic.name for row in rows} <= approved_topics

    coding_topics = {"Cloud Fundamentals", "Scripting & Automation"}
    problems = (
        db.query(CodingProblem)
        .filter(CodingProblem.blueprint_id == blueprint.id,
                CodingProblem.source == "llm_generated")
        .all()
    )
    assert len(problems) == POOL_SIZES["coding"]
    assert all(set(problem.tags_list) <= coding_topics for problem in problems)


def test_unrelated_topic_still_fails_pool_with_actionable_error(db):
    """Canonicalization matches case/whitespace only: a genuinely different topic
    (not just a different case) still fails the pool and blocks publishing, so
    validation is not weakened."""
    blueprint = make_blueprint(db)

    def bad_aptitude(spec):
        items = make_aptitude_items(spec)
        for item in items:
            item["topic"] = "Data Structures & Algorithms"
        return items

    pool_gen = QuestionPoolGenerationService(
        llm_generator=FakePoolGenerator(aptitude=bad_aptitude)
    )
    result = pool_gen.generate_for_blueprint(db, blueprint, created_by_id=1)
    aptitude_status = next(
        item for item in result["rounds"] if item["round_type"] == "aptitude"
    )
    assert aptitude_status["status"] == "incomplete"
    assert "not in blueprint topics" in aptitude_status["generation_error"]
    assert (
        db.query(AptitudeQuestion)
        .filter(AptitudeQuestion.source == "llm_generated")
        .count()
        == 0
    )
