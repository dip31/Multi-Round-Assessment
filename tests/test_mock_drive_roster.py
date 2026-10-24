"""Tests for the derived Mock Drive candidate roster + TPO result access (G4).

The roster is derived from authoritative AssessmentContext/Session/Round
records. These tests assert:

  * participants + counts come from persisted contexts, not duplicate state;
  * per-round status/score reflects the persisted round;
  * the roster is scoped to its own drive (cross-drive isolation);
  * RBAC: students and unauthenticated callers are rejected;
  * staff can read one candidate's consolidated result, and non-participants
    return 404.

HTTP-level, in-memory SQLite (never the live dev database), mirroring
tests/test_mock_drive_security_isolation.py.
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
from app.models.profile import StudentProfile, FacultyProfile, TPOProfile
from app.models.mock_drive import MockDrive
from app.models.assessment_context import AssessmentPolicy, AssessmentContext
from app.models.assessment import AssessmentSession, AssessmentRound
from app.models.aptitude import AptitudeAttempt, AptitudeQuestion
from app.models.coding import CodingProblem, CodingSubmission
from app.models.interview import InterviewSession, InterviewTurn
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
            StudentProfile(user_id=user.id, cgpa=cgpa, backlogs_count=0)
        )
        db_session.commit()
    return user


def _auth(user: User) -> dict:
    token = create_access_token(data={"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


def _published_coding_drive(client, tpo_headers, *, name="Roster Co"):
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


def _entry(roster: dict, candidate_id: int) -> dict:
    matches = [c for c in roster["candidates"] if c["candidate_id"] == candidate_id]
    assert matches, f"candidate {candidate_id} not present in roster"
    return matches[0]


# ══════════════════════════════════════════════════════════════════════
# Derivation + counts
# ══════════════════════════════════════════════════════════════════════


def test_roster_derives_participants_and_counts_from_contexts(client, db_session):
    tpo = _make_user(db_session, "tpo")
    student_a = _make_user(db_session, "student")
    student_b = _make_user(db_session, "student")
    tpo_headers = _auth(tpo)

    drive_id = _published_coding_drive(client, tpo_headers)

    # A starts but does not finish; B starts and completes the single round.
    assert (
        client.post(
            f"/api/v1/mock-drives/{drive_id}/start", headers=_auth(student_a)
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/mock-drives/{drive_id}/start", headers=_auth(student_b)
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/mock-drives/{drive_id}/advance", headers=_auth(student_b)
        ).status_code
        == 200
    )

    roster = client.get(
        f"/api/v1/tpo/mock-drives/{drive_id}/roster", headers=tpo_headers
    )
    assert roster.status_code == 200, roster.text
    body = roster.json()

    assert body["mock_drive_id"] == drive_id
    assert body["enabled_rounds"] == ["coding"]
    assert body["total_participants"] == 2
    assert body["in_progress_count"] == 1
    assert body["completed_count"] == 1

    a = _entry(body, student_a.id)
    assert a["context_status"] == "active"
    assert a["name"] == student_a.name
    assert a["email"] == student_a.email
    assert a["rounds"][0]["round"] == "coding"
    assert a["rounds"][0]["status"] == "active"

    b = _entry(body, student_b.id)
    assert b["context_status"] == "completed"
    assert b["rounds"][0]["status"] == "completed"
    # Completing the round lifecycle without an evaluated coding submission is
    # not a numeric result and must not be presented as a score.
    assert b["rounds"][0]["score"] is None
    assert b["rounds"][0]["max_score"] is None
    assert b["overall_score"] is None


def test_roster_shows_configured_round_as_not_started_when_no_round_record_exists(
    client, db_session
):
    tpo = _make_user(db_session, "tpo")
    student = _make_user(db_session, "student")
    drive_id = _published_coding_drive(client, _auth(tpo), name="No Round Record Co")
    drive = db_session.get(MockDrive, drive_id)
    context = AssessmentContext(
        mode="mock_drive", purpose="mock_drive", student_id=student.id,
        company_name=drive.company_name, target_role=drive.target_role,
        policy_id=DEFAULT_PRACTICE_POLICY_ID, mock_drive_id=drive_id,
        blueprint_snapshot={}, status="active",
    )
    db_session.add(context)
    db_session.flush()
    db_session.add(AssessmentSession(
        user_id=student.id, context_id=context.id, status="in_progress",
        started_at=datetime.utcnow(),
    ))
    db_session.commit()

    response = client.get(
        f"/api/v1/tpo/mock-drives/{drive_id}/roster", headers=_auth(tpo)
    )
    assert response.status_code == 200, response.text
    entry = _entry(response.json(), student.id)
    assert entry["rounds"] == [{
        "round": "coding", "round_type": "coding", "status": "not_started",
        "deadline_passed": False, "score": None, "max_score": None,
        "completed_at": None,
    }]


def test_roster_uses_evaluated_round_score_and_competency_aggregate(
    client, db_session, monkeypatch
):
    import app.services.mock_drive_service as mock_drive_service

    tpo = _make_user(db_session, "tpo")
    student = _make_user(db_session, "student")
    drive_id = _published_coding_drive(client, _auth(tpo), name="Scored Roster Co")
    drive = db_session.query(MockDrive).get(drive_id)
    context = AssessmentContext(
        mode="mock_drive", purpose="mock_drive", student_id=student.id,
        company_name=drive.company_name, target_role=drive.target_role,
        policy_id=DEFAULT_PRACTICE_POLICY_ID, mock_drive_id=drive_id,
        blueprint_snapshot={}, status="completed",
    )
    db_session.add(context)
    db_session.flush()
    session = AssessmentSession(
        user_id=student.id, context_id=context.id, status="completed",
        total_score=25.0, started_at=datetime.utcnow(), completed_at=datetime.utcnow(),
    )
    db_session.add(session)
    db_session.flush()
    round_item = AssessmentRound(
        session_id=session.id, round_type="coding", practice_type="coding",
        status="completed", score=0.0, max_questions=10,
    )
    problem = CodingProblem(title="Roster score", description="Score evidence test")
    db_session.add_all([round_item, problem])
    db_session.flush()
    db_session.add(CodingSubmission(
        round_id=round_item.id, problem_id=problem.id, code="pass", status="accepted", score=0.0,
    ))
    db_session.commit()

    monkeypatch.setattr(mock_drive_service, "score_session_competencies", lambda _db, _session: {
        "overall_score_status": "final", "overall_score": 72.5,
        "competencies": [], "missing_competencies": [],
    })
    response = client.get(
        f"/api/v1/tpo/mock-drives/{drive_id}/roster", headers=_auth(tpo)
    )
    assert response.status_code == 200, response.text
    entry = _entry(response.json(), student.id)
    assert entry["overall_score"] == 72.5
    assert entry["rounds"][0]["score"] == 0.0
    assert entry["rounds"][0]["max_score"] == 1.0


def test_roster_exposes_expired_rounds_and_mapping_status(client, db_session):
    tpo = _make_user(db_session, "tpo")
    student = _make_user(db_session, "student")
    tpo_headers = _auth(tpo)
    drive_id = _published_coding_drive(client, tpo_headers, name="Expired Co")

    drive = db_session.query(MockDrive).get(drive_id)
    ctx = AssessmentContext(
        mode="mock_drive",
        purpose="mock_drive",
        student_id=student.id,
        company_name=drive.company_name,
        target_role=drive.target_role,
        policy_id=DEFAULT_PRACTICE_POLICY_ID,
        mock_drive_id=drive_id,
        blueprint_snapshot={},
        status="active",
        competency_mapping_status="pending",
    )
    db_session.add(ctx)
    db_session.flush()
    session = AssessmentSession(
        user_id=student.id,
        context_id=ctx.id,
        status="in_progress",
        started_at=datetime.utcnow(),
    )
    db_session.add(session)
    db_session.flush()
    db_session.add(
        AssessmentRound(
            session_id=session.id,
            round_type="coding",
            practice_type="coding",
            status="expired",
            score=0.0,
            completed_at=datetime.utcnow(),
        )
    )
    db_session.commit()

    roster = client.get(
        f"/api/v1/tpo/mock-drives/{drive_id}/roster", headers=tpo_headers
    ).json()

    entry = _entry(roster, student.id)
    assert entry["competency_mapping_status"] == "pending"
    assert entry["rounds"][0]["status"] == "expired"
    assert entry["rounds"][0]["deadline_passed"] is True
    # An expired coding round with no evaluated submission has no score scale/result.
    assert entry["rounds"][0]["score"] is None
    assert entry["rounds"][0]["max_score"] is None


def test_roster_marks_active_round_past_deadline(client, db_session):
    tpo = _make_user(db_session, "tpo")
    student = _make_user(db_session, "student")
    drive_id = _published_coding_drive(client, _auth(tpo), name="Overdue Co")
    drive = db_session.query(MockDrive).get(drive_id)
    context = AssessmentContext(
        mode="mock_drive",
        purpose="mock_drive",
        student_id=student.id,
        company_name=drive.company_name,
        target_role=drive.target_role,
        policy_id=DEFAULT_PRACTICE_POLICY_ID,
        mock_drive_id=drive_id,
        blueprint_snapshot={},
        status="active",
    )
    db_session.add(context)
    db_session.flush()
    session = AssessmentSession(
        user_id=student.id,
        context_id=context.id,
        status="in_progress",
        started_at=datetime.utcnow(),
    )
    db_session.add(session)
    db_session.flush()
    db_session.add(AssessmentRound(
        session_id=session.id,
        round_type="coding",
        practice_type="coding",
        status="active",
        expires_at=datetime.utcnow() - timedelta(seconds=1),
    ))
    db_session.commit()

    roster = client.get(
        f"/api/v1/tpo/mock-drives/{drive_id}/roster", headers=_auth(tpo)
    ).json()
    round_data = _entry(roster, student.id)["rounds"][0]
    assert round_data["status"] == "active"
    assert round_data["deadline_passed"] is True


def test_cohort_students_expose_current_session_time_remaining(client, db_session):
    tpo = _make_user(db_session, "tpo")
    student = _make_user(db_session, "student")
    session = AssessmentSession(
        user_id=student.id,
        status="in_progress",
        started_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(minutes=1),
    )
    db_session.add(session)
    db_session.commit()

    response = client.get("/api/v1/profile/cohort/students", headers=_auth(tpo))
    assert response.status_code == 200
    student_data = next(row for row in response.json()["students"] if row["user_id"] == student.id)
    assert student_data["session_status"] == "in_progress"
    assert student_data["session_time_remaining_seconds"] > 0

    session.expires_at = datetime.utcnow() - timedelta(seconds=1)
    db_session.commit()
    response = client.get("/api/v1/profile/cohort/students", headers=_auth(tpo))
    student_data = next(row for row in response.json()["students"] if row["user_id"] == student.id)
    assert student_data["session_time_remaining_seconds"] == 0


def test_faculty_cohort_scope_comes_from_profile_and_omits_unassigned_students(
    client, db_session
):
    faculty = _make_user(db_session, "faculty")
    db_session.add(FacultyProfile(user_id=faculty.id, department="Computer Science"))
    in_scope = _make_user(db_session, "student")
    db_session.query(StudentProfile).filter_by(user_id=in_scope.id).one().department = "Computer Science"
    out_of_scope = _make_user(db_session, "student")
    db_session.query(StudentProfile).filter_by(user_id=out_of_scope.id).one().department = "Mathematics"
    unassigned = _make_user(db_session, "student")
    db_session.query(StudentProfile).filter_by(user_id=unassigned.id).delete()
    db_session.commit()

    default_scope = client.get(
        "/api/v1/profile/cohort/students", headers=_auth(faculty)
    )
    assert default_scope.status_code == 200, default_scope.text
    visible_ids = {student["user_id"] for student in default_scope.json()["students"]}
    assert in_scope.id in visible_ids
    assert out_of_scope.id not in visible_ids
    assert unassigned.id not in visible_ids
    visible_student = next(student for student in default_scope.json()["students"] if student["user_id"] == in_scope.id)
    assert "email" not in visible_student
    assert "mobile_no" not in visible_student
    assert "date_of_birth" not in visible_student

    attempted_override = client.get(
        "/api/v1/profile/cohort/students?department=Mathematics",
        headers=_auth(faculty),
    )
    assert attempted_override.status_code == 403


def test_department_distribution_is_aggregate_only_and_scoped_by_role_and_institution(
    client, db_session
):
    tpo = _make_user(db_session, "tpo")
    db_session.add(TPOProfile(user_id=tpo.id, institution="Engineering College"))
    in_scope_cs = _make_user(db_session, "student")
    in_scope_it = _make_user(db_session, "student")
    other_institution = _make_user(db_session, "student")
    db_session.query(StudentProfile).filter_by(user_id=in_scope_cs.id).one().department = "Computer Science"
    db_session.query(StudentProfile).filter_by(user_id=in_scope_it.id).one().department = "Information Technology"
    db_session.query(StudentProfile).filter_by(user_id=in_scope_it.id).one().institution = "Engineering College"
    db_session.query(StudentProfile).filter_by(user_id=other_institution.id).one().department = "Mechanical Engineering"
    db_session.query(StudentProfile).filter_by(user_id=other_institution.id).one().institution = "Other College"
    db_session.commit()

    response = client.get(
        "/api/v1/profile/cohort/department-distribution", headers=_auth(tpo)
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["scope"] == "institution"
    assert body["institution"] == "Engineering College"
    assert body["total_students"] == 2
    assert body["departments"] == [
        {"department": "Computer Science", "count": 1},
        {"department": "Information Technology", "count": 1},
    ]
    assert "students" not in body
    assert "email" not in str(body)

    faculty = _make_user(db_session, "faculty")
    db_session.add(FacultyProfile(user_id=faculty.id, department="Computer Science"))
    db_session.commit()
    denied = client.get(
        "/api/v1/profile/cohort/department-distribution", headers=_auth(faculty)
    )
    assert denied.status_code == 403


def test_admin_department_distribution_includes_unprofiled_students_as_unspecified(
    client, db_session
):
    admin = _make_user(db_session, "admin")
    cs_student = _make_user(db_session, "student")
    it_student = _make_user(db_session, "student")
    no_profile_student = _make_user(db_session, "student")
    db_session.query(StudentProfile).filter_by(user_id=it_student.id).one().department = "Information Technology"
    db_session.query(StudentProfile).filter_by(user_id=cs_student.id).one().department = "Computer Science"
    db_session.query(StudentProfile).filter_by(user_id=no_profile_student.id).delete()
    db_session.commit()

    response = client.get(
        "/api/v1/profile/cohort/department-distribution", headers=_auth(admin)
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["scope"] == "all_institutions"
    assert body["total_students"] == 3
    assert {row["department"]: row["count"] for row in body["departments"]} == {
        "Computer Science": 1,
        "Information Technology": 1,
        "Department Not Specified": 1,
    }


def test_faculty_cannot_change_own_department_scope(client, db_session):
    faculty = _make_user(db_session, "faculty")
    profile = FacultyProfile(user_id=faculty.id, department="Computer Science")
    db_session.add(profile)
    db_session.commit()

    response = client.put(
        "/api/v1/profile/faculty/me",
        headers=_auth(faculty),
        json={"department": "Mathematics"},
    )

    db_session.refresh(profile)
    assert response.status_code == 403
    assert profile.department == "Computer Science"


def test_cohort_response_keeps_zero_and_null_scores_distinct(client, db_session):
    tpo = _make_user(db_session, "tpo")
    scored_student = _make_user(db_session, "student")
    unscored_student = _make_user(db_session, "student")
    session = AssessmentSession(
        user_id=scored_student.id,
        status="completed",
        total_score=0.0,
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
    )
    db_session.add(session)
    db_session.flush()
    db_session.add(AssessmentRound(
        session_id=session.id,
        round_type="aptitude",
        status="completed",
        score=88.0,
        max_questions=1,
    ))
    db_session.commit()

    response = client.get("/api/v1/profile/cohort/students", headers=_auth(tpo))
    assert response.status_code == 200, response.text
    by_id = {student["user_id"]: student for student in response.json()["students"]}
    assert by_id[scored_student.id]["overall_score"] == 0.0
    assert by_id[unscored_student.id]["overall_score"] is None
    # A completed round counts as assessed even when its score is unavailable.
    assert response.json()["summary"]["assessed_students"] == 1
    assert response.json()["summary"]["average_score"] is None
    assert response.json()["summary"]["average_score_status"] == "unavailable"


def test_global_report_scope_is_limited_to_tpo_and_admin(client, db_session):
    faculty = _make_user(db_session, "faculty")
    tpo = _make_user(db_session, "tpo")
    admin = _make_user(db_session, "admin")
    db_session.add(FacultyProfile(user_id=faculty.id, department="Computer Science"))
    db_session.commit()

    path = "/api/v1/report/admin/cohort-stats"
    assert client.get(path, headers=_auth(faculty)).status_code == 403
    assert client.get(path, headers=_auth(tpo)).status_code == 200
    assert client.get(path, headers=_auth(admin)).status_code == 200


def test_faculty_round_scores_require_evaluation_evidence_and_preserve_zero(client, db_session):
    faculty = _make_user(db_session, "faculty")
    db_session.add(FacultyProfile(user_id=faculty.id, department="Computer Science"))
    zero_student = _make_user(db_session, "student")
    no_result_student = _make_user(db_session, "student")
    partial_student = _make_user(db_session, "student")
    zero_session = AssessmentSession(
        user_id=zero_student.id,
        status="completed",
        total_score=0.0,
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
    )
    no_result_session = AssessmentSession(
        user_id=no_result_student.id,
        status="completed",
        total_score=0.0,
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
    )
    partial_session = AssessmentSession(
        user_id=partial_student.id,
        status="completed",
        total_score=0.0,
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
    )
    db_session.add_all([zero_session, no_result_session, partial_session])
    db_session.flush()
    zero_round = AssessmentRound(
        session_id=zero_session.id,
        round_type="aptitude",
        status="completed",
        score=88.0,
        max_questions=1,
    )
    no_result_round = AssessmentRound(
        session_id=no_result_session.id,
        round_type="aptitude",
        status="completed",
        score=0.0,
        max_questions=1,
    )
    partial_round = AssessmentRound(
        session_id=partial_session.id,
        round_type="aptitude",
        status="completed",
        score=50.0,
        max_questions=2,
    )
    db_session.add_all([zero_round, no_result_round, partial_round])
    db_session.flush()
    question = AptitudeQuestion(
        question_text="Preview test question?",
        option_a="A",
        option_b="B",
        option_c="C",
        option_d="D",
        correct_option="A",
        difficulty="easy",
    )
    db_session.add(question)
    db_session.flush()
    db_session.add(AptitudeAttempt(
        round_id=zero_round.id,
        question_id=question.id,
        attempt_number=1,
        selected_option="B",
        is_correct=False,
    ))
    db_session.add_all([
        AptitudeAttempt(round_id=partial_round.id, question_id=question.id, attempt_number=1, selected_option="B", is_correct=False),
        AptitudeAttempt(round_id=partial_round.id, question_id=question.id, attempt_number=1, selected_option="A", is_correct=None),
    ])
    db_session.commit()

    response = client.get("/api/v1/profile/cohort/students", headers=_auth(faculty))
    assert response.status_code == 200, response.text
    by_id = {student["user_id"]: student for student in response.json()["students"]}
    assert by_id[zero_student.id]["rounds"]["aptitude"]["score"] == 0.0
    assert by_id[no_result_student.id]["rounds"]["aptitude"]["score"] is None
    assert by_id[zero_student.id]["round_records"][0]["score_max"] == 100
    assert by_id[zero_student.id]["round_records"][0]["evaluation_evidence"] == {"evaluated": 1, "total": 1, "correct": 0}
    assert by_id[partial_student.id]["rounds"]["aptitude"]["score"] is None
    assert "email" not in by_id[zero_student.id]
    # Completion is a lifecycle metric and includes completed rounds regardless
    # of whether the round contains complete evaluation evidence.
    assert response.json()["summary"]["assessed_students"] == 3


def test_faculty_assessed_summary_uses_latest_timestamp_and_completed_round_definition(
    client, db_session
):
    faculty = _make_user(db_session, "faculty")
    db_session.add(FacultyProfile(user_id=faculty.id, department="Computer Science"))
    student = _make_user(db_session, "student")
    db_session.query(StudentProfile).filter_by(user_id=student.id).one().department = "Computer Science"

    now = datetime.utcnow()
    latest_completed = AssessmentSession(
        user_id=student.id,
        status="completed",
        started_at=now + timedelta(minutes=1),
        completed_at=now + timedelta(minutes=2),
    )
    db_session.add(latest_completed)
    db_session.flush()
    db_session.add(AssessmentRound(
        session_id=latest_completed.id,
        round_type="aptitude",
        status="completed",
        score=0.0,
        max_questions=1,
    ))
    # A newer database ID with an older persisted start time must not replace
    # the actual latest session used in the roster or summary.
    db_session.add(AssessmentSession(
        user_id=student.id,
        status="in_progress",
        started_at=now - timedelta(minutes=1),
    ))
    db_session.commit()

    response = client.get("/api/v1/profile/cohort/students", headers=_auth(faculty))
    assert response.status_code == 200, response.text
    roster_student = next(row for row in response.json()["students"] if row["user_id"] == student.id)
    assert roster_student["session_status"] == "completed"
    assert response.json()["summary"]["authorized_students"] == 1
    assert response.json()["summary"]["assessed_students"] == 1
    assert response.json()["summary"]["latest_attempt_completion_rate"] == 100.0


def test_faculty_interview_score_uses_persisted_scored_turns_not_default_round_zero(
    client, db_session
):
    faculty = _make_user(db_session, "faculty")
    db_session.add(FacultyProfile(user_id=faculty.id, department="Computer Science"))
    student = _make_user(db_session, "student")
    db_session.query(StudentProfile).filter_by(user_id=student.id).one().department = "Computer Science"
    session = AssessmentSession(
        user_id=student.id,
        status="completed",
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
    )
    db_session.add(session)
    db_session.flush()
    round_item = AssessmentRound(
        session_id=session.id,
        round_type="interview",
        status="completed",
        score=0.0,
        max_questions=1,
    )
    interview = InterviewSession(session_id=session.id, status="COMPLETED")
    db_session.add_all([round_item, interview])
    db_session.flush()
    db_session.add(InterviewTurn(
        interview_id=interview.id,
        turn_number=1,
        question_text="Describe a technical challenge.",
        candidate_response="I investigated the failure and fixed it.",
        final_score=0.8,
        is_followup=False,
    ))
    db_session.commit()

    response = client.get("/api/v1/profile/cohort/students", headers=_auth(faculty))
    assert response.status_code == 200, response.text
    roster_student = next(row for row in response.json()["students"] if row["user_id"] == student.id)
    assert roster_student["rounds"]["interview"]["score"] == pytest.approx(0.8)
    assert roster_student["round_records"][0]["score"] == pytest.approx(0.8)


def test_faculty_roster_search_status_and_pagination_are_server_scoped(client, db_session):
    faculty = _make_user(db_session, "faculty")
    db_session.add(FacultyProfile(user_id=faculty.id, department="Computer Science"))
    first = _make_user(db_session, "student")
    first.name = "Avery Student"
    second = _make_user(db_session, "student")
    second.name = "Zoe Student"
    db_session.commit()

    path = "/api/v1/profile/cohort/students"
    headers = _auth(faculty)
    page_one = client.get(f"{path}?page=1&page_size=1", headers=headers)
    page_two = client.get(f"{path}?page=2&page_size=1", headers=headers)
    assert page_one.status_code == page_two.status_code == 200
    assert page_one.json()["total"] == 2
    assert page_one.json()["pages"] == 2
    assert page_one.json()["students"][0]["user_id"] != page_two.json()["students"][0]["user_id"]

    searched = client.get(f"{path}?search=Zoe&page=1&page_size=20", headers=headers)
    assert searched.status_code == 200
    assert [student["name"] for student in searched.json()["students"]] == ["Zoe Student"]
    assert searched.json()["summary"]["authorized_students"] == 2

    not_started = client.get(f"{path}?status=not_started&page=1&page_size=20", headers=headers)
    completed = client.get(f"{path}?status=completed&page=1&page_size=20", headers=headers)
    assert not_started.status_code == completed.status_code == 200
    assert not_started.json()["total"] == 2
    assert completed.json()["total"] == 0


# ══════════════════════════════════════════════════════════════════════
# Authorization + isolation
# ══════════════════════════════════════════════════════════════════════


def test_roster_requires_staff(client, db_session):
    tpo = _make_user(db_session, "tpo")
    student = _make_user(db_session, "student")
    drive_id = _published_coding_drive(client, _auth(tpo), name="RBAC Co")

    # Student is forbidden, and must learn nothing about the roster.
    forbidden = client.get(
        f"/api/v1/tpo/mock-drives/{drive_id}/roster", headers=_auth(student)
    )
    assert forbidden.status_code == 403

    # Unauthenticated is 401.
    assert (
        client.get(f"/api/v1/tpo/mock-drives/{drive_id}/roster").status_code == 401
    )


def test_roster_is_scoped_to_its_own_drive(client, db_session):
    tpo = _make_user(db_session, "tpo")
    student = _make_user(db_session, "student")
    tpo_headers = _auth(tpo)

    drive_one = _published_coding_drive(client, tpo_headers, name="Scoped One")
    drive_two = _published_coding_drive(client, tpo_headers, name="Scoped Two")

    # Only drive_one has a participant.
    assert (
        client.post(
            f"/api/v1/mock-drives/{drive_one}/start", headers=_auth(student)
        ).status_code
        == 200
    )

    one = client.get(
        f"/api/v1/tpo/mock-drives/{drive_one}/roster", headers=tpo_headers
    ).json()
    two = client.get(
        f"/api/v1/tpo/mock-drives/{drive_two}/roster", headers=tpo_headers
    ).json()

    assert one["total_participants"] == 1
    assert two["total_participants"] == 0
    assert two["candidates"] == []


# ══════════════════════════════════════════════════════════════════════
# TPO result access (separated from candidate access)
# ══════════════════════════════════════════════════════════════════════


def test_staff_can_read_participant_result_and_non_participant_is_404(
    client, db_session
):
    tpo = _make_user(db_session, "tpo")
    student = _make_user(db_session, "student")
    stranger = _make_user(db_session, "student")
    tpo_headers = _auth(tpo)

    drive_id = _published_coding_drive(client, tpo_headers, name="Result Access Co")
    assert (
        client.post(
            f"/api/v1/mock-drives/{drive_id}/start", headers=_auth(student)
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/mock-drives/{drive_id}/advance", headers=_auth(student)
        ).status_code
        == 200
    )

    result = client.get(
        f"/api/v1/tpo/mock-drives/{drive_id}/candidates/{student.id}/result",
        headers=tpo_headers,
    )
    assert result.status_code == 200, result.text
    assert result.json()["candidate_id"] == student.id
    assert result.json()["status"] == "completed"

    # A candidate who never attempted the drive has no result.
    missing = client.get(
        f"/api/v1/tpo/mock-drives/{drive_id}/candidates/{stranger.id}/result",
        headers=tpo_headers,
    )
    assert missing.status_code == 404

    # Students cannot use the staff result route (access stays separated).
    assert (
        client.get(
            f"/api/v1/tpo/mock-drives/{drive_id}/candidates/{student.id}/result",
            headers=_auth(student),
        ).status_code
        == 403
    )


def test_candidate_cannot_read_another_candidates_status(client, db_session):
    tpo = _make_user(db_session, "tpo")
    student_a = _make_user(db_session, "student")
    student_b = _make_user(db_session, "student")
    drive_id = _published_coding_drive(client, _auth(tpo), name="Status Isolation Co")

    assert (
        client.post(
            f"/api/v1/mock-drives/{drive_id}/start", headers=_auth(student_a)
        ).status_code
        == 200
    )

    # B has no attempt: the student status route reports not_started for B, and
    # A's own attempt is unaffected.
    b_status = client.get(
        f"/api/v1/mock-drives/{drive_id}/status", headers=_auth(student_b)
    )
    assert b_status.status_code == 200
    assert b_status.json()["status"] == "not_started"

    a_status = client.get(
        f"/api/v1/mock-drives/{drive_id}/status", headers=_auth(student_a)
    )
    assert a_status.json()["status"] == "in_progress"


def test_faculty_assessment_activity_is_department_scoped_filtered_and_score_safe(
    client, db_session
):
    faculty = _make_user(db_session, "faculty")
    db_session.add(FacultyProfile(user_id=faculty.id, department="Computer Science"))
    in_scope = _make_user(db_session, "student")
    out_scope = _make_user(db_session, "student")
    db_session.query(StudentProfile).filter_by(user_id=in_scope.id).one().department = "Computer Science"
    db_session.query(StudentProfile).filter_by(user_id=out_scope.id).one().department = "Mathematics"

    pending_session = AssessmentSession(
        user_id=in_scope.id, status="completed", started_at=datetime.utcnow(), completed_at=datetime.utcnow()
    )
    active_session = AssessmentSession(
        user_id=in_scope.id, status="in_progress", started_at=datetime.utcnow()
    )
    outside_session = AssessmentSession(
        user_id=out_scope.id, status="in_progress", started_at=datetime.utcnow()
    )
    db_session.add_all([pending_session, active_session, outside_session])
    db_session.flush()
    db_session.add_all([
        AssessmentRound(session_id=pending_session.id, round_type="coding", status="completed", score=0.0),
        AssessmentRound(session_id=active_session.id, round_type="aptitude", status="active", score=0.0),
        AssessmentRound(session_id=outside_session.id, round_type="aptitude", status="active", score=0.0),
    ])
    db_session.commit()

    response = client.get(
        "/api/v1/profile/cohort/assessment-activity?round_type=coding",
        headers=_auth(faculty),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    row = body["records"][0]
    assert row["student"]["user_id"] == in_scope.id
    assert row["evaluation_status"] == "awaiting_evaluation"
    assert row["score"] is None
    assert row["score_scale"] is None

    search = client.get(
        f"/api/v1/profile/cohort/assessment-activity?search={in_scope.name}&needs_attention=true&page=2&page_size=1",
        headers=_auth(faculty),
    )
    assert search.status_code == 200, search.text
    assert search.json()["total"] == 2
    assert search.json()["page"] == 2
    assert len(search.json()["records"]) == 1

    student_access = client.get(
        "/api/v1/profile/cohort/assessment-activity", headers=_auth(in_scope)
    )
    assert student_access.status_code == 403

    scoped_detail = client.get(
        f"/api/v1/profile/cohort/students?student_id={out_scope.id}&page=1&page_size=1",
        headers=_auth(faculty),
    )
    assert scoped_detail.status_code == 200
    assert scoped_detail.json()["students"] == []


def test_faculty_improvement_compares_only_same_drive_blueprint_and_authorized_students(
    client, db_session, monkeypatch
):
    import app.services.faculty_dashboard_analytics_service as analytics

    faculty = _make_user(db_session, "faculty")
    db_session.add(FacultyProfile(user_id=faculty.id, department="Computer Science"))
    student = _make_user(db_session, "student")
    insufficient = _make_user(db_session, "student")
    outside = _make_user(db_session, "student")
    for user, department in ((student, "Computer Science"), (insufficient, "Computer Science"), (outside, "Mathematics")):
        db_session.query(StudentProfile).filter_by(user_id=user.id).one().department = department

    tpo = _make_user(db_session, "tpo")
    drive_a = _published_coding_drive(client, _auth(tpo), name="Comparable Drive")
    drive_b = _published_coding_drive(client, _auth(tpo), name="Different Drive")

    def add_attempt(user, drive_id, score, day, blueprint_version=1):
        context = AssessmentContext(
            mode="mock_drive", purpose="mock_drive", student_id=user.id,
            policy_id=DEFAULT_PRACTICE_POLICY_ID, mock_drive_id=drive_id,
            blueprint_snapshot={"blueprint_id": 91, "blueprint_version": blueprint_version},
            status="completed", created_at=datetime(2026, 1, day), completed_at=datetime(2026, 1, day),
        )
        db_session.add(context)
        db_session.flush()
        db_session.add(AssessmentSession(
            user_id=user.id, context_id=context.id, status="completed",
            total_score=score, started_at=datetime(2026, 1, day), completed_at=datetime(2026, 1, day),
        ))

    add_attempt(student, drive_a, 40, 1)
    add_attempt(student, drive_a, 60, 2)
    add_attempt(student, drive_b, 10, 3)  # Separate drive must not compare.
    add_attempt(student, drive_a, 90, 4, blueprint_version=2)  # Separate blueprint version.
    add_attempt(insufficient, drive_a, 50, 1)
    add_attempt(outside, drive_a, 10, 1)
    add_attempt(outside, drive_a, 90, 2)
    db_session.commit()

    monkeypatch.setattr(analytics, "score_session_competencies", lambda _db, session, evidence_mappings=None: {
        "overall_score_status": "final", "overall_score": session.total_score,
        "blueprint_id": session.context.blueprint_snapshot["blueprint_id"],
        "blueprint_version": session.context.blueprint_snapshot["blueprint_version"],
    })
    response = client.get("/api/v1/profile/cohort/improvement", headers=_auth(faculty))
    assert response.status_code == 200, response.text
    assert response.json()["improving_students"] == 1
    assert response.json()["students_compared"] == 1
    assert response.json()["comparison_scopes"] == 1
    assert response.json()["authorized_students"] == 2

    forbidden = client.get("/api/v1/profile/cohort/improvement", headers=_auth(student))
    assert forbidden.status_code == 403


def test_faculty_improvement_reports_insufficient_history_without_zero(client, db_session):
    faculty = _make_user(db_session, "faculty")
    db_session.add(FacultyProfile(user_id=faculty.id, department="Computer Science"))
    db_session.commit()
    response = client.get("/api/v1/profile/cohort/improvement", headers=_auth(faculty))
    assert response.status_code == 200, response.text
    assert response.json()["available"] is False
    assert response.json()["improving_students"] is None
    assert response.json()["students_compared"] == 0


def test_faculty_improvement_trend_uses_fixed_authorized_cohort_and_comparable_histories(
    client, db_session, monkeypatch
):
    import app.services.faculty_dashboard_analytics_service as analytics

    faculty = _make_user(db_session, "faculty")
    db_session.add(FacultyProfile(user_id=faculty.id, department="Computer Science"))
    first = _make_user(db_session, "student")
    second = _make_user(db_session, "student")
    single_attempt = _make_user(db_session, "student")
    provisional_only = _make_user(db_session, "student")
    outside = _make_user(db_session, "student")
    for user, department in (
        (first, "Computer Science"),
        (second, "Computer Science"),
        (single_attempt, "Computer Science"),
        (provisional_only, "Computer Science"),
        (outside, "Mathematics"),
    ):
        db_session.query(StudentProfile).filter_by(user_id=user.id).one().department = department

    tpo = _make_user(db_session, "tpo")
    drive = _published_coding_drive(client, _auth(tpo), name="Trend Comparable Drive")

    def add_attempt(user, score, day, *, blueprint_version=1, context_status="completed"):
        context = AssessmentContext(
            mode="mock_drive", purpose="mock_drive", student_id=user.id,
            policy_id=DEFAULT_PRACTICE_POLICY_ID, mock_drive_id=drive,
            blueprint_snapshot={"blueprint_id": 91, "blueprint_version": blueprint_version},
            status=context_status, created_at=datetime(2026, 2, day), completed_at=datetime(2026, 2, day),
        )
        db_session.add(context)
        db_session.flush()
        db_session.add(AssessmentSession(
            user_id=user.id, context_id=context.id, status="completed", total_score=score,
            started_at=datetime(2026, 2, day), completed_at=datetime(2026, 2, day),
        ))
        return context

    add_attempt(first, 40, 1)
    duplicate_session_context = add_attempt(first, 60, 2)
    add_attempt(first, 80, 3)
    add_attempt(second, 60, 1)
    add_attempt(second, 70, 2)
    add_attempt(second, 90, 3)
    add_attempt(single_attempt, 99, 1)
    add_attempt(first, 100, 4, blueprint_version=2)  # Different pinned definition.
    add_attempt(provisional_only, 10, 1)
    add_attempt(provisional_only, 20, 2)
    add_attempt(outside, 1, 1)
    add_attempt(outside, 99, 2)
    add_attempt(first, 100, 5, context_status="cancelled")
    db_session.add(AssessmentSession(
        user_id=first.id, context_id=duplicate_session_context.id, status="completed", total_score=65,
        started_at=datetime(2026, 2, 2, 1), completed_at=datetime(2026, 2, 2, 1),
    ))
    db_session.commit()

    monkeypatch.setattr(analytics, "score_session_competencies", lambda _db, session: {
        "overall_score_status": "provisional" if session.total_score in {10, 20} else "final",
        "overall_score": session.total_score,
        "blueprint_id": session.context.blueprint_snapshot["blueprint_id"],
        "blueprint_version": session.context.blueprint_snapshot["blueprint_version"],
    })
    response = client.get("/api/v1/profile/cohort/improvement-trend", headers=_auth(faculty))
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["available"] is True
    assert payload["distinct_students"] == 2
    assert payload["comparable_series"] == 2
    assert payload["partial_coverage"] is True
    assert [point["average_score"] for point in payload["points"]] == [50, 67.5, 85]
    assert [point["distinct_students"] for point in payload["points"]] == [2, 2, 2]
    assert [point["score_change_percentage_points"] for point in payload["points"]] == [None, 17.5, 17.5]
    assert payload["included_attempts"] == 6
    assert payload["scored_attempts"] == 8
    assert payload["excluded_attempts"] == 4

    forbidden = client.get("/api/v1/profile/cohort/improvement-trend", headers=_auth(first))
    assert forbidden.status_code == 403
