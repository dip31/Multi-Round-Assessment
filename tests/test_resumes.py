"""
Automated tests for Student Resumes & Interview Selection feature.
"""

import io
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import User
from app.models.profile import UserResume
from app.models.assessment import AssessmentSession

client = TestClient(app)


def test_student_multiple_resumes_and_interview_selection():
    uid = uuid.uuid4().hex[:6]
    email = f"resume_student_{uid}@test.com"

    # 1. Register student
    reg_resp = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Resume Student",
            "email": email,
            "password": "Password@123",
            "role": "student",
        },
    )
    assert reg_resp.status_code == 201

    # 2. Login
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password@123"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Dummy PDF content
    fake_pdf = b"%PDF-1.4\n1 0 obj\n<< /Title (Test Resume) >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"

    # 3. Upload first CV (Software Developer)
    cv1_resp = client.post(
        "/api/v1/profile/resumes",
        headers=headers,
        data={"cv_name": "Full Stack Dev CV", "cv_type": "Software Developer"},
        files={"file": ("fullstack_resume.pdf", io.BytesIO(fake_pdf), "application/pdf")},
    )
    assert cv1_resp.status_code == 200
    cv1 = cv1_resp.json()
    assert cv1["cv_name"] == "Full Stack Dev CV"
    assert cv1["cv_type"] == "Software Developer"
    assert cv1["file_name"] == "fullstack_resume.pdf"
    assert cv1["id"] is not None

    # 4. Upload second CV (Data Science)
    cv2_resp = client.post(
        "/api/v1/profile/resumes",
        headers=headers,
        data={"cv_name": "Data Scientist CV", "cv_type": "Data Science"},
        files={"file": ("datascience_resume.pdf", io.BytesIO(fake_pdf), "application/pdf")},
    )
    assert cv2_resp.status_code == 200
    cv2 = cv2_resp.json()
    assert cv2["cv_name"] == "Data Scientist CV"
    assert cv2["cv_type"] == "Data Science"

    # 5. List resumes
    list_resp = client.get("/api/v1/profile/resumes", headers=headers)
    assert list_resp.status_code == 200
    resumes = list_resp.json()
    assert len(resumes) >= 2
    assert any(r["id"] == cv1["id"] for r in resumes)
    assert any(r["id"] == cv2["id"] for r in resumes)

    # 6. Verify included in /profile/me
    me_resp = client.get("/api/v1/profile/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["resumes"] is not None
    assert len(me_resp.json()["resumes"]) >= 2

    # 7. Start an assessment session to enable interview question generation
    session_resp = client.post("/api/v1/session/start", headers=headers)
    assert session_resp.status_code in (200, 201)

    # 8. Use profile resume cv1 for interview question generation
    use_resp = client.post(
        f"/api/v1/interview/resume/use-profile-resume/{cv1['id']}",
        headers=headers,
    )
    assert use_resp.status_code == 200
    use_data = use_resp.json()
    assert use_data["status"] == "pool_generated"
    assert use_data["pool_id"] is not None
    assert use_data["question_count"] > 0

    # 9. Delete CV2
    del_resp = client.delete(f"/api/v1/profile/resumes/{cv2['id']}", headers=headers)
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted_id"] == cv2["id"]

    # 10. Verify CV2 is removed from list
    list_after = client.get("/api/v1/profile/resumes", headers=headers).json()
    assert not any(r["id"] == cv2["id"] for r in list_after)
