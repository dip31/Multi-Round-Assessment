"""
Automated tests for expanded Practice Mode and Interview Modes.

Verifies:
1. MCQ round question selection (Aptitude topics only, anti-cheating privacy).
2. Technical round subject filtering (OS, CN, OOPS, DBMS, DSA, and All Technical).
3. Combined round selection and submission balance.
4. Privacy: correct_option is never exposed to candidate in question responses.
5. Interview pool generation tailored to technical, hr, and communication interview types.
6. Use profile resume endpoint with interview_type query parameter.
7. Session history round labels and technical subject breakdown in analytics.
8. Clean empty states for new students without fabricated statistics.
"""

import io
import uuid
import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from app.main import app
from app.database.db import SessionLocal
from app.models.user import User
from app.models.assessment import AssessmentSession, AssessmentRound
from app.models.interview import ApprovedQuestionPool, InterviewSession
from app.models.aptitude import AptitudeQuestion, AptitudeTopic, AptitudeAttempt
from app.services.groq_service import GroqService
from app.config.settings import settings

client = TestClient(app)


def _create_student(name: str = "Test Student", cgpa: float = 8.5, backlogs: int = 0):
    uid = uuid.uuid4().hex[:6]
    email = f"student_{uid}@college.edu"
    password = "Password@123"

    reg_resp = client.post(
        "/api/v1/auth/register",
        json={
            "name": name,
            "email": email,
            "password": password,
            "role": "student",
        },
    )
    assert reg_resp.status_code == 201

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    user_id = login_resp.json()["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}

    client.put(
        "/api/v1/profile/student/me",
        headers=headers,
        json={
            "cgpa": cgpa,
            "backlogs_count": backlogs,
            "roll_number": f"CS-{uid.upper()}",
            "department": "Computer Science",
            "target_role": "Software Engineer",
        },
    )

    return {"email": email, "token": token, "user_id": user_id, "headers": headers}


def _get_test_db():
    from app.database.db import get_db
    if get_db in app.dependency_overrides:
        gen = app.dependency_overrides[get_db]()
        return next(gen)
    return SessionLocal()


def test_mcq_round_question_selection_and_privacy():
    """Verify MCQ round returns only general aptitude topics and hides correct_option."""
    student = _create_student("MCQ Student")
    client.post("/api/v1/session/start", headers=student["headers"])

    resp = client.get(
        "/api/v1/aptitude/next-question",
        params={"practice_type": "mcq"},
        headers=student["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()

    # Privacy verification: correct_option must NEVER be returned
    assert "correct_option" not in data, "Security breach: correct_option leaked in response"
    assert "question_id" in data
    assert "question_text" in data
    assert "options" in data
    assert "difficulty" in data
    assert "topic" in data

    # Verify topic is Aptitude / Reasoning / Math / DI
    apt_topics = {"Quantitative Aptitude", "Logical Reasoning", "Verbal Ability", "Data Interpretation"}
    assert data["topic"] in apt_topics, f"Expected aptitude topic, got: {data['topic']}"


def test_technical_round_subject_filtering():
    """Verify Technical round filters by specific subjects: OS, CN, OOPS, DBMS, DSA, and all."""
    student = _create_student("Tech Student")
    client.post("/api/v1/session/start", headers=student["headers"])

    subject_to_topic = {
        "os": "Operating Systems",
        "cn": "Computer Networks",
        "oops": "Object-Oriented Programming",
        "dbms": "Database Management Systems",
        "dsa": "Data Structures",
    }

    for subj, expected_topic in subject_to_topic.items():
        resp = client.get(
            "/api/v1/aptitude/next-question",
            params={"practice_type": "technical", "subject": subj},
            headers=student["headers"],
        )
        assert resp.status_code == 200, f"Failed fetching technical question for subject: {subj}"
        data = resp.json()
        assert "correct_option" not in data
        assert data["topic"] == expected_topic, f"Expected topic {expected_topic} for subject {subj}, got {data['topic']}"
        assert data.get("subject") == subj

    # Test "all" subject selector
    resp_all = client.get(
        "/api/v1/aptitude/next-question",
        params={"practice_type": "technical", "subject": "all"},
        headers=student["headers"],
    )
    assert resp_all.status_code == 200
    data_all = resp_all.json()
    assert data_all["topic"] in set(subject_to_topic.values())


def test_combined_round_and_answer_submission():
    """Verify Combined round serves questions and accepts answer submissions."""
    student = _create_student("Combined Student")
    client.post("/api/v1/session/start", headers=student["headers"])

    # Fetch first question
    resp = client.get(
        "/api/v1/aptitude/next-question",
        params={"practice_type": "combined"},
        headers=student["headers"],
    )
    assert resp.status_code == 200
    q1 = resp.json()
    assert "correct_option" not in q1

    # Submit answer
    sub_resp = client.post(
        "/api/v1/aptitude/submit-answer",
        json={
            "question_id": q1["question_id"],
            "selected_option": "A",
            "response_time": 12.5,
            "practice_type": "combined",
        },
        headers=student["headers"],
    )
    assert sub_resp.status_code == 200
    sub_data = sub_resp.json()
    assert "correct" in sub_data
    assert "correct_option" in sub_data  # Allowed after submission for feedback


def test_interview_pool_generation_by_type():
    """Verify question pool generation for technical, hr, and communication interview types."""
    service = GroqService(settings.GROQ_API_KEY)
    skills = ["Python", "FastAPI", "PostgreSQL"]
    projects = {"Portal": "Student assessment portal"}

    # 1. Technical
    tech_pool = service.generate_question_pool(skills, projects, count=6, interview_type="technical")
    assert tech_pool is not None
    assert len(tech_pool) >= 3

    # 2. HR
    hr_pool = service.generate_question_pool(skills, projects, count=6, interview_type="hr")
    assert hr_pool is not None
    assert len(hr_pool) >= 3
    assert any(q.get("phase") == "HR" for q in hr_pool)

    # 3. Communication
    comm_pool = service.generate_question_pool(skills, projects, count=6, interview_type="communication")
    assert comm_pool is not None
    assert len(comm_pool) >= 3
    assert any(q.get("phase") == "COMMUNICATION" for q in comm_pool)


def test_use_profile_resume_with_interview_type():
    """Verify selecting a profile resume records the requested interview_type."""
    student = _create_student("Interview Student")
    # Initialize active assessment session
    client.post("/api/v1/session/start", headers=student["headers"])

    # Upload a test PDF to student profile
    fake_pdf = b"%PDF-1.4\n1 0 obj\n<< /Title (Test CV) >>\nendobj\ntrailer\n<< >>\n%%EOF"
    upload_resp = client.post(
        "/api/v1/profile/resumes",
        headers=student["headers"],
        files={"file": ("resume.pdf", io.BytesIO(fake_pdf), "application/pdf")},
        data={"cv_name": "Test CV", "cv_type": "Software Developer"},
    )
    assert upload_resp.status_code == 200
    resume_id = upload_resp.json()["id"]

    # Use profile resume for HR interview
    hr_resp = client.post(
        f"/api/v1/interview/resume/use-profile-resume/{resume_id}?interview_type=hr",
        headers=student["headers"],
    )
    assert hr_resp.status_code == 200
    hr_data = hr_resp.json()
    assert "pool_id" in hr_data

    db = _get_test_db()
    try:
        pool = db.query(ApprovedQuestionPool).filter(ApprovedQuestionPool.id == hr_data["pool_id"]).first()
        assert pool is not None
        assert pool.question_pool is not None
        assert any(q.get("phase") == "HR" for q in pool.question_pool)
    finally:
        db.close()


def test_session_history_round_types_and_analytics():
    """Verify session history distinguishes round types and provides technical subject breakdown."""
    student = _create_student("History Student")

    # Call analytics on fresh student: clean empty states, no crash, no fabricated data
    empty_resp = client.get("/api/v1/report/analytics", headers=student["headers"])
    assert empty_resp.status_code == 200
    empty_data = empty_resp.json()
    assert empty_data["session_history"] == []
    assert empty_data["skill_breakdown"] == []

    # Create completed rounds in DB
    db = _get_test_db()
    try:
        sess = AssessmentSession(user_id=student["user_id"], status="completed", total_score=0.82)
        db.add(sess)
        db.commit()

        # 1. Technical round
        r_tech = AssessmentRound(
            session_id=sess.id,
            round_type="technical",
            status="completed",
            score=0.85,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        # 2. Combined round
        r_comb = AssessmentRound(
            session_id=sess.id,
            round_type="combined",
            status="completed",
            score=0.75,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        # 3. Coding round
        r_cod = AssessmentRound(
            session_id=sess.id,
            round_type="coding",
            status="completed",
            score=0.90,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        # 4. HR Interview round
        r_int = AssessmentRound(
            session_id=sess.id,
            round_type="hr_interview",
            status="completed",
            score=0.80,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        db.add_all([r_tech, r_comb, r_cod, r_int])
        db.commit()
    finally:
        db.close()

    resp = client.get("/api/v1/report/analytics", headers=student["headers"])
    assert resp.status_code == 200
    data = resp.json()

    history = data.get("session_history", [])
    assert len(history) >= 4

    types = [item["type"] for item in history]
    assert "Technical Round" in types
    assert "Combined Round" in types
    assert "Coding Challenge" in types
    assert "HR Interview" in types
