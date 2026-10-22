"""
Regression tests for the blueprint-driven aptitude assessment flow.

Reported bug: the aptitude assessment reported "no aptitude questions were
completed" when submitting, even though questions had been served and answered.

These tests drive the real HTTP chain (start mock drive -> next-question ->
submit-answer -> finish) so assignment, answer-persistence and
completion-tracking identifiers are exercised exactly as the frontend uses them.
"""

import json
import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.db import get_db
from app.main import app as application
from app.models.user import User
from app.models.profile import StudentProfile
from app.models.company_data import CompanyBlueprint
from app.models.assessment_context import AssessmentContext, AssessmentPolicy
from app.models.assessment import AssessmentRound, AssessmentSession
from app.modules.aptitude.routers.aptitude_router import _session_aptitude_attempt_count

from app.models.aptitude import AptitudeAttempt, AptitudeQuestion, AptitudeRoundQuestion, AptitudeTopic
from app.models.question_pool_generation import POOL_STATUS_COMPLETE
from app.services.assessment_context_service import DEFAULT_PRACTICE_POLICY_ID
from app.services.question_pool_generation_service import QuestionPoolGenerationService
from app.config.security import create_access_token


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

import app.models.user
import app.models.company_data
import app.models.mock_drive
import app.models.assessment_context
import app.models.assessment
import app.models.aptitude
import app.models.question_pool_generation


@pytest.fixture(scope="module", autouse=True)
def setup_db_override():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    if not db.query(AssessmentPolicy).filter(AssessmentPolicy.id == DEFAULT_PRACTICE_POLICY_ID).first():
        db.add(AssessmentPolicy(
            id=DEFAULT_PRACTICE_POLICY_ID,
            name="Default Practice Policy",
            session_duration_minutes=180,
            round_duration_minutes=30,
            resume_allowed=True,
            exit_allowed=True,
            progression_mode="sequential",
            progression_config={"rounds": ["aptitude", "coding", "interview"]},
        ))
        db.commit()
    db.close()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    application.dependency_overrides[get_db] = override_get_db
    yield
    application.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)


client = TestClient(application)


def _make_user(role, *, profile=False):
    uid = uuid.uuid4().hex[:8]
    user = User(
        name=f"Test {role}",
        email=f"{role}_{uid}@test.com",
        role=role,
        password_hash="pw",
    )
    db = TestingSessionLocal()
    db.add(user)
    db.commit()
    db.refresh(user)
    if profile:
        db.add(StudentProfile(
            user_id=user.id,
            cgpa=8.5,
            backlogs_count=0,
            department="Computer Science",
        ))
        db.commit()
    token = create_access_token(data={"sub": str(user.id)})
    db.close()
    return {"Authorization": f"Bearer {token}"}, user.id


@pytest.fixture(scope="module")
def tpo_headers():
    return _make_user("tpo")[0]


@pytest.fixture(scope="module")
def student_headers():
    return _make_user("student", profile=True)[0]


def _seed_blueprint(company, role, *, question_count=4):
    db = TestingSessionLocal()
    tpo_id = db.query(User).filter(User.role == "tpo").first().id
    blueprint = CompanyBlueprint(
        company_name=company,
        target_role=role,
        status="approved",
        version=1,
        blueprint_data={"rounds": [{
            "round_type": "aptitude",
            "round_order": 1,
            "question_count": question_count,
            "time_limit_minutes": 60,
            "question_types": ["MCQ"],
            "topics": [
                {"topic": "Quantitative Aptitude", "weight_pct": 50},
                {"topic": "Logical Reasoning", "weight_pct": 50},
            ],
            "difficulty_distribution": {"easy": 50, "medium": 50},
        }]},
        confidence_level="high",
        evidence_sources_count=1,
        created_by_id=tpo_id,
    )
    db.add(blueprint)
    db.commit()
    db.refresh(blueprint)

    for name in ("Quantitative Aptitude", "Logical Reasoning"):
        topic = db.query(AptitudeTopic).filter(AptitudeTopic.name == name).first()
        if topic is None:
            topic = AptitudeTopic(name=name)
            db.add(topic)
            db.flush()
        if db.query(AptitudeQuestion).filter(AptitudeQuestion.topic_id == topic.id).count() == 0:
            for difficulty in ("easy", "medium"):
                for duplicate in range(3):
                    db.add(AptitudeQuestion(
                        question_text=f"{name} {difficulty} {duplicate}",
                        option_a="A",
                        option_b="B",
                        option_c="C",
                        option_d="D",
                        correct_option="A",
                        difficulty=difficulty,
                        topic_id=topic.id,
                        is_active=True,
                    ))
    db.commit()
    blueprint_id = blueprint.id
    db.close()
    return blueprint_id


