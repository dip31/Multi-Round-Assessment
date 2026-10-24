"""Faculty Practice Assessment reads use isolated in-memory SQLite records."""

from datetime import datetime, timedelta, timezone
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config.security import create_access_token
from app.database.base import Base
from app.database.db import get_db
from app.main import app as application
from app.models.assessment import AssessmentRound, AssessmentSession
from app.models.assessment_context import AssessmentContext, AssessmentPolicy
from app.models.aptitude import AptitudeAttempt, AptitudeQuestion
from app.models.coding import CodingProblem, CodingSubmission
from app.models.interview import InterviewSession, InterviewTurn
from app.models.profile import FacultyProfile, StudentProfile
from app.models.user import User
from app.models.faculty_practice_assessment import FacultyPracticeAssessment, FacultyPracticeRoundAttempt
from app.services.faculty_practice_assessment_service import _activity_status
from types import SimpleNamespace


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "TEXT"


engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="module", autouse=True)
def create_schema():
    Base.metadata.create_all(bind=engine)
    with TestingSessionLocal() as db:
        db.add(AssessmentPolicy(
            id=2,
            name="Practice policy",
            session_duration_minutes=180,
            round_duration_minutes=30,
            progression_mode="independent",
            progression_config={},
        ))
        db.commit()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    db = TestingSessionLocal(bind=connection)
    yield db
    db.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    application.dependency_overrides[get_db] = override_get_db
    with TestClient(application) as test_client:
        yield test_client
    application.dependency_overrides.pop(get_db, None)


def _user(db: Session, role: str, name: str | None = None, department: str = "Computer Science") -> User:
    suffix = uuid.uuid4().hex[:10]
    user = User(
        name=name or f"{role.title()} {suffix}",
        email=f"{role}-{suffix}@example.test",
        password_hash="not-used",
        role=role,
    )
    db.add(user)
    db.flush()
    if role == "faculty":
        db.add(FacultyProfile(user_id=user.id, department=department))
    if role == "student":
        db.add(StudentProfile(user_id=user.id, department=department, full_name=name))
    db.flush()
    return user


def _practice_session(db: Session, student: User, mode: str = "practice", status: str = "completed"):
    context = AssessmentContext(
        mode=mode,
        purpose=mode,
        student_id=student.id,
        policy_id=2,
        status="completed" if status == "completed" else "active",
    )
    db.add(context)
    db.flush()
    session = AssessmentSession(
        user_id=student.id,
        context_id=context.id,
        status=status,
        started_at=datetime(2026, 10, 1, 12, 0, 0),
        completed_at=datetime(2026, 10, 1, 12, 30, 0) if status == "completed" else None,
    )
    db.add(session)
    db.flush()
    return context, session


def _round(db: Session, session: AssessmentSession, kind: str, status: str = "completed", score: float = 0.0):
    round_item = AssessmentRound(
        session_id=session.id,
        round_type=kind,
        status=status,
        score=score,
        max_questions=20,
        started_at=datetime(2026, 10, 1, 12, 0, 0),
        completed_at=datetime(2026, 10, 1, 12, 30, 0) if status == "completed" else None,
    )
    db.add(round_item)
    db.flush()
    return round_item


def _auth(user: User):
    return {"Authorization": f"Bearer {create_access_token(data={'sub': str(user.id)})}"}


