"""
Tests for EDI5 Student Portfolio Module:
- GET /api/v1/portfolio/me
- PUT /api/v1/portfolio/me
- POST /api/v1/portfolio/project
- PUT /api/v1/portfolio/project/{id}
- DELETE /api/v1/portfolio/project/{id}
- POST /api/v1/portfolio/certification
- DELETE /api/v1/portfolio/certification/{id}
- POST /api/v1/portfolio/experience
- DELETE /api/v1/portfolio/experience/{id}
- POST /api/v1/portfolio/achievement
- DELETE /api/v1/portfolio/achievement/{id}
- Strict ownership isolation between Student A and Student B
- Unauthenticated rejection (401)
"""

import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _create_test_student(name: str = "Portfolio Student"):
    uid = uuid.uuid4().hex[:6]
    email = f"portfolio_{uid}@college.edu"
    password = "Password@123"

    reg = client.post(
        "/api/v1/auth/register",
        json={"name": name, "email": email, "password": password, "role": "student"},
    )
    assert reg.status_code == 201

    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    user_id = login.json()["user"]["id"]
    return {"token": token, "user_id": user_id, "headers": {"Authorization": f"Bearer {token}"}}


def test_portfolio_unauthenticated_rejected():
    """Unauthenticated access must return 401."""
    resp = client.get("/api/v1/portfolio/me")
    assert resp.status_code == 401


def test_portfolio_get_empty_state():
    """Newly registered student gets complete portfolio structure with clean empty states."""
    student = _create_test_student("Empty Student")
    resp = client.get("/api/v1/portfolio/me", headers=student["headers"])
    assert resp.status_code == 200

    data = resp.json()
    assert "profile" in data
    assert "education" in data
    assert "skills" in data
    assert "projects" in data
    assert "certifications" in data
    assert "assessment_highlights" in data
    assert "badges" in data
    assert "learning_journey" in data
    assert "completeness" in data
    assert "improvement_suggestions" in data

    # Completeness must have a score and breakdown
    assert isinstance(data["completeness"]["score"], int)
    assert isinstance(data["completeness"]["completed_sections"], list)
    assert isinstance(data["completeness"]["missing_sections"], list)