def _create_and_start_drive(tpo_headers, student_headers, company, role, blueprint_id):
    create = client.post(
        "/api/v1/tpo/mock-drives",
        json={
            "company_name": company,
            "target_role": role,
            "selected_rounds": {"aptitude": True},
            "blueprint_id": blueprint_id,
        },
        headers=tpo_headers,
    )
    assert create.status_code == 201, create.text
    drive_id = create.json()["id"]
    publish = client.post(f"/api/v1/tpo/mock-drives/{drive_id}/publish", headers=tpo_headers)
    assert publish.status_code == 200, publish.text
    start = client.post(f"/api/v1/mock-drives/{drive_id}/start", headers=student_headers)
    assert start.status_code == 200, start.text
    return drive_id, start.json()


def test_blueprint_aptitude_questions_load_and_submit_persist_and_finish(tpo_headers, student_headers):
    company = f"Flow Co {uuid.uuid4().hex[:8]}"
    role = "Software Engineer"
    blueprint_id = _seed_blueprint(company, role, question_count=4)
    _drive_id, started = _create_and_start_drive(tpo_headers, student_headers, company, role, blueprint_id)

    served = []
    for index in range(1, 5):
        q_res = client.get("/api/v1/aptitude/next-question", headers=student_headers)
        assert q_res.status_code == 200, q_res.text
        question = q_res.json()
        assert question["question_number"] == index, question
        assert question["max_questions"] == 4, question
        served.append(question["question_id"])

        submit = client.post(
            "/api/v1/aptitude/submit-answer",
            json={
                "question_id": question["question_id"],
                "selected_option": "A",
                "response_time": 1.0,
            },
            headers=student_headers,
        )
        assert submit.status_code == 200, submit.text

    assert len(set(served)) == 4

    db = TestingSessionLocal()
    active_round = db.query(AssessmentRound).filter(
        AssessmentRound.session_id == started["session_id"],
        AssessmentRound.status == "active",
    ).first()
    attempt_count = db.query(AptitudeAttempt).filter(AptitudeAttempt.round_id == active_round.id).count()
    assigned_ids = {
        row[0] for row in db.query(AptitudeRoundQuestion.question_id).filter(
            AptitudeRoundQuestion.round_id == active_round.id
        ).all()
    }
    db.close()

    assert attempt_count == 4
    assert set(served) == assigned_ids

    finish = client.post("/api/v1/aptitude/finish", headers=student_headers)
    assert finish.status_code == 200, finish.text
    assert finish.json()["status"] == "finalized"


def test_blueprint_aptitude_resume_mid_round_keeps_attempts_and_finishes(tpo_headers, student_headers):
    company = f"Resume Co {uuid.uuid4().hex[:8]}"
    role = "Software Engineer"
    blueprint_id = _seed_blueprint(company, role, question_count=4)
    drive_id, started = _create_and_start_drive(tpo_headers, student_headers, company, role, blueprint_id)

    for _ in (1, 2):
        q = client.get("/api/v1/aptitude/next-question", headers=student_headers)
        assert q.status_code == 200, q.text
        r = client.post(
            "/api/v1/aptitude/submit-answer",
            headers=student_headers,
            json={"question_id": q.json()["question_id"], "selected_option": "A", "response_time": 1.0},
        )
        assert r.status_code == 200, r.text

    resume = client.post(f"/api/v1/mock-drives/{drive_id}/start", headers=student_headers)
    assert resume.status_code == 200, resume.text
    assert resume.json()["already_started"] is True

    for _ in (3, 4):
        q = client.get("/api/v1/aptitude/next-question", headers=student_headers)
        assert q.status_code == 200, q.text
        r = client.post(
            "/api/v1/aptitude/submit-answer",
            headers=student_headers,
            json={"question_id": q.json()["question_id"], "selected_option": "A", "response_time": 1.0},
        )
        assert r.status_code == 200, r.text

    finish = client.post("/api/v1/aptitude/finish", headers=student_headers)
    assert finish.status_code == 200, finish.text
    assert finish.json()["status"] == "finalized"