def test_practice_list_excludes_other_modes_legacy_and_other_departments(client, db_session):
    faculty = _user(db_session, "faculty")
    in_scope = _user(db_session, "student", "Verified Student")
    out_scope = _user(db_session, "student", "Outside Student", "Mathematics")
    _, practice = _practice_session(db_session, in_scope, "practice")
    _, second_practice = _practice_session(db_session, in_scope, "practice")
    _, mock = _practice_session(db_session, in_scope, "mock_drive")
    _, portfolio = _practice_session(db_session, in_scope, "portfolio_verification")
    _, outside = _practice_session(db_session, out_scope, "practice")
    legacy = AssessmentSession(user_id=in_scope.id, status="completed")
    db_session.add(legacy)
    db_session.flush()
    for session in (practice, second_practice, mock, portfolio, outside, legacy):
        _round(db_session, session, "aptitude")
    db_session.flush()

    response = client.get(
        "/api/v1/profile/cohort/practice-assessment-activity?page=1&page_size=1",
        headers=_auth(faculty),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 2
    assert body["records"][0]["session_id"] in {practice.id, second_practice.id}
    assert body["records"][0]["assessment_type"] == "practice"
    assert body["records"][0]["student"]["name"] == "Verified Student"
    assert body["pages"] == 2

    report = client.get(
        f"/api/v1/profile/cohort/practice-assessment-activity/students/{in_scope.id}/report",
        headers=_auth(faculty),
    )
    assert report.status_code == 200
    report_body = report.json()
    assert report_body["summary"]["practice_sessions"] == 2
    assert {item["session_id"] for item in report_body["history"]} == {practice.id, second_practice.id}


def test_student_identity_uses_profile_name_then_linked_canonical_user_name(client, db_session):
    faculty = _user(db_session, "faculty")
    canonical = _user(db_session, "student", "Canonical Profile Name")
    canonical.name = "No Auto Test"
    missing = _user(db_session, "student", "Coding MCQ Test")
    missing.student_profile.full_name = None
    linked_name_only = _user(db_session, "student", "Ava Johnson")
    linked_name_only.student_profile.full_name = None
    verified_name = _user(db_session, "student", "Interview Coding Test")
    verified_name.student_profile.full_name = None
    verified_name.is_verified = True
    _, first_session = _practice_session(db_session, canonical)
    _, second_session = _practice_session(db_session, missing)
    _, third_session = _practice_session(db_session, linked_name_only)
    _, fourth_session = _practice_session(db_session, verified_name)
    _round(db_session, first_session, "aptitude", status="active")
    _round(db_session, second_session, "aptitude", status="active")
    _round(db_session, third_session, "aptitude", status="active")
    _round(db_session, fourth_session, "aptitude", status="active")
    db_session.flush()

    response = client.get("/api/v1/profile/cohort/practice-assessment-activity", headers=_auth(faculty))
    assert response.status_code == 200
    names = {row["session_id"]: row["student"]["name"] for row in response.json()["records"]}
    assert names[first_session.id] == "Canonical Profile Name"
    assert names[second_session.id] == "Student identity unavailable"
    assert names[third_session.id] == "Ava Johnson"
    assert names[fourth_session.id] == "Interview Coding Test"
    identities = {row["session_id"]: row["student"] for row in response.json()["records"]}
    assert identities[first_session.id]["name_source"] == "student_profile"
    assert identities[second_session.id]["name_source"] == "unavailable"
    assert identities[third_session.id]["name_source"] == "linked_user_account"
    assert identities[fourth_session.id]["name_source"] == "linked_user_account"
    assert all(row["assessment_name"] == "Practice Assessment" for row in response.json()["records"])
    assert names[first_session.id] == "Canonical Profile Name"
    assert "No Auto Test" not in names.values()
    assert "Coding MCQ Test" not in names.values()


def test_activity_filters_report_detail_and_authorization(client, db_session):
    faculty = _user(db_session, "faculty")
    student = _user(db_session, "student", "Practice Candidate")
    outsider = _user(db_session, "student", "Out of scope", "Mathematics")
    _, session = _practice_session(db_session, student)
    round_item = _round(db_session, session, "aptitude", score=0)
    topic_question = AptitudeQuestion(
        question_text="Two plus two?",
        option_a="3", option_b="4", option_c="5", option_d="6",
        correct_option="B", difficulty="easy",
    )
    db_session.add(topic_question)
    db_session.flush()
    db_session.add_all([
        AptitudeAttempt(round_id=round_item.id, question_id=topic_question.id, attempt_number=1, selected_option="B", is_correct=True),
        AptitudeAttempt(round_id=round_item.id, question_id=topic_question.id, attempt_number=2, selected_option="A", is_correct=False),
    ])
    db_session.flush()

    list_response = client.get(
        "/api/v1/profile/cohort/practice-assessment-activity?evaluation_status=completed",
        headers=_auth(faculty),
    )
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1
    row = list_response.json()["records"][0]
    assert row["attempt_count"] == 2
    assert row["attempt_summary"] == {
        "question_attempts": 2,
        "evaluated_answers": 2,
        "correct_answers": 1,
    }
    assert row["score"] == 50.0
    assert row["score_scale"] == "out of 100"

    report = client.get(
        f"/api/v1/profile/cohort/practice-assessment-activity/students/{student.id}/report",
        headers=_auth(faculty),
    )
    assert report.status_code == 200
    report_body = report.json()
    assert report_body["summary"]["practice_sessions"] == 1
    assert report_body["summary"]["rounds_with_participation"] == 1
    assert report_body["summary"]["question_attempts"] == 2
    assert report_body["summary"]["correct_answers"] == 1
    assert report_body["summary"]["rounds_with_participation"] == 1
    assert report_body["comparisons"] == []
    assert "one evaluated practice result" in report_body["progress_message"].lower()
    history_row = report_body["history"][0]
    assert history_row["assessment_name"] == "Practice Assessment"
    assert history_row["session_name"] == f"Practice Session #{session.id}"
    assert history_row["round_status"] == "completed"
    assert history_row["evaluation_status"] == "completed"
    assert history_row["activity_label"] == "2 questions attempted; 1 correct"
    assert all("StudentProfile" not in note for note in report_body["data_notes"])
    assert any("roll number" in note.lower() for note in report_body["data_notes"])

    details = client.get(
        f"/api/v1/profile/cohort/practice-assessment-activity/students/{student.id}/sessions/{session.id}/rounds/{round_item.id}",
        headers=_auth(faculty),
    )
    assert details.status_code == 200
    assert details.json()["question_attempts"] == 2
    assert details.json()["correct_answers"] == 1
    assert details.json()["has_submission_details"] is True
    assert {answer["attempt_id"] for answer in details.json()["answers"]} == {
        item.id for item in db_session.query(AptitudeAttempt).filter(AptitudeAttempt.round_id == round_item.id).all()
    }
    assert details.json()["answers"][0]["attempted_at"]

    denied = client.get(
        f"/api/v1/profile/cohort/practice-assessment-activity/students/{outsider.id}/report",
        headers=_auth(faculty),
    )
    assert denied.status_code == 404
    wrong_round = client.get(
        f"/api/v1/profile/cohort/practice-assessment-activity/students/{student.id}/sessions/{session.id}/rounds/99999",
        headers=_auth(faculty),
    )
    assert wrong_round.status_code == 404


def test_real_zero_and_unavailable_scores_remain_distinct(client, db_session):
    faculty = _user(db_session, "faculty")
    student = _user(db_session, "student", "Zero Score Candidate")
    _, session = _practice_session(db_session, student)
    zero_round = _round(db_session, session, "aptitude", score=0)
    missing_round = _round(db_session, session, "aptitude", score=0)
    question = AptitudeQuestion(
        question_text="One plus one?",
        option_a="1", option_b="2", option_c="3", option_d="4",
        correct_option="B", difficulty="easy",
    )
    db_session.add(question)
    db_session.flush()
    db_session.add(AptitudeAttempt(
        round_id=zero_round.id,
        question_id=question.id,
        attempt_number=1,
        selected_option="A",
        is_correct=False,
    ))
    db_session.flush()

    response = client.get(
        "/api/v1/profile/cohort/practice-assessment-activity?round_type=aptitude",
        headers=_auth(faculty),
    )
    assert response.status_code == 200
    records = {row["round_id"]: row for row in response.json()["records"]}
    assert records[zero_round.id]["evaluation_status"] == "completed"
    assert records[zero_round.id]["score"] == 0.0
    assert records[missing_round.id]["evaluation_status"] == "unavailable"
    assert records[missing_round.id]["score"] is None
    assert records[missing_round.id]["activity_label"] == "No attempt recorded"


def test_progress_requires_comparable_evaluated_rounds_and_includes_dates(client, db_session):
    faculty = _user(db_session, "faculty")
    student = _user(db_session, "student", "Progress Candidate")
    question = AptitudeQuestion(
        question_text="A persisted practice question?",
        option_a="A", option_b="B", option_c="C", option_d="D",
        correct_option="A", difficulty="easy",
    )
    db_session.add(question)
    db_session.flush()
    sessions = []
    for day, selected, is_correct in ((1, "B", False), (8, "A", True)):
        _, session = _practice_session(db_session, student)
        round_item = _round(db_session, session, "aptitude")
        session.started_at = datetime(2026, 10, day, 12, 0)
        round_item.started_at = datetime(2026, 10, day, 12, 0)
        round_item.completed_at = datetime(2026, 10, day, 12, 30)
        db_session.add(AptitudeAttempt(
            round_id=round_item.id,
            question_id=question.id,
            attempt_number=1,
            selected_option=selected,
            is_correct=is_correct,
            attempted_at=datetime(2026, 10, day, 12, 15),
        ))
        sessions.append(session)
    db_session.flush()

    response = client.get(
        f"/api/v1/profile/cohort/practice-assessment-activity/students/{student.id}/report",
        headers=_auth(faculty),
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["comparisons"]) == 1
    comparison = body["comparisons"][0]
    assert comparison["first_score"] == 0.0
    assert comparison["latest_score"] == 100.0
    assert comparison["first_date"].startswith("2026-10-01")
    assert comparison["latest_date"].startswith("2026-10-08")


def test_interview_turns_remain_session_level_and_are_not_copied_to_rounds(client, db_session):
    faculty = _user(db_session, "faculty")
    student = _user(db_session, "student", "Interview Candidate")
    _, session = _practice_session(db_session, student)
    first_round = _round(db_session, session, "interview")
    second_round = _round(db_session, session, "interview")
    interview = InterviewSession(session_id=session.id, phase="HR", status="COMPLETED")
    db_session.add(interview)
    db_session.flush()
    db_session.add_all([
        InterviewTurn(interview_id=interview.id, turn_number=1, question_text="Q1", candidate_response="A1", final_score=0.0, is_followup=False),
        InterviewTurn(interview_id=interview.id, turn_number=2, question_text="Q2", candidate_response="A2", final_score=0.7, is_followup=True),
    ])
    db_session.flush()

    response = client.get(
        "/api/v1/profile/cohort/practice-assessment-activity",
        headers=_auth(faculty),
    )
    assert response.status_code == 200
    rows = response.json()["records"]
    assert rows, response.json()
    assert {row["round_id"] for row in rows} == {first_round.id, second_round.id}
    assert all(row["attempt_count"] == 0 for row in rows)
    assert all(row["attempt_summary"] == {} for row in rows)
    assert all(row["score"] is None for row in rows)

    report = client.get(
        f"/api/v1/profile/cohort/practice-assessment-activity/students/{student.id}/report",
        headers=_auth(faculty),
    )
    assert report.status_code == 200
    assert report.json()["summary"]["interview_responses"] == 2
    assert report.json()["session_level_interviews"][0]["evaluated_response_count"] == 2
    assert sum(item["response_count"] for item in report.json()["session_level_interviews"]) == 2


def test_activity_denies_nonfaculty_and_uses_distinct_pending_statuses(client, db_session):
    student = _user(db_session, "student")
    denied = client.get(
        "/api/v1/profile/cohort/practice-assessment-activity",
        headers=_auth(student),
    )
    assert denied.status_code == 403
    round_item = SimpleNamespace(round_type="aptitude", status="completed")
    assert _activity_status(round_item, attempt_rows=[], coding_rows=[], assigned_problem_ids=[]) == "unavailable"
    assert _activity_status(round_item, attempt_rows=[SimpleNamespace(is_correct=None)], coding_rows=[], assigned_problem_ids=[]) == "awaiting_evaluation"
    assert _activity_status(SimpleNamespace(round_type="coding", status="completed"), attempt_rows=[], coding_rows=[SimpleNamespace(problem_id=1, status="running", score=None)], assigned_problem_ids=[1]) == "evaluation_in_progress"
    assert _activity_status(SimpleNamespace(round_type="coding", status="completed"), attempt_rows=[], coding_rows=[SimpleNamespace(problem_id=1, status="internal_error", score=None)], assigned_problem_ids=[1]) == "failed"


@pytest.fixture
def assignment_client():
    """Use a disposable database because assignment endpoints commit records."""
    isolated_engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=isolated_engine)
    isolated_session = sessionmaker(autocommit=False, autoflush=False, bind=isolated_engine)
    with isolated_session() as db:
        db.add(AssessmentPolicy(
            id=2, name="Practice policy", session_duration_minutes=180,
            round_duration_minutes=30, progression_mode="independent", progression_config={},
        ))
        db.commit()

    def override_get_db():
        with isolated_session() as db:
            yield db

    application.dependency_overrides[get_db] = override_get_db
    with TestClient(application) as test_client:
        yield test_client, isolated_session
    application.dependency_overrides.pop(get_db, None)
    isolated_engine.dispose()