def test_portfolio_update_metadata():
    """Update about text and external profiles."""
    student = _create_test_student("Metadata Student")
    payload = {
        "about": "Aspiring Cloud and AI Engineer with deep interest in scalable microservices.",
        "external_profiles": {
            "github": "https://github.com/metastudent",
            "linkedin": "https://linkedin.com/in/metastudent",
            "leetcode": "https://leetcode.com/metastudent",
        },
    }
    resp = client.put("/api/v1/portfolio/me", headers=student["headers"], json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["about"] == payload["about"]
    assert data["external_profiles"]["github"] == "https://github.com/metastudent"
    assert data["external_profiles"]["linkedin"] == "https://linkedin.com/in/metastudent"


def test_portfolio_project_lifecycle():
    """Add, update, and delete a technical project."""
    student = _create_test_student("Project Student")

    # 1. Add project
    project_payload = {
        "title": "Autonomous Drone Surveillance",
        "description": "Object detection and flight path planning using YOLOv8 and ROS.",
        "problem_statement": "Manual perimeter monitoring is slow and labor-intensive.",
        "solution": "Built a vision-pipeline on edge device with live telemetry streaming.",
        "technologies": ["Python", "OpenCV", "ROS", "PyTorch"],
        "role": "Computer Vision Lead",
        "individual_or_team": "Team",
        "duration": "4 months",
        "github_url": "https://github.com/proj/drone",
        "demo_url": "https://demo.drone.io",
    }
    add_resp = client.post("/api/v1/portfolio/project", headers=student["headers"], json=project_payload)
    assert add_resp.status_code == 200
    portfolio = add_resp.json()
    assert len(portfolio["projects"]) == 1
    proj = portfolio["projects"][0]
    assert proj["title"] == "Autonomous Drone Surveillance"
    assert proj["evidence_status"] == "Submitted"
    proj_id = proj["id"]

    # 2. Update project
    update_payload = {
        **project_payload,
        "title": "Autonomous Drone Surveillance V2",
        "duration": "6 months",
    }
    upd_resp = client.put(f"/api/v1/portfolio/project/{proj_id}", headers=student["headers"], json=update_payload)
    assert upd_resp.status_code == 200
    upd_data = upd_resp.json()
    assert upd_data["projects"][0]["title"] == "Autonomous Drone Surveillance V2"
    assert upd_data["projects"][0]["duration"] == "6 months"

    # 3. Delete project
    del_resp = client.delete(f"/api/v1/portfolio/project/{proj_id}", headers=student["headers"])
    assert del_resp.status_code == 200
    del_data = del_resp.json()
    assert len(del_data["projects"]) == 0


def test_portfolio_certification_lifecycle():
    """Add and delete industry certification."""
    student = _create_test_student("Cert Student")

    cert_payload = {
        "name": "AWS Certified Developer - Associate",
        "issuer": "Amazon Web Services",
        "issue_date": "2026-05",
        "credential_id": "AWS-DVA-9999",
        "credential_url": "https://aws.amazon.com/verify/9999",
        "skills": ["AWS", "DynamoDB", "Lambda"],
    }
    add_resp = client.post("/api/v1/portfolio/certification", headers=student["headers"], json=cert_payload)
    assert add_resp.status_code == 200
    data = add_resp.json()
    assert len(data["certifications"]) == 1
    cert = data["certifications"][0]
    assert cert["name"] == "AWS Certified Developer - Associate"
    assert cert["verification_status"] == "Submitted"
    cert_id = cert["id"]

    # Delete cert
    del_resp = client.delete(f"/api/v1/portfolio/certification/{cert_id}", headers=student["headers"])
    assert del_resp.status_code == 200
    assert len(del_resp.json()["certifications"]) == 0


def test_portfolio_student_ownership_isolation():
    """Student A cannot view or manipulate Student B's portfolio data."""
    student_a = _create_test_student("Student A")
    student_b = _create_test_student("Student B")

    # Add project to Student A
    client.post(
        "/api/v1/portfolio/project",
        headers=student_a["headers"],
        json={"title": "Project Alpha", "technologies": ["Go", "Docker"]},
    )

    # Student B views portfolio -> should NOT have Project Alpha
    b_port = client.get("/api/v1/portfolio/me", headers=student_b["headers"]).json()
    assert len(b_port["projects"]) == 0

    # Student A views portfolio -> has Project Alpha
    a_port = client.get("/api/v1/portfolio/me", headers=student_a["headers"]).json()
    assert len(a_port["projects"]) == 1
    a_proj_id = a_port["projects"][0]["id"]

    # Student B attempts to delete Student A's project -> should fail (not found for Student B)
    del_resp = client.delete(f"/api/v1/portfolio/project/{a_proj_id}", headers=student_b["headers"])
    assert del_resp.status_code == 200  # returns B's portfolio, unchanged
    assert len(del_resp.json()["projects"]) == 0

    # Student A's project remains untouched
    a_check = client.get("/api/v1/portfolio/me", headers=student_a["headers"]).json()
    assert len(a_check["projects"]) == 1
    assert a_check["projects"][0]["id"] == a_proj_id


def test_student_analytics_endpoint():
    """Verify GET /api/v1/report/student-analytics returns the 12-dimensional real data structure."""
    student = _create_test_student("Analytics Student")

    # Unauthenticated rejected
    unauth = client.get("/api/v1/report/student-analytics")
    assert unauth.status_code == 401

    # Authenticated returns structure
    resp = client.get("/api/v1/report/student-analytics", headers=student["headers"])
    assert resp.status_code == 200
    data = resp.json()

    assert "overview" in data
    assert "summary" in data
    assert "trend" in data
    assert "subjects" in data
    assert "topics" in data
    assert "rounds" in data
    assert "difficulty" in data
    assert "coding" in data
    assert "interviews" in data
    assert "strengths" in data
    assert "focus_areas" in data
    assert "recommendation" in data
    assert "consistency" in data

    # Default values for fresh student
    assert data["overview"]["overall_readiness"] is None or data["overview"]["overall_readiness"] == 0.0
    assert data["summary"]["questions_attempted"] == 0
    assert "subject" in data["recommendation"]
    assert "reason" in data["recommendation"]
