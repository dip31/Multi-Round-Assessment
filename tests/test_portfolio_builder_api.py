"""
Integration tests for Portfolio Builder Assessment API.

Tests the complete 6-stage orchestration API endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app

client = TestClient(app)


def _create_test_student(name: str = "Portfolio Builder Student"):
    import uuid
    uid = uuid.uuid4().hex[:6]
    email = f"pb_{uid}@college.edu"
    password = "Pass123!"  # Short password for bcrypt

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


def test_portfolio_builder_unauthenticated_rejected():
    """Unauthenticated access to portfolio builder must return 401."""
    resp = client.get("/api/v1/portfolio-builder")
    assert resp.status_code == 401


def test_portfolio_builder_initialize_creates_attempt():
    """Initialize creates a new Portfolio Builder attempt with 6 stages."""
    student = _create_test_student("Initialize Student")
    
    resp = client.get("/api/v1/portfolio-builder", headers=student["headers"])
    assert resp.status_code == 200
    
    data = resp.json()
    assert "attempt" in data
    assert "is_new" in data
    assert data["is_new"] is True
    
    attempt = data["attempt"]
    assert attempt["user_id"] == student["user_id"]
    assert attempt["current_stage"] == "APTITUDE"
    assert attempt["overall_status"] == "ACTIVE"
    assert len(attempt["stages"]) == 6
    
    # Check stage order
    stage_keys = [s["stage_key"] for s in attempt["stages"]]
    expected = ["APTITUDE", "TECHNICAL_MCQ", "COMBINED_MCQ", "DSA_CODING", "RESUME_INTERVIEW", "COMPETENCY_RESULTS"]
    assert stage_keys == expected
    
    # First stage should be AVAILABLE, rest LOCKED
    assert attempt["stages"][0]["status"] == "AVAILABLE"
    for stage in attempt["stages"][1:]:
        assert stage["status"] == "LOCKED"


def test_portfolio_builder_initialize_idempotent():
    """Repeated initialization returns existing attempt, not a new one."""
    student = _create_test_student("Idempotent Student")
    
    # First call
    resp1 = client.get("/api/v1/portfolio-builder", headers=student["headers"])
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["is_new"] is True
    attempt_id = data1["attempt"]["id"]
    
    # Second call
    resp2 = client.get("/api/v1/portfolio-builder", headers=student["headers"])
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["is_new"] is False
    assert data2["attempt"]["id"] == attempt_id


def test_portfolio_builder_progress_endpoint():
    """Progress endpoint returns lightweight progress info."""
    student = _create_test_student("Progress Student")
    
    # Initialize first
    client.get("/api/v1/portfolio-builder", headers=student["headers"])
    
    # Get progress
    resp = client.get("/api/v1/portfolio-builder/progress", headers=student["headers"])
    assert resp.status_code == 200
    
    data = resp.json()
    assert "attempt_id" in data
    assert "current_stage" in data
    assert "overall_status" in data
    assert "stages" in data
    assert len(data["stages"]) == 6


def test_portfolio_builder_start_first_stage():
    """Starting first stage (APTITUDE) should succeed and return redirect."""
    student = _create_test_student("Start Stage Student")
    
    client.get("/api/v1/portfolio-builder", headers=student["headers"])
    
    resp = client.post(
        "/api/v1/portfolio-builder/stage/start",
        headers=student["headers"],
        json={"stage_key": "APTITUDE"}
    )
    assert resp.status_code == 200
    
    data = resp.json()
    assert data["stage_key"] == "APTITUDE"
    assert data["stage_status"] == "IN_PROGRESS"
    assert "redirect_url" in data
    assert data["redirect_url"].startswith("/aptitude")
    assert "assessment_session_id" in data
    assert "assessment_round_id" in data


def test_portfolio_builder_cannot_skip_stages():
    """Cannot start a later stage without completing prerequisites."""
    student = _create_test_student("Skip Stage Student")
    
    client.get("/api/v1/portfolio-builder", headers=student["headers"])
    
    # Try to start TECHNICAL_MCQ without completing APTITUDE
    resp = client.post(
        "/api/v1/portfolio-builder/stage/start",
        headers=student["headers"],
        json={"stage_key": "TECHNICAL_MCQ"}
    )
    assert resp.status_code == 400
    assert "locked" in resp.json()["detail"].lower() or "prerequisite" in resp.json()["detail"].lower()


def test_portfolio_builder_complete_stage_validates():
    """Completing a stage validates actual assessment completion."""
    student = _create_test_student("Complete Stage Student")
    
    client.get("/api/v1/portfolio-builder", headers=student["headers"])
    
    # Start APTITUDE
    client.post(
        "/api/v1/portfolio-builder/stage/start",
        headers=student["headers"],
        json={"stage_key": "APTITUDE"}
    )
    
    # Try to complete without actual assessment completion
    resp = client.post(
        "/api/v1/portfolio-builder/stage/complete",
        headers=student["headers"],
        json={"stage_key": "APTITUDE"}
    )
    # Should fail because assessment round is not actually completed
    assert resp.status_code == 400


def test_portfolio_builder_stage_results_locked():
    """Cannot get results for locked stage."""
    student = _create_test_student("Results Locked Student")
    
    client.get("/api/v1/portfolio-builder", headers=student["headers"])
    
    # Try to get results for locked stage
    resp = client.get(
        "/api/v1/portfolio-builder/stage/TECHNICAL_MCQ/results",
        headers=student["headers"]
    )
    assert resp.status_code == 403


def test_portfolio_builder_consolidated_results_locked():
    """Consolidated results not available until all stages complete."""
    student = _create_test_student("Results Locked Student 2")
    
    client.get("/api/v1/portfolio-builder", headers=student["headers"])
    
    resp = client.get("/api/v1/portfolio-builder/results", headers=student["headers"])
    assert resp.status_code == 403


def test_portfolio_builder_student_isolation():
    """Student A cannot access Student B's portfolio builder attempt."""
    student_a = _create_test_student("Student A")
    student_b = _create_test_student("Student B")
    
    # Student A initializes
    client.get("/api/v1/portfolio-builder", headers=student_a["headers"])
    
    # Student B tries to access - should get their own empty attempt
    resp = client.get("/api/v1/portfolio-builder", headers=student_b["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["attempt"]["user_id"] == student_b["user_id"]
    assert data["attempt"]["id"] != data["attempt"]["user_id"]  # Different attempt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])