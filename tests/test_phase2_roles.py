"""
Automated tests for Phase 2: Authentication + Role-Based Routing & Authorization.
"""

import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_login_response_payload():
    """Verify login returns token along with user object and role synchronously."""
    uid = uuid.uuid4().hex[:6]
    email = f"phase2_student_{uid}@test.com"
    client.post(
        "/api/v1/auth/register",
        json={
            "name": "Phase2 Candidate",
            "email": email,
            "password": "Password@123",
            "role": "student",
        },
    )

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password@123"},
    )
    assert login_resp.status_code == 200
    data = login_resp.json()

    assert "access_token" in data
    assert data["role"] == "student"
    assert "user" in data
    assert data["user"]["email"] == email
    assert data["user"]["role"] == "student"


def test_faculty_and_tpo_staff_access():
    """Verify faculty and TPO can access cohort analytics and student rosters."""
    # 1. Register and login as Faculty
    fac_email = f"phase2_prof_{uuid.uuid4().hex[:6]}@test.com"
    client.post(
        "/api/v1/auth/register",
        json={
            "name": "Prof. Phase2",
            "email": fac_email,
            "password": "Password@123",
            "role": "faculty",
        },
    )
    fac_login = client.post(
        "/api/v1/auth/login",
        json={"email": fac_email, "password": "Password@123"},
    )
    assert fac_login.status_code == 200
    fac_data = fac_login.json()
    assert fac_data["role"] == "faculty"
    fac_token = fac_data["access_token"]
    fac_headers = {"Authorization": f"Bearer {fac_token}"}

    # Faculty can access cohort stats
    cohort_resp = client.get("/api/v1/report/admin/cohort-stats", headers=fac_headers)
    assert cohort_resp.status_code == 200

    # Faculty can access cohort students roster
    students_resp = client.get("/api/v1/profile/cohort/students", headers=fac_headers)
    assert students_resp.status_code == 200
    assert "students" in students_resp.json()

    # 2. Register and login as TPO
    tpo_email = f"phase2_tpo_{uuid.uuid4().hex[:6]}@test.com"
    client.post(
        "/api/v1/auth/register",
        json={
            "name": "Officer Phase2",
            "email": tpo_email,
            "password": "Password@123",
            "role": "tpo",
        },
    )
    tpo_login = client.post(
        "/api/v1/auth/login",
        json={"email": tpo_email, "password": "Password@123"},
    )
    assert tpo_login.status_code == 200
    tpo_data = tpo_login.json()
    assert tpo_data["role"] == "tpo"
    tpo_token = tpo_data["access_token"]
    tpo_headers = {"Authorization": f"Bearer {tpo_token}"}

    # TPO can access cohort stats and students roster
    tpo_cohort_resp = client.get("/api/v1/report/admin/cohort-stats", headers=tpo_headers)
    assert tpo_cohort_resp.status_code == 200

    tpo_students_resp = client.get("/api/v1/profile/cohort/students", headers=tpo_headers)
    assert tpo_students_resp.status_code == 200


def test_student_forbidden_from_staff_endpoints():
    """Verify students receive 403 Forbidden when trying to access staff cohort endpoints."""
    email = f"phase2_regular_student_{uuid.uuid4().hex[:6]}@test.com"
    client.post(
        "/api/v1/auth/register",
        json={
            "name": "Regular Student",
            "email": email,
            "password": "Password@123",
            "role": "student",
        },
    )
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password@123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Attempting staff endpoints should fail with 403
    stats_resp = client.get("/api/v1/report/admin/cohort-stats", headers=headers)
    assert stats_resp.status_code == 403

    students_resp = client.get("/api/v1/profile/cohort/students", headers=headers)
    assert students_resp.status_code == 403
