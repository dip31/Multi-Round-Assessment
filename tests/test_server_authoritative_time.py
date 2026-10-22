"""Server-authoritative time enforcement tests (EDI5 Phase 4C Part 3).

Verifies that the persisted round/session deadlines are the sole authority for
assessment timing and that no client-supplied value can extend or bypass them.

Covered scenarios:
  1. A valid, in-time submission is accepted.
  2. An expired submission / round-completion is rejected server-side.
  3. Client-supplied timing cannot extend the persisted deadline.
  4. Resume/refresh does not reset the persisted deadline.
  5. Manual round advancement cannot bypass an expired round.
  6. Candidate isolation + blueprint/round order are preserved.

HTTP-level tests over an in-memory SQLite database (never the live dev
database), mirroring tests/test_mock_drive_security_isolation.py.
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
from app.models.coding import CodingProblem
from app.models.interview import ApprovedQuestionPool, InterviewSession, InterviewTurn
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


def _make_user(db_session, role: str):
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
                cgpa=8.5,
                backlogs_count=0,
                department="Computer Science",
            )
        )
        db_session.commit()
    return user


def _auth(user: User) -> dict:
    token = create_access_token(data={"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


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


def _add_question(db_session, *, correct="B"):
    topic = AptitudeTopic(name=f"Topic {uuid.uuid4().hex[:6]}")
    db_session.add(topic)
    db_session.flush()
    question = AptitudeQuestion(
        question_text="1 + 1 = ?",
        option_a="1",
        option_b="2",
        option_c="3",
        option_d="4",
        correct_option=correct,
        difficulty="easy",
        topic_id=topic.id,
    )
    db_session.add(question)
    db_session.flush()
    db_session.commit()
    return question.id


def _seed_aptitude_context(
    db_session,
    student,
    *,
    drive=None,
    round_delta_seconds=1800,
    session_delta_seconds=10800,
    snapshot=None,
    with_attempt=False,
):
    """Seed a drive/context/session with one active aptitude round.

    ``round_delta_seconds`` is relative to now; negative values create an
    already-expired round while the session stays in progress.
    """
    now = datetime.utcnow()
    if drive is None:
        drive = MockDrive(
            company_name="Time Co",
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
        started_at=now,
        expires_at=now + timedelta(seconds=session_delta_seconds),
    )
    db_session.add(session)
    db_session.flush()
    apt_round = AssessmentRound(
        session_id=session.id,
        round_type="aptitude",
        status="active",
        max_questions=5,
        started_at=now,
        expires_at=now + timedelta(seconds=round_delta_seconds),
    )
    db_session.add(apt_round)
    db_session.flush()

    if with_attempt:
        question_id = _add_question(db_session)
        db_session.add(
            AptitudeAttempt(
                round_id=apt_round.id,
                question_id=question_id,
                attempt_number=1,
                selected_option="B",
                is_correct=True,
                response_time=1.0,
                difficulty="easy",
            )
        )
    db_session.commit()
    return drive, ctx, session, apt_round


# ══════════════════════════════════════════════════════════════════════
# 1. Valid in-time submission is accepted
# ══════════════════════════════════════════════════════════════════════


def test_in_time_submission_is_accepted(client, db_session):
    student = _make_user(db_session, "student")
    _, _, session, apt_round = _seed_aptitude_context(db_session, student)
    question_id = _add_question(db_session)

    resp = client.post(
        "/api/v1/aptitude/submit-answer",
        json={
            "question_id": question_id,
            "selected_option": "B",
            "response_time": 4.0,
        },
        headers=_auth(student),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["correct"] is True

    db_session.expire_all()
    assert (
        db_session.query(AptitudeAttempt)
        .filter(AptitudeAttempt.round_id == apt_round.id)
        .count()
        == 1
    )


# ══════════════════════════════════════════════════════════════════════
# 2. Expired submission / completion is rejected server-side
# ══════════════════════════════════════════════════════════════════════


def test_expired_aptitude_submission_is_rejected(client, db_session):
    student = _make_user(db_session, "student")
    _, _, session, apt_round = _seed_aptitude_context(
        db_session, student, round_delta_seconds=-60
    )
    question_id = _add_question(db_session)

    resp = client.post(
        "/api/v1/aptitude/submit-answer",
        json={
            "question_id": question_id,
            "selected_option": "B",
            "response_time": 1.0,
        },
        headers=_auth(student),
    )
    assert resp.status_code in (404, 410), resp.text

    db_session.expire_all()
    assert db_session.query(AssessmentRound).get(apt_round.id).status == "expired"
    assert (
        db_session.query(AptitudeAttempt)
        .filter(AptitudeAttempt.round_id == apt_round.id)
        .count()
        == 0
    )


def test_expired_interview_completion_is_rejected(client, db_session):
    student = _make_user(db_session, "student")
    now = datetime.utcnow()
    session = AssessmentSession(
        user_id=student.id,
        status="in_progress",
        started_at=now,
        expires_at=now + timedelta(hours=3),
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
    interview_round = AssessmentRound(
        session_id=session.id,
        round_type="interview",
        status="active",
        started_at=now - timedelta(hours=1),
        expires_at=now - timedelta(minutes=1),
    )
    db_session.add(interview_round)
    db_session.commit()
    interview_id = interview.id

    resp = client.post(
        f"/api/v1/interview/session/{interview_id}/complete",
        headers=_auth(student),
    )
    assert resp.status_code == 410, resp.text

    db_session.expire_all()
    # G5: Interview should be marked COMPLETED with TIME_EXPIRED reason
    assert (
        db_session.query(InterviewSession).get(interview_id).status == "COMPLETED"
    )
    assert (
        db_session.query(InterviewSession).get(interview_id).completion_reason
        == "TIME_EXPIRED"
    )
    assert (
        db_session.query(AssessmentRound).get(interview_round.id).status
        == "expired"
    )


# ══════════════════════════════════════════════════════════════════════
# 2b. First-question (/next) terminal + expiry handling
# ══════════════════════════════════════════════════════════════════════


def _seed_interview_context(
    db_session,
    student,
    *,
    round_delta_seconds=None,
    session_delta_seconds=10800,
    interview_status="ACTIVE",
    phase="HR",
    with_pool=True,
):
    """Seed a session + interview (+ optional active round and approved pool).

    ``round_delta_seconds``/``session_delta_seconds`` are relative to now;
    negative values create already-elapsed deadlines.
    """
    now = datetime.utcnow()
    session = AssessmentSession(
        user_id=student.id,
        status="in_progress",
        started_at=now,
        expires_at=now + timedelta(seconds=session_delta_seconds),
    )
    db_session.add(session)
    db_session.flush()

    interview = InterviewSession(
        session_id=session.id,
        phase=phase,
        current_turn=0,
        total_turns=5,
        rl_state={},
        status=interview_status,
    )
    db_session.add(interview)
    db_session.flush()

    interview_round = None
    if round_delta_seconds is not None:
        interview_round = AssessmentRound(
            session_id=session.id,
            round_type="interview",
            status="active",
            started_at=now,
            expires_at=now + timedelta(seconds=round_delta_seconds),
        )
        db_session.add(interview_round)

    if with_pool:
        db_session.add(
            ApprovedQuestionPool(
                session_id=session.id,
                question_pool=[
                    {
                        "id": "q1",
                        "question": "Tell me about yourself.",
                        "phase": phase,
                        "difficulty": "MEDIUM",
                        # Blueprint pools are served verbatim (no LLM call).
                        "blueprint_pool": True,
                    },
                    {
                        "id": "q2",
                        "question": "What are your strengths?",
                        "phase": phase,
                        "difficulty": "MEDIUM",
                        "blueprint_pool": True,
                    },
                ],
                admin_approved=True,
            )
        )

    db_session.commit()
    db_session.refresh(interview)
    if interview_round is not None:
        db_session.refresh(interview_round)
    return session, interview, interview_round


def test_first_question_accepted_for_in_time_interview(client, db_session):
    student = _make_user(db_session, "student")
    _, interview, _ = _seed_interview_context(
        db_session, student, round_delta_seconds=1800
    )
    resp = client.get(
        f"/api/v1/interview/session/{interview.id}/next",
        headers=_auth(student),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["question"]
    assert body["phase"] == "HR"


def test_first_question_rejected_when_session_expired(client, db_session):
    student = _make_user(db_session, "student")
    session, interview, _ = _seed_interview_context(
        db_session, student, round_delta_seconds=1800, session_delta_seconds=-60
    )
    resp = client.get(
        f"/api/v1/interview/session/{interview.id}/next",
        headers=_auth(student),
    )
    assert resp.status_code == 410, resp.text
    db_session.expire_all()
    assert db_session.query(AssessmentSession).get(session.id).status == "expired"


def test_first_question_rejected_when_round_expired(client, db_session):
    student = _make_user(db_session, "student")
    _, interview, interview_round = _seed_interview_context(
        db_session, student, round_delta_seconds=-60
    )
    resp = client.get(
        f"/api/v1/interview/session/{interview.id}/next",
        headers=_auth(student),
    )
    assert resp.status_code == 410, resp.text
    db_session.expire_all()
    assert (
        db_session.query(AssessmentRound).get(interview_round.id).status
        == "expired"
    )


def test_completed_interview_short_circuits_before_expiry(client, db_session):
    # A completed interview is terminal: it reports "already completed" (400)
    # rather than a misleading 410 once its deadlines have also elapsed, and it
    # must not generate a new question or emit expiry side effects.
    student = _make_user(db_session, "student")
    session, interview, interview_round = _seed_interview_context(
        db_session,
        student,
        round_delta_seconds=-60,
        session_delta_seconds=-60,
        interview_status="COMPLETED",
    )
    turn = InterviewTurn(
        interview_id=interview.id,
        turn_number=1,
        question_text="Tell me about yourself.",
        candidate_response="I am a final-year student.",
    )
    db_session.add(turn)
    db_session.commit()
    turn_id = turn.id

    resp = client.get(
        f"/api/v1/interview/session/{interview.id}/next",
        headers=_auth(student),
    )
    assert resp.status_code == 400, resp.text
    assert "already completed" in resp.json()["detail"].lower()

    db_session.expire_all()
    # Terminal completed status must be honoured before expiry mutation runs.
    assert (
        db_session.query(AssessmentRound).get(interview_round.id).status
        == "active"
    )
    assert (
        db_session.query(InterviewSession).get(interview.id).status
        == "COMPLETED"
    )
    # Existing responses/history are preserved.
    assert (
        db_session.query(InterviewTurn).get(turn_id).candidate_response
        == "I am a final-year student."
    )


def test_completed_unexpired_interview_does_not_serve_next_question(
    client, db_session
):
    # Regression: early USER_SUBMITTED completion sets status=COMPLETED without
    # advancing phase, so a completed-but-unexpired interview must still be
    # rejected (phase alone would let it slip through and serve a question).
    student = _make_user(db_session, "student")
    _, interview, _ = _seed_interview_context(
        db_session,
        student,
        round_delta_seconds=1800,
        interview_status="COMPLETED",
        phase="TECHNICAL",
    )
    resp = client.get(
        f"/api/v1/interview/session/{interview.id}/next",
        headers=_auth(student),
    )
    assert resp.status_code == 400, resp.text
    db_session.expire_all()
    refreshed = db_session.query(InterviewSession).get(interview.id)
    assert refreshed.current_turn == 0
    assert not (refreshed.rl_state or {}).get("current_question_text")


# ══════════════════════════════════════════════════════════════════════
# 3. Client-supplied timing cannot extend the deadline
# ══════════════════════════════════════════════════════════════════════


def test_client_response_time_cannot_extend_deadline(client, db_session):
    student = _make_user(db_session, "student")
    _, _, session, apt_round = _seed_aptitude_context(
        db_session, student, round_delta_seconds=1800
    )
    question_id = _add_question(db_session)

    db_session.refresh(apt_round)
    original_round_expiry = apt_round.expires_at
    original_session_expiry = session.expires_at

    resp = client.post(
        "/api/v1/aptitude/submit-answer",
        json={
            "question_id": question_id,
            "selected_option": "B",
            "response_time": 999999.0,
        },
        headers=_auth(student),
    )
    assert resp.status_code == 200, resp.text

    db_session.expire_all()
    refreshed_round = db_session.query(AssessmentRound).get(apt_round.id)
    refreshed_session = db_session.query(AssessmentSession).get(session.id)
    assert refreshed_round.expires_at == original_round_expiry
    assert refreshed_session.expires_at == original_session_expiry

    # A client-supplied "recent" time cannot make an expired round valid again.
    expired_student = _make_user(db_session, "student")
    _, _, _, expired_round = _seed_aptitude_context(
        db_session, expired_student, round_delta_seconds=-300
    )
    expired_question = _add_question(db_session)
    expired_resp = client.post(
        "/api/v1/aptitude/submit-answer",
        json={
            "question_id": expired_question,
            "selected_option": "B",
            "response_time": 0.0,
        },
        headers=_auth(expired_student),
    )
    assert expired_resp.status_code in (404, 410), expired_resp.text
    db_session.expire_all()
    assert db_session.query(AssessmentRound).get(expired_round.id).status == "expired"


# ══════════════════════════════════════════════════════════════════════
# 4. Resume / refresh does not reset the persisted deadline
# ══════════════════════════════════════════════════════════════════════


def test_resume_and_refresh_do_not_reset_deadline(client, db_session):
    student = _make_user(db_session, "student")
    drive, ctx, session, apt_round = _seed_aptitude_context(db_session, student)

    db_session.refresh(session)
    db_session.refresh(apt_round)
    session_started = session.started_at
    session_expiry = session.expires_at
    round_started = apt_round.started_at
    round_expiry = apt_round.expires_at
    round_id = apt_round.id

    headers = _auth(student)

    # Refresh path.
    status = client.get("/api/v1/session/status", headers=headers)
    assert status.status_code == 200, status.text

    # Resume path (start an already in-progress drive).
    resume = client.post(f"/api/v1/mock-drives/{drive.id}/start", headers=headers)
    assert resume.status_code == 200, resume.text

    db_session.expire_all()
    resumed_session = db_session.query(AssessmentSession).get(session.id)
    resumed_round = db_session.query(AssessmentRound).get(round_id)
    assert resumed_session.started_at == session_started
    assert resumed_session.expires_at == session_expiry
    assert resumed_round.started_at == round_started
    assert resumed_round.expires_at == round_expiry
    assert resumed_round.status == "active"


# ══════════════════════════════════════════════════════════════════════
# 5. Manual advancement cannot bypass an expired round
# ══════════════════════════════════════════════════════════════════════


def test_manual_advance_expired_round_advances_to_next(client, db_session):
    """G5: Manual advance on expired round finalizes it and advances to next round."""
    student = _make_user(db_session, "student")
    drive, ctx, session, apt_round = _seed_aptitude_context(
        db_session, student, round_delta_seconds=-120, with_attempt=True
    )
    headers = _auth(student)

    # First advance: expired aptitude round should be finalized and drive advances to coding
    resp = client.post(f"/api/v1/mock-drives/{drive.id}/advance", headers=headers)
    assert resp.status_code == 410, resp.text
    assert "advanced to the next round" in resp.json()["detail"]

    db_session.expire_all()
    assert db_session.query(AssessmentRound).get(apt_round.id).status == "expired"
    # Coding round SHOULD be created (drive advanced)
    assert (
        db_session.query(AssessmentRound)
        .filter(
            AssessmentRound.session_id == session.id,
            AssessmentRound.round_type == "coding",
        )
        .count()
        == 1
    )

    # Second advance: drive should now be completed (no more rounds)
    resp2 = client.post(f"/api/v1/mock-drives/{drive.id}/advance", headers=headers)
    # Second advance completes the drive (coding was the last round)
    assert resp2.status_code == 200, resp2.text
    assert resp2.json()["status"] == "completed"
    assert (
        db_session.query(AssessmentRound)
        .filter(AssessmentRound.session_id == session.id)
        .count()
        == 2
    )


# ══════════════════════════════════════════════════════════════════════
# 6. Candidate isolation + blueprint / round order remain intact
# ══════════════════════════════════════════════════════════════════════


def test_isolation_and_blueprint_preserved(client, db_session):
    student_a = _make_user(db_session, "student")
    student_b = _make_user(db_session, "student")
    snapshot = _approved_aptitude_snapshot()

    now = datetime.utcnow()
    drive = MockDrive(
        company_name="Shared Time Co",
        target_role="Software Engineer",
        status="published",
        minimum_cgpa=0.0,
        maximum_backlogs=100,
        eligible_branches=[],
        selected_rounds={"aptitude": True, "coding": True},
        round_configurations={},
        blueprint_snapshot=snapshot,
        created_by_id=student_a.id,
    )
    db_session.add(drive)
    db_session.flush()

    _, ctx_a, session_a, round_a = _seed_aptitude_context(
        db_session, student_a, drive=drive, snapshot=snapshot, round_delta_seconds=-120
    )
    # Candidate B shares the drive but uses the blueprintless (legacy) path so
    # the in-time submission assertion exercises the non-blueprint bank.
    _, ctx_b, session_b, round_b = _seed_aptitude_context(
        db_session, student_b, drive=drive, round_delta_seconds=1800
    )

    # Candidate A's expired round blocks A's manual advance.
    a_advance = client.post(
        f"/api/v1/mock-drives/{drive.id}/advance", headers=_auth(student_a)
    )
    assert a_advance.status_code == 410, a_advance.text
    db_session.expire_all()
    assert db_session.query(AssessmentRound).get(round_a.id).status == "expired"

    # Candidate B is unaffected: still active and can still submit in time.
    db_session.expire_all()
    assert db_session.query(AssessmentRound).get(round_b.id).status == "active"
    question_id = _add_question(db_session)
    b_submit = client.post(
        "/api/v1/aptitude/submit-answer",
        json={
            "question_id": question_id,
            "selected_option": "B",
            "response_time": 2.0,
        },
        headers=_auth(student_b),
    )
    assert b_submit.status_code == 200, b_submit.text

    # Blueprint snapshot and enabled-round order are preserved, unchanged.
    db_session.expire_all()
    preserved = db_session.query(MockDrive).get(drive.id).blueprint_snapshot
    assert preserved["enabled_rounds"] == ["aptitude", "coding"]
    assert [
        r["round_order"] for r in preserved["blueprint_data"]["rounds"]
    ] == [1, 2]
    assert ctx_a.id != ctx_b.id
    assert session_a.id != session_b.id


# ═══════════════════════════════════════════════════════════════════════
# G5: Timeout finalization and recovery tests
# ══════════════════════════════════════════════════════════════════════

def _seed_mock_drive_with_aptitude_coding(
    db_session,
    tpo_user,
    student,
    *,
    aptitude_round_delta_seconds=1800,
    coding_round_delta_seconds=1800,
    session_delta_seconds=10800,
):
    """Seed a mock drive with aptitude + coding rounds."""
    now = datetime.utcnow()
    drive = MockDrive(
        company_name="Timeout Test Co",
        target_role="Software Engineer",
        status="published",
        minimum_cgpa=0.0,
        maximum_backlogs=100,
        eligible_branches=[],
        selected_rounds={"aptitude": True, "coding": True},
        round_configurations={},
        created_by_id=tpo_user.id,
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
        status="active",
        created_by_id=tpo_user.id,
    )
    db_session.add(ctx)
    db_session.flush()

    session = AssessmentSession(
        user_id=student.id,
        context_id=ctx.id,
        status="in_progress",
        started_at=now,
        expires_at=now + timedelta(seconds=session_delta_seconds),
    )
    db_session.add(session)
    db_session.flush()

    apt_round = AssessmentRound(
        session_id=session.id,
        round_type="aptitude",
        status="active",
        max_questions=5,
        started_at=now,
        expires_at=now + timedelta(seconds=aptitude_round_delta_seconds),
    )
    db_session.add(apt_round)
    db_session.flush()

    # Add a coding round that will be created when aptitude completes
    return drive, ctx, session, apt_round


def _add_aptitude_question(db_session, correct="B"):
    topic = AptitudeTopic(name=f"Topic {uuid.uuid4().hex[:6]}")
    db_session.add(topic)
    db_session.flush()
    question = AptitudeQuestion(
        question_text="1 + 1 = ?",
        option_a="1",
        option_b="2",
        option_c="3",
        option_d="4",
        correct_option=correct,
        difficulty="easy",
        topic_id=topic.id,
    )
    db_session.add(question)
    db_session.flush()
    db_session.commit()
    return question.id


def test_g5_aptitude_timeout_finalizes_and_advances(client, db_session):
    """G5: Aptitude timeout finalizes round with available evidence and advances to coding."""
    tpo_user = _make_user(db_session, "tpo")
    student = _make_user(db_session, "student")
    headers = _auth(student)

    # Seed mock drive with aptitude (expired) + coding
    drive, ctx, session, apt_round = _seed_mock_drive_with_aptitude_coding(
        db_session, tpo_user, student, aptitude_round_delta_seconds=-60
    )
    _add_aptitude_question(db_session)  # Seed one question for the bank

    # The aptitude round is already expired (expires_at was in the past)
    # Trigger timeout by calling next-question
    resp = client.get("/api/v1/aptitude/next-question", headers=headers)
    # Should get 404/410 because round is expired and no more questions
    assert resp.status_code in (404, 410)

    db_session.expire_all()
    # Aptitude round should be expired
    assert db_session.query(AssessmentRound).get(apt_round.id).status == "expired"
    # Coding round should have been created (advanced)
    coding_rounds = db_session.query(AssessmentRound).filter(
        AssessmentRound.session_id == session.id,
        AssessmentRound.round_type == "coding",
    ).all()
    assert len(coding_rounds) >= 1


def test_g5_coding_timeout_finalizes_and_advances(client, db_session):
    """G5: Coding timeout finalizes with available submissions and advances."""
    from app.services.mock_drive_service import try_advance_mock_drive
    student = _make_user(db_session, "student")
    headers = _auth(student)

    # Seed a drive with coding round (expired)
    now = datetime.utcnow()
    drive = MockDrive(
        company_name="Coding Timeout Co",
        target_role="Software Engineer",
        status="published",
        minimum_cgpa=0.0,
        maximum_backlogs=100,
        eligible_branches=[],
        selected_rounds={"coding": True},
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
        status="active",
    )
    db_session.add(ctx)
    db_session.flush()

    session = AssessmentSession(
        user_id=student.id,
        context_id=ctx.id,
        status="in_progress",
        started_at=now,
        expires_at=now + timedelta(hours=3),
    )
    db_session.add(session)
    db_session.flush()

    coding_round = AssessmentRound(
        session_id=session.id,
        round_type="coding",
        status="active",
        started_at=now - timedelta(hours=1),
        expires_at=now - timedelta(minutes=1),
    )
    db_session.add(coding_round)
    db_session.flush()

    # Add a coding problem
    problem = CodingProblem(
        title="Test Problem",
        description="Return sum of array",
        difficulty="easy",
    )
    problem.tags_list = ["Arrays"]
    db_session.add(problem)
    db_session.flush()

    # Assign problem to round
    from app.models.session_problem import SessionProblem
    sp = SessionProblem(round_id=coding_round.id, problem_id=problem.id, assigned_at=datetime.utcnow())
    db_session.add(sp)
    db_session.commit()

    # Submit code (round is expired) - should auto-finalize and advance
    resp = client.post(
        "/api/v1/coding/submit",
        json={
            "problem_id": problem.id,
            "code": "def solve(arr):\n    return sum(arr)",
            "language": "python",
        },
        headers=headers,
    )
    # Should get 400 (expired) but round should be finalized and drive advanced
    assert resp.status_code == 400

    db_session.expire_all()
    # Coding round should be completed (finalized) because drive is finalized when last round expires
    assert db_session.query(AssessmentRound).get(coding_round.id).status == "completed"
    # This was the only round, so the attempt must reach a terminal state.
    assert db_session.query(AssessmentSession).get(session.id).status == "completed"
    assert db_session.query(AssessmentContext).get(ctx.id).status == "completed"
    # No more rounds (this was the only round), so drive should be completed
    # Check by trying to advance
    result = try_advance_mock_drive(db_session, session.id)
    # Should return None because drive is already completed
    assert result is None


def test_g5_interview_timeout_sets_time_expired_and_advances(client, db_session):
    """G5: Interview timeout sets TIME_EXPIRED and advances mock drive."""
    student = _make_user(db_session, "student")
    headers = _auth(student)

    now = datetime.utcnow()
    drive = MockDrive(
        company_name="Interview Timeout Co",
        target_role="Software Engineer",
        status="published",
        minimum_cgpa=0.0,
        maximum_backlogs=100,
        eligible_branches=[],
        selected_rounds={"technical_interview": True},
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
        status="active",
    )
    db_session.add(ctx)
    db_session.flush()

    session = AssessmentSession(
        user_id=student.id,
        context_id=ctx.id,
        status="in_progress",
        started_at=now,
        expires_at=now + timedelta(hours=3),
    )
    db_session.add(session)
    db_session.flush()

    interview = InterviewSession(
        session_id=session.id,
        phase="TECHNICAL",
        current_turn=1,
        total_turns=5,
        rl_state={},
        status="ACTIVE",
    )
    db_session.add(interview)
    db_session.flush()

    interview_round = AssessmentRound(
        session_id=session.id,
        round_type="interview",
        status="active",
        practice_type="technical_interview",
        started_at=now - timedelta(hours=1),
        expires_at=now - timedelta(minutes=1),
    )
    db_session.add(interview_round)
    db_session.flush()

    # Add approved pool
    from app.models.interview import ApprovedQuestionPool
    pool = ApprovedQuestionPool(
        session_id=session.id,
        question_pool=[
            {"id": "q1", "question": "Q1", "phase": "TECHNICAL", "difficulty": "MEDIUM"},
            {"id": "q2", "question": "Q2", "phase": "TECHNICAL", "difficulty": "MEDIUM"},
        ],
        admin_approved=True,
    )
    db_session.add(pool)
    db_session.commit()

    interview_id = interview.id

    # Try to get next question - should trigger timeout
    resp = client.get(
        f"/api/v1/interview/session/{interview_id}/next",
        headers=_auth(student),
    )
    assert resp.status_code == 410

    db_session.expire_all()
    # Interview should be COMPLETED with TIME_EXPIRED
    interview = db_session.query(InterviewSession).get(interview_id)
    assert interview.status == "COMPLETED"
    assert interview.completion_reason == "TIME_EXPIRED"
    assert db_session.query(AssessmentRound).get(interview_round.id).status == "expired"


def test_g5_timeout_idempotent_on_repeated_calls(client, db_session):
    """G5: Repeated timeout handling calls are idempotent."""
    student = _make_user(db_session, "student")
    headers = _auth(student)

    now = datetime.utcnow()
    drive = MockDrive(
        company_name="Idempotent Timeout Co",
        target_role="Software Engineer",
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
        status="active",
    )
    db_session.add(ctx)
    db_session.flush()

    session = AssessmentSession(
        user_id=student.id,
        context_id=ctx.id,
        status="in_progress",
        started_at=now,
        expires_at=now + timedelta(hours=3),
    )
    db_session.add(session)
    db_session.flush()

    apt_round = AssessmentRound(
        session_id=session.id,
        round_type="aptitude",
        status="active",
        max_questions=5,
        started_at=now,
        expires_at=now - timedelta(minutes=1),
    )
    db_session.add(apt_round)
    db_session.commit()

    # First timeout trigger
    from app.services.session_service import _expire_stale_rounds
    _expire_stale_rounds(db_session, session.id)

    db_session.expire_all()
    assert db_session.query(AssessmentRound).get(apt_round.id).status == "expired"

    # Second call should be idempotent (no errors, no duplicate advancement)
    _expire_stale_rounds(db_session, session.id)
    db_session.expire_all()
    assert db_session.query(AssessmentRound).get(apt_round.id).status == "expired"

    # No duplicate rounds created
    rounds = db_session.query(AssessmentRound).filter(
        AssessmentRound.session_id == session.id
    ).all()
    assert len(rounds) == 1


def test_g5_refresh_does_not_reset_deadline(client, db_session):
    """G5: Refresh/reconnect does not reset server deadline."""
    student = _make_user(db_session, "student")
    headers = _auth(student)

    now = datetime.utcnow()
    drive = MockDrive(
        company_name="Refresh Test Co",
        target_role="Software Engineer",
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
        status="active",
    )
    db_session.add(ctx)
    db_session.flush()

    session = AssessmentSession(
        user_id=student.id,
        context_id=ctx.id,
        status="in_progress",
        started_at=now,
        expires_at=now + timedelta(minutes=30),
    )
    db_session.add(session)
    db_session.flush()

    apt_round = AssessmentRound(
        session_id=session.id,
        round_type="aptitude",
        status="active",
        max_questions=5,
        started_at=now,
        expires_at=now + timedelta(minutes=1),  # 1 minute expiry
    )
    db_session.add(apt_round)
    db_session.commit()

    original_round_expiry = apt_round.expires_at
    original_session_expiry = session.expires_at

    # Simulate refresh by calling status endpoint
    resp = client.get("/api/v1/session/status", headers=_auth(student))
    assert resp.status_code == 200

    # Resume path
    resume = client.post(f"/api/v1/mock-drives/{drive.id}/start", headers=headers)
    assert resume.status_code == 200

    db_session.expire_all()
    resumed_round = db_session.query(AssessmentRound).get(apt_round.id)
    assert resumed_round.expires_at == original_round_expiry
    assert resumed_round.status == "active"  # Still active if not expired yet


def test_g5_hr_interview_timeout_advances_and_finalizes(client, db_session):
    """G5: HR interview timeout advances and finalizes the mock drive."""
    student = _make_user(db_session, "student")
    headers = _auth(student)

    now = datetime.utcnow()
    drive = MockDrive(
        company_name="HR Timeout Co",
        target_role="Software Engineer",
        status="published",
        minimum_cgpa=0.0,
        maximum_backlogs=100,
        eligible_branches=[],
        selected_rounds={"technical_interview": True, "hr_interview": True},
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
        status="active",
    )
    db_session.add(ctx)
    db_session.flush()

    session = AssessmentSession(
        user_id=student.id,
        context_id=ctx.id,
        status="in_progress",
        started_at=now,
        expires_at=now + timedelta(hours=3),
    )
    db_session.add(session)
    db_session.flush()

    # Technical interview round (completed)
    tech_round = AssessmentRound(
        session_id=session.id,
        round_type="interview",
        practice_type="technical_interview",
        status="completed",
        started_at=now - timedelta(hours=2),
        completed_at=now - timedelta(hours=1),
    )
    db_session.add(tech_round)
    db_session.flush()

    # HR interview round (expired)
    hr_round = AssessmentRound(
        session_id=session.id,
        round_type="interview",
        practice_type="hr_interview",
        status="active",
        started_at=now - timedelta(hours=1),
        expires_at=now - timedelta(minutes=1),
    )
    db_session.add(hr_round)
    db_session.flush()

    interview = InterviewSession(
        session_id=session.id,
        phase="HR",
        current_turn=1,
        total_turns=3,
        rl_state={},
        status="ACTIVE",
    )
    db_session.add(interview)
    db_session.flush()

    # Add approved pool for HR
    from app.models.interview import ApprovedQuestionPool
    pool = ApprovedQuestionPool(
        session_id=session.id,
        question_pool=[
            {"id": "q1", "question": "HR Q1", "phase": "HR", "difficulty": "MEDIUM"},
        ],
        admin_approved=True,
    )
    db_session.add(pool)
    db_session.commit()

    interview_id = interview.id

    # Try to complete HR interview - should timeout
    resp = client.post(
        f"/api/v1/interview/session/{interview_id}/complete",
        headers=_auth(student),
    )
    assert resp.status_code == 410

    db_session.expire_all()
    # HR interview should be COMPLETED with TIME_EXPIRED
    interview = db_session.query(InterviewSession).get(interview_id)
    assert interview.status == "COMPLETED"
    assert interview.completion_reason == "TIME_EXPIRED"
    assert db_session.query(AssessmentRound).get(hr_round.id).status == "expired"

    # Technical interview round should also be marked completed (already was)
    assert db_session.query(AssessmentRound).get(tech_round.id).status == "completed"


def _seed_hr_last_round_drive(db_session, student):
    """Seed a drive whose final round is an expired HR interview.

    Enabled rounds: technical_interview (already completed) then hr_interview
    (active but overdue). Returns (drive, ctx, session, tech_round, hr_round,
    interview).
    """
    now = datetime.utcnow()
    drive = MockDrive(
        company_name="HR Finalize Co",
        target_role="Software Engineer",
        status="published",
        minimum_cgpa=0.0,
        maximum_backlogs=100,
        eligible_branches=[],
        selected_rounds={"technical_interview": True, "hr_interview": True},
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
        status="active",
    )
    db_session.add(ctx)
    db_session.flush()

    session = AssessmentSession(
        user_id=student.id,
        context_id=ctx.id,
        status="in_progress",
        started_at=now,
        expires_at=now + timedelta(hours=3),
    )
    db_session.add(session)
    db_session.flush()

    tech_round = AssessmentRound(
        session_id=session.id,
        round_type="interview",
        practice_type="technical_interview",
        status="completed",
        started_at=now - timedelta(hours=2),
        completed_at=now - timedelta(hours=1),
    )
    db_session.add(tech_round)
    db_session.flush()

    hr_round = AssessmentRound(
        session_id=session.id,
        round_type="interview",
        practice_type="hr_interview",
        status="active",
        started_at=now - timedelta(hours=1),
        expires_at=now - timedelta(minutes=1),
    )
    db_session.add(hr_round)
    db_session.flush()

    interview = InterviewSession(
        session_id=session.id,
        phase="HR",
        current_turn=1,
        total_turns=3,
        rl_state={},
        status="ACTIVE",
    )
    db_session.add(interview)
    db_session.flush()

    pool = ApprovedQuestionPool(
        session_id=session.id,
        question_pool=[
            {"id": "q1", "question": "HR Q1", "phase": "HR", "difficulty": "MEDIUM"},
        ],
        admin_approved=True,
    )
    db_session.add(pool)
    db_session.commit()
    return drive, ctx, session, tech_round, hr_round, interview


def test_g5_hr_interview_timeout_finalizes_drive_when_no_rounds_remain(
    client, db_session
):
    """G5: Expiring the final HR round must finalize the mock drive.

    The round becomes TIME_EXPIRED, no further round is created, and the
    session/context are marked completed because no rounds remain.
    """
    student = _make_user(db_session, "student")
    drive, ctx, session, tech_round, hr_round, interview = _seed_hr_last_round_drive(
        db_session, student
    )
    interview_id = interview.id
    round_count_before = (
        db_session.query(AssessmentRound)
        .filter(AssessmentRound.session_id == session.id)
        .count()
    )

    resp = client.post(
        f"/api/v1/interview/session/{interview_id}/complete",
        headers=_auth(student),
    )
    assert resp.status_code == 410

    db_session.expire_all()
    # Round + interview timed out.
    assert db_session.query(AssessmentRound).get(hr_round.id).status == "expired"
    interview = db_session.query(InterviewSession).get(interview_id)
    assert interview.status == "COMPLETED"
    assert interview.completion_reason == "TIME_EXPIRED"
    # No new round was created.
    assert (
        db_session.query(AssessmentRound)
        .filter(AssessmentRound.session_id == session.id)
        .count()
        == round_count_before
    )
    # Drive finalized: session + context completed.
    session = db_session.query(AssessmentSession).get(session.id)
    ctx = db_session.query(AssessmentContext).get(ctx.id)
    assert session.status == "completed"
    assert ctx.status == "completed"


def test_g5_hr_interview_timeout_is_idempotent(client, db_session):
    """G5: Repeated HR timeout handling must not duplicate advancement/finalization."""
    student = _make_user(db_session, "student")
    _, ctx, session, _, hr_round, interview = _seed_hr_last_round_drive(
        db_session, student
    )
    interview_id = interview.id

    # First timeout.
    first = client.post(
        f"/api/v1/interview/session/{interview_id}/complete",
        headers=_auth(student),
    )
    assert first.status_code == 410

    db_session.expire_all()
    session = db_session.query(AssessmentSession).get(session.id)
    rounds_after_first = (
        db_session.query(AssessmentRound)
        .filter(AssessmentRound.session_id == session.id)
        .count()
    )
    session_completed_at = session.completed_at

    # Second + third timeout triggers must be no-ops: the completed interview
    # short-circuits (200) and never re-finalizes. Round count and completion
    # timestamp must be unchanged.
    for _ in range(2):
        again = client.post(
            f"/api/v1/interview/session/{interview_id}/complete",
            headers=_auth(student),
        )
        assert again.status_code in (200, 410, 404)

    db_session.expire_all()
    session = db_session.query(AssessmentSession).get(session.id)
    rounds_after = (
        db_session.query(AssessmentRound)
        .filter(AssessmentRound.session_id == session.id)
        .count()
    )
    assert rounds_after == rounds_after_first
    assert session.completed_at == session_completed_at
    assert session.status == "completed"
    assert (
        db_session.query(AssessmentRound)
        .filter(AssessmentRound.session_id == session.id, AssessmentRound.status == "active")
        .count()
        == 0
    )


def _seed_technical_interview(
    db_session, student, *, session_delta_seconds, round_delta_seconds
):
    """Seed a mock drive with one active technical interview round.

    Deadlines are relative to now; negative values mean already overdue.
    Returns (drive, ctx, session, round, interview).
    """
    now = datetime.utcnow()
    drive = MockDrive(
        company_name="Session Expiry Co",
        target_role="Software Engineer",
        status="published",
        minimum_cgpa=0.0,
        maximum_backlogs=100,
        eligible_branches=[],
        selected_rounds={"technical_interview": True},
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
        status="active",
    )
    db_session.add(ctx)
    db_session.flush()

    session = AssessmentSession(
        user_id=student.id,
        context_id=ctx.id,
        status="in_progress",
        started_at=now,
        expires_at=now + timedelta(seconds=session_delta_seconds),
    )
    db_session.add(session)
    db_session.flush()

    round_obj = AssessmentRound(
        session_id=session.id,
        round_type="interview",
        practice_type="technical_interview",
        status="active",
        started_at=now - timedelta(hours=1),
        expires_at=now + timedelta(seconds=round_delta_seconds),
    )
    db_session.add(round_obj)
    db_session.flush()

    interview = InterviewSession(
        session_id=session.id,
        phase="TECHNICAL",
        current_turn=1,
        total_turns=3,
        rl_state={},
        status="ACTIVE",
    )
    db_session.add(interview)
    db_session.flush()

    pool = ApprovedQuestionPool(
        session_id=session.id,
        question_pool=[
            {"id": "q1", "question": "TECH Q1", "phase": "TECHNICAL", "difficulty": "MEDIUM"},
        ],
        admin_approved=True,
    )
    db_session.add(pool)
    db_session.commit()
    return drive, ctx, session, round_obj, interview


def test_g5_session_expiry_terminates_interview_attempt(client, db_session):
    """G5: An expired *session* deadline must terminate the interview attempt.

    The round deadline is still in the future, so only the session deadline is
    authoritative here. The candidate must be blocked and the active round must
    be closed (mirroring _expire_stale_session); repeated attempts stay
    idempotent and create no new rounds.
    """
    student = _make_user(db_session, "student")
    drive, ctx, session, round_obj, interview = _seed_technical_interview(
        db_session,
        student,
        session_delta_seconds=-60,
        round_delta_seconds=3600,
    )
    interview_id = interview.id

    resp = client.get(
        f"/api/v1/interview/session/{interview_id}/next",
        headers=_auth(student),
    )
    assert resp.status_code == 410

    db_session.expire_all()
    session = db_session.query(AssessmentSession).get(session.id)
    round_obj = db_session.query(AssessmentRound).get(round_obj.id)
    rounds_after_first = (
        db_session.query(AssessmentRound)
        .filter(AssessmentRound.session_id == session.id)
        .count()
    )
    # No work may remain active once the session deadline passed.
    assert (
        db_session.query(AssessmentRound)
        .filter(AssessmentRound.session_id == session.id, AssessmentRound.status == "active")
        .count()
        == 0
    )
    assert round_obj.status == "expired"
    assert session.status == "expired"

    # Repeated triggers stay idempotent: no duplicate rounds/advancement.
    for _ in range(2):
        again = client.get(
            f"/api/v1/interview/session/{interview_id}/next",
            headers=_auth(student),
        )
        assert again.status_code in (400, 410, 404)

    db_session.expire_all()
    assert (
        db_session.query(AssessmentRound)
        .filter(AssessmentRound.session_id == session.id)
        .count()
        == rounds_after_first
    )
