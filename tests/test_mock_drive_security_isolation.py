"""Security and candidate-isolation tests for the Mock Drive flow.

Covers three verified defects (see final report):
  A. Result/turn ownership: interview + coding result endpoints must only be
     readable by the owning candidate (or staff), never another candidate.
  B. Drive lifecycle separation: the shared MockDrive global status must stay
     "published" while candidates attempt it; completion is per-candidate.
  C. Round-completion integrity: "Complete Round" (manual /advance) must not
     bypass the blueprint aptitude round's "at least one attempt" rule.

These tests are HTTP-level and use an in-memory SQLite database (never the live
dev database), mirroring tests/test_mock_drive_blueprint_integration.py.
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
from app.models.aptitude import AptitudeAttempt, AptitudeQuestion, AptitudeTopic
from app.models.coding import CodingProblem, CodingSubmission
from app.models.interview import (
    ApprovedQuestionPool,
    InterviewSession,
    InterviewTurn,
)
from app.modules.interview.routers import interview_router as interview_router_module
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
            StudentProfile(
                user_id=user.id,
                cgpa=cgpa,
                backlogs_count=0,
                department="Computer Science",
            )
        )
        db_session.commit()
    return user


def _auth(user: User) -> dict:
    token = create_access_token(data={"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


def _published_coding_drive(client, tpo_headers, *, name="Isolation Co"):
    resp = client.post(
        "/api/v1/tpo/mock-drives",
        json={
            "company_name": name,
            "target_role": "Software Engineer",
            "minimum_cgpa": 0.0,
            "maximum_backlogs": 100,
            "selected_rounds": {"coding": True},
            "round_configurations": {
                "coding": {
                    "question_count": 5,
                    "duration_minutes": 30,
                    "difficulty_distribution": {
                        "easy": 0.5,
                        "medium": 0.5,
                        "hard": 0.0,
                    },
                }
            },
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


def _insert_interview(db_session, student_id: int, *, secret: str):
    session = AssessmentSession(
        user_id=student_id,
        status="in_progress",
        started_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(hours=3),
    )
    db_session.add(session)
    db_session.flush()
    interview = InterviewSession(
        session_id=session.id,
        phase="HR",
        current_turn=1,
        total_turns=5,
        rl_state={},
        status="ACTIVE",
    )
    db_session.add(interview)
    db_session.flush()
    db_session.add(
        InterviewTurn(
            interview_id=interview.id,
            turn_number=1,
            question_text=secret,
            candidate_response="my answer",
            content_score=0.8,
            final_score=0.8,
            is_followup=False,
        )
    )
    db_session.commit()
    return interview.id


# ══════════════════════════════════════════════════════════════════════
# Requirement 1: candidate cannot read/finish another candidate's interview
# ══════════════════════════════════════════════════════════════════════


def test_interview_report_and_status_are_candidate_isolated(
    client, db_session, monkeypatch
):
    monkeypatch.setattr(
        interview_router_module.groq_service,
        "generate_feedback_summary",
        lambda turns_data: "feedback",
    )
    student_a = _make_user(db_session, "student")
    other_b = _make_user(db_session, "student")
    tpo = _make_user(db_session, "tpo")
    secret = "SECRET_QUESTION_FROM_CANDIDATE_A"
    interview_id = _insert_interview(db_session, student_a.id, secret=secret)

    a_headers = _auth(student_a)
    b_headers = _auth(other_b)
    tpo_headers = _auth(tpo)

    # Owner can read status + report.
    status = client.get(
        f"/api/v1/interview/session/{interview_id}/status", headers=a_headers
    )
    assert status.status_code == 200
    assert status.json()["interview_id"] == interview_id

    report = client.get(
        f"/api/v1/interview/session/{interview_id}/report", headers=a_headers
    )
    assert report.status_code == 200
    assert secret in report.text

    # Another candidate gets 404 (no existence leak) and never sees the content.
    assert (
        client.get(
            f"/api/v1/interview/session/{interview_id}/status", headers=b_headers
        ).status_code
        == 404
    )
    b_report = client.get(
        f"/api/v1/interview/session/{interview_id}/report", headers=b_headers
    )
    assert b_report.status_code == 404
    assert secret not in b_report.text

    # Another candidate cannot complete it; interview stays ACTIVE.
    b_complete = client.post(
        f"/api/v1/interview/session/{interview_id}/complete", headers=b_headers
    )
    assert b_complete.status_code == 404
    db_session.expire_all()
    assert (
        db_session.query(InterviewSession).get(interview_id).status == "ACTIVE"
    )

    # Unauthenticated access is rejected with 401.
    assert (
        client.get(f"/api/v1/interview/session/{interview_id}/report").status_code
        == 401
    )

    # Staff may read (existing policy) but not complete (owner-only write).
    assert (
        client.get(
            f"/api/v1/interview/session/{interview_id}/report", headers=tpo_headers
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/interview/session/{interview_id}/complete", headers=tpo_headers
        ).status_code
        == 404
    )


# ══════════════════════════════════════════════════════════════════════
# Requirement 2: candidate cannot read/finish another candidate's coding submission
# ══════════════════════════════════════════════════════════════════════


def test_coding_submission_is_candidate_isolated(client, db_session):
    student_a = _make_user(db_session, "student")
    other_b = _make_user(db_session, "student")
    tpo = _make_user(db_session, "tpo")

    session = AssessmentSession(
        user_id=student_a.id,
        status="in_progress",
        started_at=datetime.utcnow(),
    )
    db_session.add(session)
    db_session.flush()
    problem = CodingProblem(
        title="Two Sum", description="Return indices", difficulty="easy"
    )
    db_session.add(problem)
    db_session.flush()
    round_obj = AssessmentRound(
        session_id=session.id, round_type="coding", status="completed"
    )
    db_session.add(round_obj)
    db_session.flush()
    submission = CodingSubmission(
        round_id=round_obj.id,
        problem_id=problem.id,
        code="print(1)",
        language="python",
        status="accepted",
        score=1.0,
    )
    db_session.add(submission)
    db_session.commit()
    submission_id = submission.id

    # Owner can read.
    owner = client.get(
        f"/api/v1/coding/submission/{submission_id}", headers=_auth(student_a)
    )
    assert owner.status_code == 200
    assert owner.json()["submission_id"] == submission_id
    assert owner.json()["score"] == 1.0

    # Another candidate gets 404.
    assert (
        client.get(
            f"/api/v1/coding/submission/{submission_id}", headers=_auth(other_b)
        ).status_code
        == 404
    )

    # Unauthenticated is 401.
    assert client.get(f"/api/v1/coding/submission/{submission_id}").status_code == 401

    # Staff follows existing read policy.
    assert (
        client.get(
            f"/api/v1/coding/submission/{submission_id}", headers=_auth(tpo)
        ).status_code
        == 200
    )


# ══════════════════════════════════════════════════════════════════════
# Requirement 3: authorized staff access + admin-only writes
# ══════════════════════════════════════════════════════════════════════


def test_pool_access_and_admin_only_approval(client, db_session):
    student_a = _make_user(db_session, "student")
    other_b = _make_user(db_session, "student")
    admin = _make_user(db_session, "admin")

    session = AssessmentSession(
        user_id=student_a.id, status="in_progress", started_at=datetime.utcnow()
    )
    db_session.add(session)
    db_session.flush()
    pool = ApprovedQuestionPool(
        session_id=session.id,
        question_pool=[
            {
                "question": "SECRET_POOL_QUESTION",
                "difficulty": "EASY",
                "topic": "General",
                "phase": "HR",
            }
        ],
        extracted_skills=[],
        extracted_projects={},
        admin_approved=False,
        detected_role="SDE",
    )
    db_session.add(pool)
    db_session.commit()
    pool_id = pool.id

    # Owner can read the pool.
    assert (
        client.get(
            f"/api/v1/interview/pool/{pool_id}", headers=_auth(student_a)
        ).status_code
        == 200
    )

    # Another candidate cannot.
    assert (
        client.get(
            f"/api/v1/interview/pool/{pool_id}", headers=_auth(other_b)
        ).status_code
        == 404
    )

    # Approval is admin-only: student + other candidate are forbidden.
    assert (
        client.put(
            f"/api/v1/interview/pool/{pool_id}/approve",
            json={"approved": True},
            headers=_auth(student_a),
        ).status_code
        == 403
    )
    assert (
        client.put(
            f"/api/v1/interview/pool/{pool_id}/approve",
            json={"approved": True},
            headers=_auth(other_b),
        ).status_code
        == 403
    )

    approved = client.put(
        f"/api/v1/interview/pool/{pool_id}/approve",
        json={"approved": True},
        headers=_auth(admin),
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"


def test_high_risk_sessions_is_admin_only(client, db_session):
    student = _make_user(db_session, "student")
    tpo = _make_user(db_session, "tpo")
    admin = _make_user(db_session, "admin")

    assert (
        client.get(
            "/api/v1/advanced-proctoring/high-risk-sessions", headers=_auth(student)
        ).status_code
        == 403
    )
    assert (
        client.get(
            "/api/v1/advanced-proctoring/high-risk-sessions", headers=_auth(tpo)
        ).status_code
        == 403
    )
    # Admin passes the authorization gate. (The underlying aggregate query uses
    # PostgreSQL JSONB operators and may not fully execute on SQLite, so only
    # the authorization outcome is asserted here.)
    assert (
        client.get(
            "/api/v1/advanced-proctoring/high-risk-sessions", headers=_auth(admin)
        ).status_code
        != 403
    )


# ══════════════════════════════════════════════════════════════════════
# Requirement 4 & 5: two candidates use the same published drive
# independently, and one candidate's completion does not affect the other
# ══════════════════════════════════════════════════════════════════════


def test_two_candidates_attempt_same_drive_independently(client, db_session):
    tpo = _make_user(db_session, "tpo")
    student_a = _make_user(db_session, "student")
    student_b = _make_user(db_session, "student")
    tpo_headers = _auth(tpo)
    a_headers = _auth(student_a)
    b_headers = _auth(student_b)

    drive_id = _published_coding_drive(client, tpo_headers)

    # Both candidates see the freshly published drive.
    assert drive_id in [
        d["id"]
        for d in client.get(
            "/api/v1/mock-drives/available", headers=a_headers
        ).json()
    ]
    assert drive_id in [
        d["id"]
        for d in client.get(
            "/api/v1/mock-drives/available", headers=b_headers
        ).json()
    ]

    # Candidate A starts.
    a_start = client.post(f"/api/v1/mock-drives/{drive_id}/start", headers=a_headers)
    assert a_start.status_code == 200, a_start.text
    assert a_start.json()["status"] == "in_progress"
    assert a_start.json()["current_round"] == "coding"

    # Global drive status must remain "published" (not "active"/"completed").
    drive_after_a_start = client.get(
        f"/api/v1/tpo/mock-drives/{drive_id}", headers=tpo_headers
    ).json()
    assert drive_after_a_start["status"] == "published"

    # Candidate B can still start the SAME drive.
    b_start = client.post(f"/api/v1/mock-drives/{drive_id}/start", headers=b_headers)
    assert b_start.status_code == 200, b_start.text
    assert b_start.json()["status"] == "in_progress"
    assert b_start.json()["session_id"] != a_start.json()["session_id"]

    # Candidate A completes (coding is the only round).
    a_advance = client.post(
        f"/api/v1/mock-drives/{drive_id}/advance", headers=a_headers
    )
    assert a_advance.status_code == 200, a_advance.text
    assert a_advance.json()["status"] == "completed"

    # Drive stays published after A's completion; B is unaffected.
    drive_after_a_done = client.get(
        f"/api/v1/tpo/mock-drives/{drive_id}", headers=tpo_headers
    ).json()
    assert drive_after_a_done["status"] == "published"

    b_status = client.get(f"/api/v1/mock-drives/{drive_id}/status", headers=b_headers)
    assert b_status.status_code == 200
    assert b_status.json()["status"] == "in_progress"
    assert b_status.json()["current_round"] == "coding"

    # A is now complete; restarting returns the graceful already-completed payload.
    a_restart = client.post(f"/api/v1/mock-drives/{drive_id}/start", headers=a_headers)
    assert a_restart.status_code == 200
    assert a_restart.json()["status"] == "completed"
    assert a_restart.json()["already_started"] is True

    # B still completes independently.
    b_advance = client.post(
        f"/api/v1/mock-drives/{drive_id}/advance", headers=b_headers
    )
    assert b_advance.status_code == 200, b_advance.text
    assert b_advance.json()["status"] == "completed"

    # The two attempts are distinct contexts.
    db_session.expire_all()
    ctx_ids = {
        c.id
        for c in db_session.query(AssessmentContext)
        .filter(
            AssessmentContext.mock_drive_id == drive_id,
            AssessmentContext.student_id.in_([student_a.id, student_b.id]),
        )
        .all()
    }
    assert a_start.json()["context_id"] in ctx_ids
    assert b_start.json()["context_id"] in ctx_ids
    assert a_start.json()["context_id"] != b_start.json()["context_id"]


# ══════════════════════════════════════════════════════════════════════
# Requirement 7: a completed drive is hidden from that candidate's list,
# but remains visible to other eligible candidates
# ══════════════════════════════════════════════════════════════════════


def test_completed_drive_hidden_from_own_list_but_visible_to_others(
    client, db_session
):
    tpo = _make_user(db_session, "tpo")
    student_a = _make_user(db_session, "student")
    student_b = _make_user(db_session, "student")
    tpo_headers = _auth(tpo)
    a_headers = _auth(student_a)
    b_headers = _auth(student_b)

    drive_id = _published_coding_drive(client, tpo_headers, name="Hide Completed Co")

    def _a_ids():
        return [
            d["id"]
            for d in client.get(
                "/api/v1/mock-drives/available", headers=a_headers
            ).json()
        ]

    def _b_ids():
        return [
            d["id"]
            for d in client.get(
                "/api/v1/mock-drives/available", headers=b_headers
            ).json()
        ]

    # Not started: visible to both eligible candidates.
    assert drive_id in _a_ids()
    assert drive_id in _b_ids()

    # In progress: still visible (not hidden until completed).
    assert (
        client.post(f"/api/v1/mock-drives/{drive_id}/start", headers=a_headers)
        .status_code
        == 200
    )
    assert drive_id in _a_ids()

    # Candidate A completes the single-round drive.
    done = client.post(f"/api/v1/mock-drives/{drive_id}/advance", headers=a_headers)
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "completed"

    # Hidden from A's list...
    assert drive_id not in _a_ids()
    # ...but B, who has not attempted it, still sees it.
    assert drive_id in _b_ids()

    # A's completed attempt stays reachable via the result endpoint.
    result = client.get(f"/api/v1/mock-drives/{drive_id}/result", headers=a_headers)
    assert result.status_code == 200, result.text
    own_history = client.get("/api/v1/mock-drives/history", headers=a_headers)
    other_history = client.get("/api/v1/mock-drives/history", headers=b_headers)
    assert own_history.status_code == 200
    assert any(item["mock_drive_id"] == drive_id for item in own_history.json())
    assert all(item["mock_drive_id"] != drive_id for item in other_history.json())


# ══════════════════════════════════════════════════════════════════════
# Requirement 6: premature / unauthorized round completion is rejected
# ══════════════════════════════════════════════════════════════════════


def _approved_aptitude_snapshot():
    return {
        "status": "approved",
        "blueprint_version": 1,
        "enabled_rounds": ["aptitude", "coding"],
        "blueprint_data": {
            "rounds": [
                {
                    "round_type": "aptitude",
                    "round_order": 1,
                    "question_count": 5,
                    "time_limit_minutes": 45,
                },
                {
                    "round_type": "coding",
                    "round_order": 2,
                    "question_count": 2,
                    "time_limit_minutes": 30,
                },
            ]
        },
    }


def _seed_active_aptitude_drive(db_session, student, *, with_attempt: bool):
    snapshot = _approved_aptitude_snapshot()
    drive = MockDrive(
        company_name="Premature Co",
        target_role="Software Engineer",
        status="published",
        minimum_cgpa=0.0,
        maximum_backlogs=100,
        eligible_branches=[],
        selected_rounds={"aptitude": True, "coding": True},
        round_configurations={},
        blueprint_snapshot=snapshot,
        created_by_id=student.id,
    )
    db_session.add(drive)
    db_session.flush()
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
    db_session.add(ctx)
    db_session.flush()
    session = AssessmentSession(
        user_id=student.id,
        context_id=ctx.id,
        status="in_progress",
        started_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(hours=3),
    )
    db_session.add(session)
    db_session.flush()
    apt_round = AssessmentRound(
        session_id=session.id,
        round_type="aptitude",
        status="active",
        max_questions=5,
    )
    db_session.add(apt_round)
    db_session.flush()

    if with_attempt:
        topic = AptitudeTopic(name=f"Topic {uuid.uuid4().hex[:6]}")
        db_session.add(topic)
        db_session.flush()
        question = AptitudeQuestion(
            question_text="1 + 1 = ?",
            option_a="1",
            option_b="2",
            option_c="3",
            option_d="4",
            correct_option="B",
            difficulty="easy",
            topic_id=topic.id,
        )
        db_session.add(question)
        db_session.flush()
        db_session.add(
            AptitudeAttempt(
                round_id=apt_round.id,
                question_id=question.id,
                attempt_number=1,
                selected_option="B",
                is_correct=True,
                response_time=1.0,
                difficulty="easy",
            )
        )

    db_session.commit()
    return drive.id, session.id, apt_round.id


def test_premature_aptitude_completion_is_rejected_then_allowed(client, db_session):
    student = _make_user(db_session, "student")
    drive_id, session_id, apt_round_id = _seed_active_aptitude_drive(
        db_session, student, with_attempt=False
    )
    headers = _auth(student)

    # No completed aptitude work -> 409 and the round stays active.
    resp = client.post(f"/api/v1/mock-drives/{drive_id}/advance", headers=headers)
    assert resp.status_code == 409, resp.text
    db_session.expire_all()
    assert db_session.query(AssessmentRound).get(apt_round_id).status == "active"
    assert (
        db_session.query(AssessmentRound)
        .filter(
            AssessmentRound.session_id == session_id,
            AssessmentRound.round_type == "coding",
        )
        .count()
        == 0
    )

    # Record one attempt, then completion is allowed and advances to coding.
    topic = AptitudeTopic(name=f"T {uuid.uuid4().hex[:6]}")
    db_session.add(topic)
    db_session.flush()
    question = AptitudeQuestion(
        question_text="2 + 2 = ?",
        option_a="1",
        option_b="2",
        option_c="3",
        option_d="4",
        correct_option="D",
        difficulty="easy",
        topic_id=topic.id,
    )
    db_session.add(question)
    db_session.flush()
    db_session.add(
        AptitudeAttempt(
            round_id=apt_round_id,
            question_id=question.id,
            attempt_number=1,
            selected_option="D",
            is_correct=True,
            response_time=1.0,
            difficulty="easy",
        )
    )
    db_session.commit()

    ok = client.post(f"/api/v1/mock-drives/{drive_id}/advance", headers=headers)
    assert ok.status_code == 200, ok.text
    assert ok.json()["current_round"] == "coding"
    assert ok.json()["status"] == "in_progress"


def test_unauthorized_candidate_cannot_advance_or_complete_anothers_attempt(
    client, db_session
):
    tpo = _make_user(db_session, "tpo")
    student_a = _make_user(db_session, "student")
    other_b = _make_user(db_session, "student")
    tpo_headers = _auth(tpo)

    drive_id = _published_coding_drive(client, tpo_headers, name="Advance Guard Co")

    a_start = client.post(
        f"/api/v1/mock-drives/{drive_id}/start", headers=_auth(student_a)
    )
    assert a_start.status_code == 200, a_start.text

    # Candidate B has no attempt for this drive -> cannot advance it.
    b_advance = client.post(
        f"/api/v1/mock-drives/{drive_id}/advance", headers=_auth(other_b)
    )
    assert b_advance.status_code == 404

    # Candidate A's attempt is untouched.
    a_status = client.get(
        f"/api/v1/mock-drives/{drive_id}/status", headers=_auth(student_a)
    )
    assert a_status.status_code == 200
    assert a_status.json()["status"] == "in_progress"
    assert a_status.json()["current_round"] == "coding"

    # Candidate B never got a session.
    b_status = client.get(
        f"/api/v1/mock-drives/{drive_id}/status", headers=_auth(other_b)
    )
    assert b_status.status_code == 200
    assert b_status.json()["status"] == "not_started"


# ══════════════════════════════════════════════════════════════════════
# Requirement 6 (Phase 4C P2): legacy session endpoints must not bypass the
# Mock Drive lifecycle (competency mapping + per-candidate completion).
# ══════════════════════════════════════════════════════════════════════


def _mock_drive_active_session(db_session, student, *, status="in_progress"):
    drive = MockDrive(
        company_name=f"P2 Drive {uuid.uuid4().hex[:6]}",
        target_role="Engineer",
        status="published",
        minimum_cgpa=0.0,
        maximum_backlogs=100,
        eligible_branches=[],
        selected_rounds={"aptitude": True},
        round_configurations={},
        created_by_id=student.id,
    )
    db_session.add(drive)
    db_session.flush()
    ctx = AssessmentContext(
        mode="mock_drive",
        purpose="mock_drive",
        student_id=student.id,
        company_name=drive.company_name,
        target_role=drive.target_role,
        policy_id=DEFAULT_PRACTICE_POLICY_ID,
        mock_drive_id=drive.id,
        blueprint_snapshot={},
        status="active",
    )
    db_session.add(ctx)
    db_session.flush()
    session = AssessmentSession(
        user_id=student.id,
        context_id=ctx.id,
        status=status,
        started_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(hours=3),
    )
    db_session.add(session)
    db_session.commit()
    return drive, ctx, session


def test_complete_session_rejects_active_mock_drive_attempt(client, db_session):
    student = _make_user(db_session, "student")
    _, _, session = _mock_drive_active_session(db_session, student)

    resp = client.post("/api/v1/session/complete", headers=_auth(student))
    assert resp.status_code == 409, resp.text

    db_session.expire_all()
    assert db_session.query(AssessmentSession).get(session.id).status == "in_progress"


def test_fresh_session_rejects_active_mock_drive_attempt(client, db_session):
    student = _make_user(db_session, "student")
    _, _, session = _mock_drive_active_session(db_session, student)

    resp = client.post("/api/v1/session/fresh", headers=_auth(student))
    assert resp.status_code == 409, resp.text

    # No replacement standalone session was created and the attempt is intact.
    db_session.expire_all()
    sessions = db_session.query(AssessmentSession).filter(
        AssessmentSession.user_id == student.id
    ).all()
    assert [s.id for s in sessions] == [session.id]
    assert sessions[0].status == "in_progress"


def test_complete_and_fresh_still_work_for_standalone_sessions(client, db_session):
    student = _make_user(db_session, "student")
    db_session.add(
        AssessmentSession(
            user_id=student.id,
            context_id=None,
            status="in_progress",
            started_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=3),
        )
    )
    db_session.commit()

    complete = client.post("/api/v1/session/complete", headers=_auth(student))
    assert complete.status_code == 200, complete.text
    assert complete.json()["status"] == "completed"

    fresh = client.post("/api/v1/session/fresh", headers=_auth(student))
    assert fresh.status_code == 201, fresh.text
    assert fresh.json()["status"] == "in_progress"


def test_competency_mapping_reprocess_is_tpo_admin_only(client, db_session):
    tpo = _make_user(db_session, "tpo")
    student = _make_user(db_session, "student")
    drive_id = _published_coding_drive(client, _auth(tpo), name="Reprocess Guard Co")

    # Students cannot trigger recovery.
    assert (
        client.post(
            f"/api/v1/tpo/mock-drives/{drive_id}/competency-mapping/reprocess",
            headers=_auth(student),
        ).status_code
        == 403
    )

    # TPO passes the gate; no completed attempts yet -> nothing examined.
    ok = client.post(
        f"/api/v1/tpo/mock-drives/{drive_id}/competency-mapping/reprocess",
        headers=_auth(tpo),
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["examined"] == 0


def test_start_new_drive_finalizes_active_mock_drive_attempt_via_lifecycle(
    client, db_session
):
    # Starting a different drive must end the previous Mock Drive attempt
    # through the Mock Drive lifecycle (per-candidate completion + mapping
    # status), never via the generic session API which would bypass mapping.
    student = _make_user(db_session, "student")
    tpo = _make_user(db_session, "tpo")
    drive_a, ctx_a, session_a = _mock_drive_active_session(db_session, student)
    drive_b_id = _published_coding_drive(client, _auth(tpo), name="Drive B Guard Co")

    resp = client.post(
        f"/api/v1/mock-drives/{drive_b_id}/start", headers=_auth(student)
    )
    assert resp.status_code == 200, resp.text

    db_session.expire_all()
    # The previous attempt was finalized through the lifecycle...
    assert db_session.query(AssessmentSession).get(session_a.id).status == "completed"
    db_session.refresh(ctx_a)
    assert ctx_a.status == "completed"
    # ...which runs the mapping status step (a raw session-complete would leave
    # this as None, the original bypass).
    assert ctx_a.competency_mapping_status == "not_applicable"
    # The new drive attempt starts cleanly with its own session.
    new_session = db_session.query(AssessmentSession).filter(
        AssessmentSession.user_id == student.id,
        AssessmentSession.status == "in_progress",
    ).one()
    assert new_session.id != session_a.id
    assert new_session.context_id != ctx_a.id


def test_start_drive_still_ends_stale_standalone_session(client, db_session):
    # Practice/standalone behavior is unchanged: a stale non-Mock-Drive session
    # is still completed so the new Mock Drive attempt starts cleanly.
    student = _make_user(db_session, "student")
    tpo = _make_user(db_session, "tpo")
    db_session.add(
        AssessmentSession(
            user_id=student.id,
            context_id=None,
            status="in_progress",
            started_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=3),
        )
    )
    db_session.commit()
    drive_id = _published_coding_drive(client, _auth(tpo), name="Standalone End Co")

    resp = client.post(
        f"/api/v1/mock-drives/{drive_id}/start", headers=_auth(student)
    )
    assert resp.status_code == 200, resp.text

    db_session.expire_all()
    sessions = (
        db_session.query(AssessmentSession)
        .filter(AssessmentSession.user_id == student.id)
        .order_by(AssessmentSession.id)
        .all()
    )
    assert len(sessions) == 2
    assert sessions[0].status == "completed"
    assert sessions[1].status == "in_progress"