def test_blueprint_aptitude_finish_after_round_recreation_is_not_blocked(tpo_headers, student_headers):
    company = f"Recreate Co {uuid.uuid4().hex[:8]}"
    role = "Software Engineer"
    blueprint_id = _seed_blueprint(company, role, question_count=4)
    _drive_id, started = _create_and_start_drive(tpo_headers, student_headers, company, role, blueprint_id)

    q = client.get("/api/v1/aptitude/next-question", headers=student_headers)
    assert q.status_code == 200, q.text
    submit = client.post(
        "/api/v1/aptitude/submit-answer",
        headers=student_headers,
        json={"question_id": q.json()["question_id"], "selected_option": "A", "response_time": 1.0},
    )
    assert submit.status_code == 200, submit.text

    from app.services import session_service

    db = TestingSessionLocal()
    first_round = db.query(AssessmentRound).filter(
        AssessmentRound.session_id == started["session_id"],
        AssessmentRound.status == "active",
    ).first()
    assert db.query(AptitudeAttempt).filter(AptitudeAttempt.round_id == first_round.id).count() == 1
    session_service.expire_round(db, first_round.id)
    recreated = session_service.create_round(db, started["session_id"], "aptitude")
    assert recreated.status == "active"
    new_round_attempts = db.query(AptitudeAttempt).filter(
        AptitudeAttempt.round_id == recreated.id
    ).count()
    db.close()
    assert new_round_attempts == 0

    finish = client.post("/api/v1/aptitude/finish", headers=student_headers)
    assert finish.status_code == 200, finish.text
    assert finish.json()["status"] == "finalized"


def test_blueprint_aptitude_finish_without_answers_is_rejected(tpo_headers, student_headers):
    company = f"Empty Co {uuid.uuid4().hex[:8]}"
    role = "Software Engineer"
    blueprint_id = _seed_blueprint(company, role, question_count=4)
    _drive_id, _started = _create_and_start_drive(tpo_headers, student_headers, company, role, blueprint_id)

    finish = client.post("/api/v1/aptitude/finish", headers=student_headers)
    assert finish.status_code == 409, finish.text
    assert "no aptitude questions were completed" in finish.json()["detail"]


# ── Generated (LLM) pool path ────────────────────────────────────────
#
# The reported bug is the /aptitude/finish 409 when zero attempts were
# recorded. A blueprint whose aptitude round is backed by a validated
# LLM-generated pool takes a different loading path than the seeded bank
# (pool-only scope). This test drives the full HTTP chain on that path to
# prove served IDs == submitted IDs == assigned IDs and that attempts are
# persisted, so /aptitude/finish cannot 409 for a freshly published drive.

_APTITUDE_TOPICS = [
    {"topic": "Cloud Fundamentals", "weight_pct": 20},
    {"topic": "Computer Networks", "weight_pct": 15},
    {"topic": "Operating Systems", "weight_pct": 15},
    {"topic": "Scripting & Automation", "weight_pct": 20},
    {"topic": "Security Fundamentals", "weight_pct": 15},
    {"topic": "Cost Optimization", "weight_pct": 15},
]