def test_faculty_assignment_persists_authorized_recipients_and_is_idempotent(assignment_client):
    client, session_factory = assignment_client
    with session_factory() as db:
        faculty = _user(db, "faculty")
        student = _user(db, "student", "Authorized Student")
        out_of_scope = _user(db, "student", "Other Department", "Mathematics")
        db.commit()
        faculty_id, student_id, out_of_scope_id = faculty.id, student.id, out_of_scope.id

    payload = {
        "title": "Sequential practice",
        "description": "Real practice engine assignment",
        "instructions": "Complete each round in order.",
        "rounds": [
            {"round_type": "aptitude", "practice_type": "mcq"},
            {"round_type": "coding", "practice_type": "coding"},
            {"round_type": "interview", "practice_type": "interview"},
        ],
        "student_ids": [student_id],
    }
    headers = {**_auth(User(id=faculty_id, name="Faculty", email="faculty@x", password_hash="x", role="faculty")), "Idempotency-Key": "faculty-test-assignment-1"}
    created = client.post("/api/v1/faculty/practice-assessments", json=payload, headers=headers)
    assert created.status_code == 201, created.text
    assessment_id = created.json()["id"]
    assert created.json()["assigned_students"] == 1
    assert [item["sequence"] for item in created.json()["rounds"]] == [1, 2, 3]

    repeated = client.post("/api/v1/faculty/practice-assessments", json=payload, headers=headers)
    assert repeated.status_code == 201
    assert repeated.json()["id"] == assessment_id

    rejected = {**payload, "student_ids": [out_of_scope_id]}
    denied = client.post("/api/v1/faculty/practice-assessments", json=rejected, headers={**headers, "Idempotency-Key": "faculty-test-assignment-2"})
    assert denied.status_code == 404

    student_headers = _auth(User(id=student_id, name="Student", email="student@x", password_hash="x", role="student"))
    listed = client.get("/api/v1/student/practice-assignments", headers=student_headers)
    assert listed.status_code == 200
    assignment = listed.json()[0]
    assert assignment["title"] == "Sequential practice"
    assert assignment["assessment_status"] == "published"
    assert assignment["next_round"]["sequence"] == 1
    assert assignment["rounds"][0]["status"] == "not_started"

    launch = client.post("/api/v1/practice/start", json={
        "round_type": "aptitude", "practice_type": "mcq",
        "assignment_id": assignment["assignment_id"],
        "assessment_round_id": assignment["next_round"]["id"],
    }, headers=student_headers)
    assert launch.status_code == 201, launch.text
    engine_round_id = launch.json()["active_round"]["id"]
    with session_factory() as db:
        question = AptitudeQuestion(
            question_text="Zero score evidence?", option_a="A", option_b="B",
            option_c="C", option_d="D", correct_option="A", difficulty="easy",
        )
        db.add(question)
        db.flush()
        db.add(AptitudeAttempt(
            round_id=engine_round_id, question_id=question.id, attempt_number=1,
            selected_option="B", is_correct=False,
        ))
        db.commit()
    with session_factory() as db:
        link = db.query(FacultyPracticeRoundAttempt).filter_by(assignment_id=assignment["assignment_id"]).one()
        assert link.round_id == engine_round_id
        assert link.session_id == launch.json()["session_id"]

    faculty_activity = client.get(
        "/api/v1/profile/cohort/practice-assessment-activity",
        headers=headers,
    )
    assert faculty_activity.status_code == 200
    linked_row = next(row for row in faculty_activity.json()["records"] if row["round_id"] == engine_round_id)
    assert linked_row["assessment_source"] == "faculty_assignment"
    assert linked_row["assessment_name"] == "Sequential practice"
    assert linked_row["assessment_id"] == assessment_id

    faculty_list = client.get("/api/v1/faculty/practice-assessments", headers=headers)
    assert faculty_list.status_code == 200
    assert faculty_list.json()[0]["overall_attempts"] == 1
    assert faculty_list.json()[0]["rounds_total"] == 3
    assert faculty_list.json()[0]["rounds_started"] == 1
    assert "students" not in faculty_list.json()[0]

    blocked = client.post("/api/v1/practice/start", json={
        "round_type": "coding", "practice_type": "coding",
        "assignment_id": assignment["assignment_id"],
        "assessment_round_id": assignment["rounds"][1]["id"],
    }, headers=student_headers)
    assert blocked.status_code == 409

    completed = client.post("/api/v1/practice/complete-round", json={
        "round_id": engine_round_id, "round_type": "aptitude",
    }, headers=student_headers)
    assert completed.status_code == 200, completed.text
    refreshed = client.get("/api/v1/student/practice-assignments", headers=student_headers).json()[0]
    assert refreshed["rounds"][0]["status"] == "evaluated"


    assert refreshed["rounds"][0]["score"] == 0
    assert refreshed["next_round"]["sequence"] == 2

    coding_launch = client.post("/api/v1/practice/start", json={
        "round_type": "coding", "practice_type": "coding",
        "assignment_id": assignment["assignment_id"],
        "assessment_round_id": refreshed["next_round"]["id"],
    }, headers=student_headers)
    assert coding_launch.status_code == 201, coding_launch.text
    with session_factory() as db:
        problem = CodingProblem(title="Assigned problem", description="Test problem")
        db.add(problem)
        db.flush()
        db.add(CodingSubmission(
            round_id=coding_launch.json()["active_round"]["id"], problem_id=problem.id,
            code="", status="running", score=0,
        ))
        db.commit()
    refreshed_again = client.get("/api/v1/student/practice-assignments", headers=student_headers).json()[0]
    assert refreshed_again["rounds"][1]["status"] == "in_progress"
    assert refreshed_again["next_round"]["sequence"] == 2

    coding_completed = client.post("/api/v1/practice/complete-round", json={
        "round_id": coding_launch.json()["active_round"]["id"], "round_type": "coding",
    }, headers=student_headers)
    assert coding_completed.status_code == 200, coding_completed.text
    refreshed_third = client.get("/api/v1/student/practice-assignments", headers=student_headers).json()[0]
    assert refreshed_third["rounds"][1]["status"] == "evaluation_pending"
    assert refreshed_third["rounds"][1]["score"] is None
    assert refreshed_third["next_round"]["sequence"] == 3
    interview_launch = client.post("/api/v1/practice/start", json={
        "round_type": "interview", "practice_type": "interview",
        "assignment_id": assignment["assignment_id"],
        "assessment_round_id": refreshed_third["next_round"]["id"],
    }, headers=student_headers)
    assert interview_launch.status_code == 201, interview_launch.text
    assert interview_launch.json()["active_round"]["round_type"] == "interview"
    with session_factory() as db:
        interview_session = InterviewSession(session_id=interview_launch.json()["session_id"], status="COMPLETED")
        db.add(interview_session)
        db.flush()
        db.add(InterviewTurn(
            interview_id=interview_session.id, turn_number=1, question_text="Interview prompt",
            candidate_response="Response", final_score=0,
        ))
        db.commit()
    interview_completed = client.post("/api/v1/practice/complete-round", json={
        "round_id": interview_launch.json()["active_round"]["id"], "round_type": "interview",
    }, headers=student_headers)
    assert interview_completed.status_code == 200, interview_completed.text
    results = client.get("/api/v1/student/practice-assignments", headers=student_headers).json()[0]
    assert results["rounds"][2]["status"] == "evaluated"
    assert results["rounds"][2]["score"] == 0
    faculty_results = client.get(f"/api/v1/faculty/practice-assessments/{assessment_id}", headers=headers)
    assert faculty_results.status_code == 200
    student_results = faculty_results.json()["students"][0]
    assert [item["status"] for item in student_results["rounds"]] == ["evaluated", "evaluation_pending", "evaluated"]
    assert [item["score"] for item in student_results["rounds"]] == [0, None, 0]
    assert student_results["rounds"][0]["evidence"]["evaluated_questions"] == 1
    assert student_results["rounds"][2]["evidence"]["evaluated_turns"] == 1
    cancelled = client.post(f"/api/v1/faculty/practice-assessments/{assessment_id}/cancel", headers=headers)
    assert cancelled.status_code == 200
    preserved = client.get("/api/v1/student/practice-assignments", headers=student_headers).json()[0]
    assert preserved["available"] is False
    assert preserved["assessment_status"] == "cancelled"
    assert preserved["rounds"][2]["status"] == "evaluated"
    with session_factory() as db:
        assert db.query(FacultyPracticeRoundAttempt).filter_by(assignment_id=assignment["assignment_id"]).count() == 3

    independent_launch = client.post("/api/v1/practice/start", json={
        "round_type": "aptitude", "practice_type": "mcq",
    }, headers=student_headers)
    assert independent_launch.status_code == 201, independent_launch.text
    all_activity = client.get("/api/v1/profile/cohort/practice-assessment-activity", headers=headers)
    assert all_activity.status_code == 200
    rows = all_activity.json()["records"]
    assert len(rows) == 4
    assert sum(row["assessment_source"] == "faculty_assignment" for row in rows) == 3
    assert sum(row["assessment_source"] == "independent_practice" for row in rows) == 1
    independent = next(row for row in rows if row["assessment_source"] == "independent_practice")
    assert independent["assessment_id"] is None

    monitoring = client.get("/api/v1/faculty/practice-assessments", headers=headers)
    assert monitoring.status_code == 200
    assert len(monitoring.json()) == 1
    monitored = monitoring.json()[0]
    assert monitored["assigned_students"] == 1
    assert monitored["overall_attempts"] == 3
    assert monitored["rounds_total"] == 3
    assert monitored["rounds_started"] == 3
    assert monitored["rounds_attempt_completed"] == 3
    assert monitored["rounds_evaluated"] == 2
    assert monitored["rounds_evaluation_pending"] == 1

    outsider_headers = _auth(User(id=out_of_scope_id, name="Other", email="other@x", password_hash="x", role="student"))
    denied_details = client.get(f"/api/v1/student/practice-assignments/{assignment['assignment_id']}", headers=outsider_headers)
    assert denied_details.status_code == 404


