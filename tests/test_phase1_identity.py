"""
Automated tests for Phase 1: Identity, Registration & Role Profiles.
"""

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database.db import get_db
from app.models.user import User
from app.models.profile import StudentProfile, FacultyProfile, TPOProfile

client = TestClient(app)


def test_student_registration_and_profile():
    # Register as student
    uid = uuid.uuid4().hex[:6]
    email = f"phase1_student_{uid}@test.com"
    reg_resp = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Phase1 Student",
            "email": email,
            "password": "Password@123",
            "role": "student",
        },
    )
    assert reg_resp.status_code == 201
    data = reg_resp.json()
    assert data["email"] == email
    assert data["role"] == "student"

    # Login
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password@123"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch full profile
    prof_resp = client.get("/api/v1/profile/me", headers=headers)
    assert prof_resp.status_code == 200
    prof_data = prof_resp.json()
    assert prof_data["name"] == "Phase1 Student"
    assert prof_data["role"] == "student"
    assert prof_data["student_profile"] is not None
    assert prof_data["student_profile"]["department"] == "Computer Science"

    # Update student profile
    update_resp = client.put(
        "/api/v1/profile/student/me",
        headers=headers,
        json={
            "department": "Information Technology",
            "cgpa": 8.75,
            "graduation_year": 2026,
            "backlogs_count": 0,
            "institution": "Institute of Technology",
            "target_role": "Full Stack Engineer",
            "skills": ["Python", "React", "PostgreSQL"],
            "bio": "Passionate developer eager for competitive roles.",
        },
    )
    assert update_resp.status_code == 200
    up_data = update_resp.json()
    assert up_data["department"] == "Information Technology"
    assert up_data["cgpa"] == 8.75
    assert up_data["target_role"] == "Full Stack Engineer"
    assert "React" in up_data["skills"]

    # Verify persisted in /profile/me
    verify_resp = client.get("/api/v1/profile/me", headers=headers)
    assert verify_resp.status_code == 200
    verify_data = verify_resp.json()
    assert verify_data["student_profile"]["cgpa"] == 8.75
    assert verify_data["student_profile"]["target_role"] == "Full Stack Engineer"


def test_faculty_and_tpo_registration():
    # Register as faculty
    fac_uid = uuid.uuid4().hex[:6]
    fac_email = f"phase1_faculty_{fac_uid}@test.com"
    fac_resp = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Dr. Alan Turing",
            "email": fac_email,
            "password": "Password@123",
            "role": "faculty",
        },
    )
    assert fac_resp.status_code == 201
    assert fac_resp.json()["role"] == "faculty"

    # Login
    fac_login = client.post(
        "/api/v1/auth/login",
        json={"email": fac_email, "password": "Password@123"},
    )
    fac_token = fac_login.json()["access_token"]
    fac_headers = {"Authorization": f"Bearer {fac_token}"}

    # Fetch faculty profile
    fac_prof = client.get("/api/v1/profile/me", headers=fac_headers)
    assert fac_prof.status_code == 200
    assert fac_prof.json()["faculty_profile"] is not None

    # Update faculty profile
    fac_update = client.put(
        "/api/v1/profile/faculty/me",
        headers=fac_headers,
        json={
            "department": "Computer Science & Engineering",
            "designation": "Professor & Head",
            "employee_id": "EMP-9021",
        },
    )
    assert fac_update.status_code == 200
    assert fac_update.json()["designation"] == "Professor & Head"

    # Register as TPO
    tpo_uid = uuid.uuid4().hex[:6]
    tpo_email = f"phase1_tpo_{tpo_uid}@test.com"
    tpo_resp = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Chief Placement Officer",
            "email": tpo_email,
            "password": "Password@123",
            "role": "tpo",
        },
    )
    assert tpo_resp.status_code == 201
    assert tpo_resp.json()["role"] == "tpo"

    # Login
    tpo_login = client.post(
        "/api/v1/auth/login",
        json={"email": tpo_email, "password": "Password@123"},
    )
    tpo_token = tpo_login.json()["access_token"]
    tpo_headers = {"Authorization": f"Bearer {tpo_token}"}

    # Update TPO profile
    tpo_update = client.put(
        "/api/v1/profile/tpo/me",
        headers=tpo_headers,
        json={
            "institution": "Apex University",
            "designation": "Director of Placements",
            "contact_phone": "+91-9876543210",
        },
    )
    assert tpo_update.status_code == 200
    assert tpo_update.json()["institution"] == "Apex University"


def test_student_extended_profile_fields():
    # Register new student
    uid = uuid.uuid4().hex[:6]
    email = f"extended_student_{uid}@test.com"
    reg_resp = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Original Name",
            "email": email,
            "password": "Password@123",
            "role": "student",
        },
    )
    assert reg_resp.status_code == 201

    # Login
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password@123"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Update with all 8 new fields
    payload = {
        "full_name": "Aarav Sharma",
        "gender": "Male",
        "nationality": "Indian",
        "date_of_birth": "2002-05-15",
        "mobile_no": "+91 98765 43210",
        "college_email_id": f"aarav.{uid}@apexuniv.edu.in",
        "tenth_marks": 92.5,
        "twelfth_marks": 89.0,
        "department": "Computer Science",
        "cgpa": 9.15,
        "graduation_year": 2026,
        "backlogs_count": 0,
        "target_role": "AI Engineer",
        "skills": ["Python", "FastAPI", "TensorFlow"],
    }
    update_resp = client.put(
        "/api/v1/profile/student/me",
        headers=headers,
        json=payload,
    )
    assert update_resp.status_code == 200
    up_data = update_resp.json()
    assert up_data["full_name"] == "Aarav Sharma"
    assert up_data["gender"] == "Male"
    assert up_data["nationality"] == "Indian"
    assert up_data["date_of_birth"] == "2002-05-15"
    assert up_data["mobile_no"] == "+91 98765 43210"
    assert up_data["college_email_id"] == f"aarav.{uid}@apexuniv.edu.in"
    assert up_data["tenth_marks"] == 92.5
    assert up_data["twelfth_marks"] == 89.0

    # Verify via /api/v1/profile/student/me
    get_me = client.get("/api/v1/profile/student/me", headers=headers)
    assert get_me.status_code == 200
    me_data = get_me.json()
    assert me_data["full_name"] == "Aarav Sharma"
    assert me_data["tenth_marks"] == 92.5
    assert me_data["twelfth_marks"] == 89.0
    assert me_data["nationality"] == "Indian"

    # Verify user name synchronized on /api/v1/profile/me
    base_prof = client.get("/api/v1/profile/me", headers=headers)
    assert base_prof.status_code == 200
    assert base_prof.json()["name"] == "Aarav Sharma"
    assert base_prof.json()["student_profile"]["tenth_marks"] == 92.5