class _FakePoolGenerator:
    """Deterministic stand-in for the pool LLM; identical shape to the real one."""

    def generate_aptitude_question_pool(self, spec):
        positions = spec.get("positions") or []
        offset = int(spec.get("position_offset") or 0)
        items = []
        for index, position in enumerate(positions, start=offset + 1):
            items.append({
                "question_text": f"Generated aptitude Q{index} about {position['topic']}?",
                "option_a": "a1", "option_b": "b1", "option_c": "c1", "option_d": "d1",
                "correct_option": "A",
                "difficulty": position.get("difficulty") or "medium",
                "topic": position["topic"],
                "explanation": "Correct answer justification.",
            })
        return items

    def generate_coding_problem_pool(self, spec):  # pragma: no cover - not enabled
        return []

    def generate_interview_question_pool(self, spec):  # pragma: no cover - not enabled
        return []


def _seed_generated_blueprint(company, role, *, question_count=5):
    """Approved LLM-provenance blueprint with a validated aptitude pool."""
    db = TestingSessionLocal()
    tpo_id = db.query(User).filter(User.role == "tpo").first().id
    blueprint = CompanyBlueprint(
        company_name=company,
        target_role=role,
        status="approved",
        version=1,
        blueprint_data={
            "company_name": company,
            "target_role": role,
            "rounds": [{
                "round_type": "aptitude",
                "round_order": 1,
                "question_count": question_count,
                "time_limit_minutes": 30,
                "topics": _APTITUDE_TOPICS,
                "difficulty_distribution": {"easy": 0.25, "medium": 0.5, "hard": 0.25},
            }],
            "source_provenance": {
                "classification": "llm_role_assessment",
                "selection_status": "role_assessment_generated",
                "empirical_source_count": 0,
            },
        },
        created_by_id=tpo_id,
    )
    db.add(blueprint)
    db.commit()
    db.refresh(blueprint)

    service = QuestionPoolGenerationService(llm_generator=_FakePoolGenerator())
    result = service.generate_for_blueprint(db, blueprint, created_by_id=tpo_id)
    aptitude_status = next(
        item for item in result["rounds"] if item["round_type"] == "aptitude"
    )
    assert aptitude_status["status"] == POOL_STATUS_COMPLETE, aptitude_status
    blueprint_id = blueprint.id
    db.close()
    return blueprint_id


def test_blueprint_aptitude_generated_pool_loads_submits_and_finishes(tpo_headers, student_headers):
    company = f"Generated Co {uuid.uuid4().hex[:8]}"
    role = "Cloud Engineer"
    blueprint_id = _seed_generated_blueprint(company, role, question_count=5)
    _drive_id, started = _create_and_start_drive(
        tpo_headers, student_headers, company, role, blueprint_id
    )

    served = []
    for index in range(1, 6):
        q_res = client.get("/api/v1/aptitude/next-question", headers=student_headers)
        assert q_res.status_code == 200, q_res.text
        question = q_res.json()
        assert question["question_number"] == index, question
        assert question["max_questions"] == 5, question
        served.append(question["question_id"])

        submit = client.post(
            "/api/v1/aptitude/submit-answer",
            json={
                "question_id": question["question_id"],
                "selected_option": "A",
                "response_time": 1.0,
            },
            headers=student_headers,
        )
        assert submit.status_code == 200, submit.text

    assert len(set(served)) == 5

    db = TestingSessionLocal()
    active_round = db.query(AssessmentRound).filter(
        AssessmentRound.session_id == started["session_id"],
        AssessmentRound.status == "active",
    ).first()
    attempt_count = db.query(AptitudeAttempt).filter(
        AptitudeAttempt.round_id == active_round.id
    ).count()
    assigned_ids = {
        row[0] for row in db.query(AptitudeRoundQuestion.question_id).filter(
            AptitudeRoundQuestion.round_id == active_round.id
        ).all()
    }
    pool_ids = {
        row[0] for row in db.query(AptitudeQuestion.id).filter(
            AptitudeQuestion.source == "llm_generated",
            AptitudeQuestion.blueprint_id == blueprint_id,
        ).all()
    }
    db.close()

    assert attempt_count == 5
    assert set(served) == assigned_ids
    assert assigned_ids <= pool_ids

    finish = client.post("/api/v1/aptitude/finish", headers=student_headers)
    assert finish.status_code == 200, finish.text
    assert finish.json()["status"] == "finalized"