def test_monitoring_counts_student_round_opportunities_without_multiplying_round_definitions(client, db_session):
    faculty = _user(db_session, "faculty")
    students = [_user(db_session, "student", f"Monitoring Student {index}") for index in range(2)]
    db_session.commit()
    faculty_headers = _auth(faculty)
    student_headers = [_auth(student) for student in students]

    created = client.post("/api/v1/faculty/practice-assessments", json={
        "title": "Three round monitoring",
        "rounds": [
            {"round_type": "aptitude", "practice_type": "mcq"},
            {"round_type": "coding", "practice_type": "coding"},
            {"round_type": "interview", "practice_type": "interview"},
        ],
        "student_ids": [student.id for student in students],
    }, headers=faculty_headers)
    assert created.status_code == 201, created.text
    assessment_id = created.json()["id"]

    monitoring = client.get("/api/v1/faculty/practice-assessments", headers=faculty_headers).json()[0]
    assert len(monitoring["rounds"]) == 3
    assert monitoring["assigned_students"] == 2
    assert monitoring["rounds_total"] == 6  # Three configured rounds for each of two students.
    assert monitoring["rounds_started"] == 0
    assert monitoring["rounds_attempt_completed"] == 0
    assert monitoring["rounds_evaluated"] == 0
    assert monitoring["rounds_evaluation_pending"] == 0
    assert monitoring["rounds_failed"] == 0

    assignment = client.get("/api/v1/student/practice-assignments", headers=student_headers[0]).json()[0]
    started = client.post("/api/v1/practice/start", json={
        "round_type": "aptitude", "practice_type": "mcq",
        "assignment_id": assignment["assignment_id"],
        "assessment_round_id": assignment["next_round"]["id"],
    }, headers=student_headers[0])
    assert started.status_code == 201, started.text

    monitoring = client.get("/api/v1/faculty/practice-assessments", headers=faculty_headers).json()[0]
    assert monitoring["id"] == assessment_id
    assert monitoring["rounds_total"] == 6
    assert monitoring["rounds_started"] == 1
    assert monitoring["rounds_in_progress"] == 1
    assert monitoring["rounds_attempt_completed"] == 0
    assert monitoring["rounds_evaluated"] == 0
    assert monitoring["rounds_evaluation_pending"] == 0
    assert monitoring["rounds_failed"] == 0


def test_engine_finish_callbacks_release_each_assigned_round(assignment_client):
    client, session_factory = assignment_client
    with session_factory() as db:
        faculty = _user(db, "faculty")
        student = _user(db, "student")
        db.commit()
        faculty_id, student_id = faculty.id, student.id

    faculty_headers = _auth(User(id=faculty_id, name="Faculty", email="faculty-engine@x", password_hash="x", role="faculty"))
    student_headers = _auth(User(id=student_id, name="Student", email="student-engine@x", password_hash="x", role="student"))
    created = client.post("/api/v1/faculty/practice-assessments", json={
        "title": "Engine completion progression",
        "rounds": [
            {"round_type": "aptitude", "practice_type": "mcq"},
            {"round_type": "coding", "practice_type": "coding"},
            {"round_type": "interview", "practice_type": "interview"},
        ],
        "student_ids": [student_id],
    }, headers=faculty_headers)
    assert created.status_code == 201, created.text
    assessment_id = created.json()["id"]

    assignment = client.get("/api/v1/student/practice-assignments", headers=student_headers).json()[0]
    aptitude_start = client.post("/api/v1/practice/start", json={
        "round_type": "aptitude", "practice_type": "mcq",
        "assignment_id": assignment["assignment_id"],
        "assessment_round_id": assignment["next_round"]["id"],
    }, headers=student_headers)
    assert aptitude_start.status_code == 201, aptitude_start.text
    repeated_start = client.post("/api/v1/practice/start", json={
        "round_type": "aptitude", "practice_type": "mcq",
        "assignment_id": assignment["assignment_id"],
        "assessment_round_id": assignment["next_round"]["id"],
    }, headers=student_headers)
    assert repeated_start.status_code == 201, repeated_start.text
    assert repeated_start.json()["session_id"] == aptitude_start.json()["session_id"]
    assert repeated_start.json()["active_round"]["id"] == aptitude_start.json()["active_round"]["id"]
    aptitude_finish = client.post("/api/v1/aptitude/finish", headers=student_headers)
    assert aptitude_finish.status_code == 200, aptitude_finish.text
    assert client.post("/api/v1/coding/start-after-aptitude", headers=student_headers).json() == []

    with session_factory() as db:
        aptitude_session = db.query(AssessmentSession).filter_by(id=aptitude_start.json()["session_id"]).one()
        assert aptitude_session.status == "completed"
        assert db.query(AssessmentSession).filter_by(user_id=student_id, status="in_progress").count() == 0
        assert db.query(AssessmentRound).filter_by(id=aptitude_start.json()["active_round"]["id"]).one().status == "completed"

    assignment = client.get("/api/v1/student/practice-assignments", headers=student_headers).json()[0]
    assert assignment["rounds"][0]["status"] in {"evaluated", "attempt_completed"}
    assert assignment["next_round"]["round_type"] == "coding"
    coding_start = client.post("/api/v1/practice/start", json={
        "round_type": "coding", "practice_type": "coding",
        "assignment_id": assignment["assignment_id"],
        "assessment_round_id": assignment["next_round"]["id"],
    }, headers=student_headers)
    assert coding_start.status_code == 201, coding_start.text
    coding_finish = client.post("/api/v1/coding/finish", headers=student_headers)
    assert coding_finish.status_code == 200, coding_finish.text
    with session_factory() as db:
        coding_session = db.query(AssessmentSession).filter_by(id=coding_start.json()["session_id"]).one()
        assert coding_session.status == "completed"

    assignment = client.get("/api/v1/student/practice-assignments", headers=student_headers).json()[0]
    assert assignment["rounds"][1]["status"] == "attempt_completed"
    assert assignment["next_round"]["round_type"] == "interview"
    interview_start = client.post("/api/v1/practice/start", json={
        "round_type": "interview", "practice_type": "interview",
        "assignment_id": assignment["assignment_id"],
        "assessment_round_id": assignment["next_round"]["id"],
    }, headers=student_headers)
    assert interview_start.status_code == 201, interview_start.text
    with session_factory() as db:
        interview = InterviewSession(session_id=interview_start.json()["session_id"], status="ACTIVE")
        db.add(interview)
        db.commit()
        interview_id = interview.id

    interview_finish = client.post(f"/api/v1/interview/session/{interview_id}/complete", headers=student_headers)
    assert interview_finish.status_code == 200, interview_finish.text
    results = client.get("/api/v1/student/practice-assignments", headers=student_headers).json()[0]
    assert results["rounds"][2]["status"] == "attempt_completed"
    assert results["next_round"] is None
    with session_factory() as db:
        interview_session = db.query(AssessmentSession).filter_by(id=interview_start.json()["session_id"]).one()
        assert interview_session.status == "completed"
        assert db.query(AssessmentContext).filter_by(id=interview_session.context_id).one().status == "completed"

    # Repeating engine finish operations must not reopen or duplicate attempts.
    assert client.post("/api/v1/aptitude/finish", headers=student_headers).status_code == 200
    assert client.post("/api/v1/coding/finish", headers=student_headers).status_code == 200
    assert client.post(f"/api/v1/interview/session/{interview_id}/complete", headers=student_headers).status_code == 200
    faculty_detail = client.get(f"/api/v1/faculty/practice-assessments/{assessment_id}", headers=faculty_headers)
    assert faculty_detail.status_code == 200
    assert faculty_detail.json()["overall_attempts"] == 3