def test_blueprint_aptitude_timeout_does_not_false_409_or_mark_complete(
    tpo_headers, student_headers
):
    """An overdue round must not raise the false 'no questions completed' 409.

    Server-authoritative timing expires the round; the candidate must not be
    told they answered nothing, and the drive must not be re-created with a
    fresh deadline. Because this drive's only round has now timed out, timeout
    recovery finalizes the attempt (G5) rather than stranding it in_progress.
    """
    company = f"Timeout Co {uuid.uuid4().hex[:8]}"
    role = "Software Engineer"
    blueprint_id = _seed_blueprint(company, role, question_count=4)
    drive_id, started = _create_and_start_drive(
        tpo_headers, student_headers, company, role, blueprint_id
    )

    question = client.get("/api/v1/aptitude/next-question", headers=student_headers)
    assert question.status_code == 200, question.text
    submit = client.post(
        "/api/v1/aptitude/submit-answer",
        json={"question_id": question.json()["question_id"], "selected_option": "A", "response_time": 1.0},
        headers=student_headers,
    )
    assert submit.status_code == 200, submit.text

    db = TestingSessionLocal()
    overdue = db.query(AssessmentRound).filter(
        AssessmentRound.session_id == started["session_id"],
        AssessmentRound.status == "active",
    ).first()
    overdue.expires_at = datetime.utcnow() - timedelta(minutes=5)
    overdue_id = overdue.id
    db.commit()
    db.close()

    finish = client.post("/api/v1/aptitude/finish", headers=student_headers)
    assert finish.status_code == 200, finish.text
    body = finish.json()
    assert body["status"] != "finalized", body
    assert "no aptitude questions were completed" not in json.dumps(body)

    # The sole round already timed out, so the attempt was finalized by timeout
    # recovery. A subsequent manual advance therefore finds no in-progress
    # attempt (404) or reports the expiry (410).
    advance = client.post(f"/api/v1/mock-drives/{drive_id}/advance", headers=student_headers)
    assert advance.status_code in (404, 410), advance.text

    db = TestingSessionLocal()
    expired_round = db.query(AssessmentRound).filter(AssessmentRound.id == overdue_id).first()
    session = db.query(AssessmentSession).filter(
        AssessmentSession.id == started["session_id"]
    ).first()
    db.close()
    assert expired_round.status == "expired"
    assert session.status == "completed"


def test_blueprint_aptitude_attempt_count_is_session_and_round_type_scoped(
    tpo_headers, student_headers
):
    """The completion count must not leak across sessions or non-aptitude rounds."""
    company = f"Scope Co {uuid.uuid4().hex[:8]}"
    role = "Software Engineer"
    blueprint_id = _seed_blueprint(company, role, question_count=4)
    drive_id, started = _create_and_start_drive(
        tpo_headers, student_headers, company, role, blueprint_id
    )

    question = client.get("/api/v1/aptitude/next-question", headers=student_headers)
    assert question.status_code == 200, question.text
    submit = client.post(
        "/api/v1/aptitude/submit-answer",
        json={"question_id": question.json()["question_id"], "selected_option": "A", "response_time": 1.0},
        headers=student_headers,
    )
    assert submit.status_code == 200, submit.text

    db = TestingSessionLocal()
    # A dedicated unrelated session (fresh user) carrying an aptitude attempt on
    # a NON-aptitude round: it must never satisfy this session's completion check.
    _, other_user_id = _make_user("student", profile=True)
    sibling = AssessmentSession(user_id=other_user_id, status="in_progress")
    db.add(sibling)
    db.flush()
    coding_round = AssessmentRound(
        session_id=sibling.id, round_type="coding", status="active"
    )
    db.add(coding_round)
    db.flush()
    question_row = db.query(AptitudeQuestion).first()
    db.add(AptitudeAttempt(
        round_id=coding_round.id,
        question_id=question_row.id,
        attempt_number=1,
        selected_option="A",
        is_correct=True,
        response_time=1.0,
    ))
    db.commit()

    answered_session_count = _session_aptitude_attempt_count(db, started["session_id"])
    sibling_count = _session_aptitude_attempt_count(db, sibling.id)
    db.close()

    assert answered_session_count == 1
    assert sibling_count == 0