def test_unfinalized_assigned_session_does_not_release_next_round(assignment_client):
    client, session_factory = assignment_client
    with session_factory() as db:
        faculty = _user(db, "faculty")
        student = _user(db, "student")
        db.commit()
        faculty_id, student_id = faculty.id, student.id
    faculty_headers = _auth(User(id=faculty_id, name="Faculty", email="faculty-failure@x", password_hash="x", role="faculty"))
    student_headers = _auth(User(id=student_id, name="Student", email="student-failure@x", password_hash="x", role="student"))
    created = client.post("/api/v1/faculty/practice-assessments", json={
        "title": "Failed finalization remains blocked",
        "rounds": [
            {"round_type": "aptitude", "practice_type": "mcq"},
            {"round_type": "coding", "practice_type": "coding"},
        ],
        "student_ids": [student_id],
    }, headers=faculty_headers)
    assert created.status_code == 201, created.text
    assignment = client.get("/api/v1/student/practice-assignments", headers=student_headers).json()[0]
    started = client.post("/api/v1/practice/start", json={
        "round_type": "aptitude", "practice_type": "mcq",
        "assignment_id": assignment["assignment_id"],
        "assessment_round_id": assignment["next_round"]["id"],
    }, headers=student_headers)
    assert started.status_code == 201, started.text

    # Simulate the engine round being completed while session/context
    # finalization failed. The next round must stay unavailable and guarded.
    with session_factory() as db:
        engine_round = db.query(AssessmentRound).filter_by(id=started.json()["active_round"]["id"]).one()
        engine_round.status = "completed"
        engine_round.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()

    refreshed = client.get("/api/v1/student/practice-assignments", headers=student_headers).json()[0]
    assert refreshed["rounds"][0]["status"] == "attempt_completed"
    assert refreshed["next_round"] is None
    blocked = client.post("/api/v1/practice/start", json={
        "round_type": "coding", "practice_type": "coding",
        "assignment_id": assignment["assignment_id"],
        "assessment_round_id": assignment["rounds"][1]["id"],
    }, headers=student_headers)
    assert blocked.status_code == 409