def test_blueprint_aptitude_finish_is_idempotent(tpo_headers, student_headers):
    """Repeated finish must not duplicate completion or corrupt progression."""
    company = f"Idempotent Co {uuid.uuid4().hex[:8]}"
    role = "Software Engineer"
    blueprint_id = _seed_blueprint(company, role, question_count=4)
    _drive_id, started = _create_and_start_drive(
        tpo_headers, student_headers, company, role, blueprint_id
    )

    for _ in range(4):
        question = client.get("/api/v1/aptitude/next-question", headers=student_headers)
        assert question.status_code == 200, question.text
        submit = client.post(
            "/api/v1/aptitude/submit-answer",
            json={"question_id": question.json()["question_id"], "selected_option": "A", "response_time": 1.0},
            headers=student_headers,
        )
        assert submit.status_code == 200, submit.text

    first = client.post("/api/v1/aptitude/finish", headers=student_headers)
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "finalized"

    db = TestingSessionLocal()
    completed_rounds = db.query(AssessmentRound).filter(
        AssessmentRound.session_id == started["session_id"],
        AssessmentRound.status == "completed",
    ).count()
    attempt_count = (
        db.query(AptitudeAttempt)
        .join(AssessmentRound, AssessmentRound.id == AptitudeAttempt.round_id)
        .filter(AssessmentRound.session_id == started["session_id"])
        .count()
    )
    session_score = db.query(AssessmentSession).filter(
        AssessmentSession.id == started["session_id"]
    ).first().total_score
    db.close()
    assert completed_rounds == 1
    assert attempt_count == 4

    second = client.post("/api/v1/aptitude/finish", headers=student_headers)
    assert second.status_code == 200, second.text
    assert second.json()["status"] == "no_active_round"

    db = TestingSessionLocal()
    completed_rounds_after = db.query(AssessmentRound).filter(
        AssessmentRound.session_id == started["session_id"],
        AssessmentRound.status == "completed",
    ).count()
    session_score_after = db.query(AssessmentSession).filter(
        AssessmentSession.id == started["session_id"]
    ).first().total_score
    db.close()
    assert completed_rounds_after == 1
    assert session_score_after == session_score


def test_blueprint_aptitude_manual_advance_after_round_recreation_uses_session_attempts(
    tpo_headers, student_headers
):
    """The manual 'Complete Round' guard must also honor session-wide attempts."""
    from app.services import session_service

    company = f"Advance Co {uuid.uuid4().hex[:8]}"
    role = "Software Engineer"
    blueprint_id = _seed_blueprint(company, role, question_count=4)
    drive_id, started = _create_and_start_drive(
        tpo_headers, student_headers, company, role, blueprint_id
    )

    question = client.get("/api/v1/aptitude/next-question", headers=student_headers)
    assert question.status_code == 200, question.text
    submit = client.post(
        "/api/v1/aptitude/submit-answer",
        json={"question_id": question.json()["question_id"], "selected_option": "A", "response_time": 1.0},
        headers=student_headers,
    )
    assert submit.status_code == 200, submit.text

    db = TestingSessionLocal()
    first_round = db.query(AssessmentRound).filter(
        AssessmentRound.session_id == started["session_id"],
        AssessmentRound.status == "active",
    ).first()
    session_service.expire_round(db, first_round.id)
    recreated = session_service.create_round(db, started["session_id"], "aptitude")
    recreated_attempts = db.query(AptitudeAttempt).filter(
        AptitudeAttempt.round_id == recreated.id
    ).count()
    db.close()
    assert recreated_attempts == 0

    advance = client.post(f"/api/v1/mock-drives/{drive_id}/advance", headers=student_headers)
    assert advance.status_code == 200, advance.text
    assert advance.json()["status"] == "completed"