def test_student_assignment_datetime_roundtrip_and_availability_enforcement(assignment_client):
    client, session_factory = assignment_client
    with session_factory() as db:
        faculty = _user(db, "faculty")
        student = _user(db, "student")
        db.commit()
        faculty_id, student_id = faculty.id, student.id

    faculty_headers = _auth(User(id=faculty_id, name="Faculty", email="faculty-time@x", password_hash="x", role="faculty"))
    student_headers = _auth(User(id=student_id, name="Student", email="student-time@x", password_hash="x", role="student"))
    created = client.post("/api/v1/faculty/practice-assessments", json={
        "title": "Timezone round trip",
        "availability_start": "2026-10-28T06:31:00.000Z",
        "availability_end": "2026-10-28T11:29:00.000Z",
        "rounds": [{"round_type": "aptitude", "practice_type": "mcq"}],
        "student_ids": [student_id],
    }, headers=faculty_headers)
    assert created.status_code == 201, created.text
    assert created.json()["availability_start"] == "2026-10-28T06:31:00"
    assert created.json()["availability_end"] == "2026-10-28T11:29:00"

    assignment = client.get("/api/v1/student/practice-assignments", headers=student_headers).json()[0]
    assert assignment["availability_start"] == "2026-10-28T06:31:00"
    assert assignment["availability_end"] == "2026-10-28T11:29:00"
    assert assignment["assessment_status"] == "published"

    with session_factory() as db:
        assessment = db.query(FacultyPracticeAssessment).filter_by(id=created.json()["id"]).one()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        assessment.availability_start = now - timedelta(minutes=1)
        assessment.availability_end = now + timedelta(hours=1)
        db.commit()
    assignment = client.get("/api/v1/student/practice-assignments", headers=student_headers).json()[0]
    assert assignment["available"] is True
    launch_payload = {
        "round_type": "aptitude", "practice_type": "mcq",
        "assignment_id": assignment["assignment_id"],
        "assessment_round_id": assignment["rounds"][0]["id"],
    }
    launched = client.post("/api/v1/practice/start", json=launch_payload, headers=student_headers)
    assert launched.status_code == 201, launched.text

    with session_factory() as db:
        assessment = db.query(FacultyPracticeAssessment).filter_by(id=created.json()["id"]).one()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        assessment.availability_start = now + timedelta(hours=1)
        assessment.availability_end = now + timedelta(hours=2)
        db.commit()
    not_yet = client.post("/api/v1/practice/start", json=launch_payload, headers=student_headers)
    assert not_yet.status_code == 403
    assert not_yet.json()["detail"] == "This assessment is not available yet."

    with session_factory() as db:
        assessment = db.query(FacultyPracticeAssessment).filter_by(id=created.json()["id"]).one()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        assessment.availability_start = now - timedelta(hours=2)
        assessment.availability_end = now - timedelta(hours=1)
        db.commit()
    expired = client.post("/api/v1/practice/start", json=launch_payload, headers=student_headers)
    assert expired.status_code == 403
    assert expired.json()["detail"] == "This assessment is no longer available."

def test_assessment_input_validation_and_owner_isolation(assignment_client):
    client, session_factory = assignment_client
    with session_factory() as db:
        faculty = _user(db, "faculty")
        other_faculty = _user(db, "faculty")
        student = _user(db, "student", "Student")
        db.commit()
        faculty_id, other_id, student_id = faculty.id, other_faculty.id, student.id
    headers = _auth(User(id=faculty_id, name="Faculty", email="faculty@x", password_hash="x", role="faculty"))
    base = {"title": "Valid", "rounds": [{"round_type": "coding", "practice_type": "coding"}], "student_ids": [student_id]}
    invalid_window = {**base, "availability_start": "2026-10-25T10:00:00", "availability_end": "2026-10-24T10:00:00"}
    assert client.post("/api/v1/faculty/practice-assessments", json=invalid_window, headers=headers).status_code == 422
    invalid_engine = {**base, "rounds": [{"round_type": "coding", "practice_type": "mcq"}]}
    assert client.post("/api/v1/faculty/practice-assessments", json=invalid_engine, headers=headers).status_code == 422
    created = client.post("/api/v1/faculty/practice-assessments", json=base, headers=headers)
    assert created.status_code == 201
    other_headers = _auth(User(id=other_id, name="Other faculty", email="other@x", password_hash="x", role="faculty"))
    assert client.get("/api/v1/faculty/practice-assessments", headers=other_headers).json() == []
    assert client.get(f"/api/v1/faculty/practice-assessments/{created.json()['id']}", headers=other_headers).status_code == 404


def test_weekly_practice_participation_counts_distinct_scoped_students_and_started_sessions(client, db_session):
    faculty = _user(db_session, "faculty")
    first_student = _user(db_session, "student", "Weekly Participant One")
    second_student = _user(db_session, "student", "Weekly Participant Two")
    outsider = _user(db_session, "student", "Outside Weekly Participant", "Mathematics")

    current_time = datetime.now(timezone.utc).replace(tzinfo=None)
    current_week_start = current_time.date() - timedelta(days=current_time.weekday())
    range_start = current_week_start - timedelta(weeks=12)

    def add_session(student, *, offset_days, status="completed", mode="practice"):
        _, session = _practice_session(db_session, student, mode=mode, status=status)
        session.started_at = datetime.combine(range_start + timedelta(days=offset_days), datetime.min.time())
        return session

    # Multiple starts by one student in a week count as one weekly participant.
    add_session(first_student, offset_days=6)
    add_session(first_student, offset_days=6, status="in_progress")
    # The student is counted again after participating in a different week.
    add_session(first_student, offset_days=7, status="expired")
    add_session(second_student, offset_days=1)
    # Outside-scope, non-Practice, and not-started records do not count.
    add_session(outsider, offset_days=2)
    add_session(first_student, offset_days=3, mode="mock_drive")
    add_session(first_student, offset_days=4, status="not_started")
    db_session.flush()

    response = client.get(
        "/api/v1/profile/cohort/practice-assessment-participation",
        headers=_auth(faculty),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["bucket"] == "week"
    assert payload["timezone"] == "UTC"
    assert payload["expected_weeks"] == 12
    assert len(payload["weeks"]) == 12
    assert payload["range_start"] == range_start.isoformat()
    assert payload["range_end"] == (current_week_start - timedelta(days=1)).isoformat()
    assert payload["weeks"][0]["participating_students"] == 2
    assert payload["weeks"][1]["participating_students"] == 1
    assert all(week["participating_students"] == 0 for week in payload["weeks"][2:])


def test_weekly_practice_participation_requires_faculty_authorization(client, db_session):
    student = _user(db_session, "student", "Not Faculty")
    response = client.get(
        "/api/v1/profile/cohort/practice-assessment-participation",
        headers=_auth(student),
    )
    assert response.status_code == 403
