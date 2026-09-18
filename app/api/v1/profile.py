"""
FastAPI router for EDI5 Identity, Registration & Role Profiles.
"""

import os
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.auth import get_current_user, get_current_user_from_token_str
from app.database.db import get_db
from app.models.user import User
from app.models.profile import UserResume
from app.models.assessment import AssessmentSession, AssessmentRound
from app.schemas.profile import (
    UserProfileResponse,
    StudentProfileUpdate,
    StudentProfileResponse,
    FacultyProfileUpdate,
    FacultyProfileResponse,
    TPOProfileUpdate,
    TPOProfileResponse,
    UserResumeResponse,
)
from app.services.profile_service import ProfileService
from app.services.resume_service import parse_resume

RESUMES_UPLOAD_DIR = os.path.join(os.getcwd(), "uploads", "resumes")
os.makedirs(RESUMES_UPLOAD_DIR, exist_ok=True)

router = APIRouter(prefix="/profile", tags=["EDI5 Identity & Role Profiles"])


@router.get("/me", response_model=UserProfileResponse, summary="Get full profile with role-specific details")
def get_my_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve currently authenticated user details along with their role profile."""
    return ProfileService.get_full_profile(db=db, user=current_user)


# ── Student Profile Endpoints ─────────────────────────────────────────

@router.get("/student/me", response_model=StudentProfileResponse)
def get_my_student_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve authenticated student's academic profile."""
    sp = ProfileService.get_or_create_student_profile(db, current_user.id)
    return ProfileService._to_student_response(sp, default_name=current_user.name)


@router.put("/student/me", response_model=StudentProfileResponse)
def update_my_student_profile(
    payload: StudentProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update authenticated student's academic profile (CGPA, department, graduation year, target role, etc.)."""
    return ProfileService.update_student_profile(db=db, user_id=current_user.id, payload=payload)


# ── Faculty Profile Endpoints ─────────────────────────────────────────

@router.get("/faculty/me", response_model=FacultyProfileResponse)
def get_my_faculty_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve authenticated faculty member's profile."""
    fp = ProfileService.get_or_create_faculty_profile(db, current_user.id)
    return FacultyProfileResponse.model_validate(fp)


@router.put("/faculty/me", response_model=FacultyProfileResponse)
def update_my_faculty_profile(
    payload: FacultyProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update authenticated faculty member's profile."""
    return ProfileService.update_faculty_profile(db=db, user_id=current_user.id, payload=payload)


# ── TPO Profile Endpoints ─────────────────────────────────────────────

@router.get("/tpo/me", response_model=TPOProfileResponse)
def get_my_tpo_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve authenticated TPO officer's profile."""
    tp = ProfileService.get_or_create_tpo_profile(db, current_user.id)
    return TPOProfileResponse.model_validate(tp)


@router.put("/tpo/me", response_model=TPOProfileResponse)
def update_my_tpo_profile(
    payload: TPOProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update authenticated TPO officer's profile."""
    return ProfileService.update_tpo_profile(db=db, user_id=current_user.id, payload=payload)


# ── Staff Cohort Endpoints ───────────────────────────────────────────

@router.get("/cohort/students", summary="List student cohort profiles with assessment status")
def get_cohort_students(
    department: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve students roster with academic profiles and assessment progress.
    Authorized for faculty, tpo, and admin."""
    if current_user.role not in ("faculty", "tpo", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires faculty, TPO, or admin privileges",
        )

    target_dept = department
    if not target_dept and current_user.role == "faculty":
        fp = current_user.faculty_profile
        if fp and fp.department:
            target_dept = fp.department

    query = db.query(User).filter(User.role == "student")
    students = query.all()

    results = []
    for s in students:
        sp = s.student_profile
        if target_dept and sp and sp.department and sp.department.lower() != target_dept.lower():
            continue

        latest_session = (
            db.query(AssessmentSession)
            .filter(AssessmentSession.user_id == s.id)
            .order_by(AssessmentSession.id.desc())
            .first()
        )

        rounds_info = {
            "aptitude": {"status": "pending", "score": None},
            "coding": {"status": "pending", "score": None},
            "interview": {"status": "pending", "score": None},
        }

        session_status = "not_started"
        overall_score = 0.0
        if latest_session:
            session_status = latest_session.status
            overall_score = latest_session.total_score or 0.0
            for r in latest_session.rounds:
                if r.round_type in rounds_info:
                    rounds_info[r.round_type] = {
                        "status": r.status,
                        "score": r.score,
                    }

        results.append({
            "user_id": s.id,
            "name": s.name,
            "full_name": (sp.full_name if sp and sp.full_name else s.name),
            "email": s.email,
            "roll_number": sp.roll_number if sp else None,
            "department": sp.department if sp else "General",
            "cgpa": sp.cgpa if sp else 7.5,
            "graduation_year": sp.graduation_year if sp else 2026,
            "backlogs_count": sp.backlogs_count if sp else 0,
            "target_role": sp.target_role if sp else "Software Engineer",
            "skills": sp.skills_json if (sp and isinstance(sp.skills_json, list)) else [],
            "mobile_no": (sp.mobile_no or sp.phone_number) if sp else None,
            "college_email_id": sp.college_email_id if sp else None,
            "gender": sp.gender if sp else None,
            "date_of_birth": sp.date_of_birth if sp else None,
            "nationality": sp.nationality if sp else "Indian",
            "tenth_marks": sp.tenth_marks if sp else None,
            "twelfth_marks": sp.twelfth_marks if sp else None,
            "overall_score": round(overall_score, 2),
            "session_status": session_status,
            "rounds": rounds_info,
        })

    return {
        "total": len(results),
        "department_filter": target_dept,
        "students": results,
    }


# ── Student Resume Endpoints ──────────────────────────────────────────

@router.post("/resumes", response_model=UserResumeResponse, summary="Upload a resume to student profile")
async def upload_student_resume(
    file: UploadFile = File(...),
    cv_name: str = Form("My Resume"),
    cv_type: str = Form("Software Developer"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a resume/CV for student with CV name and category."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a valid PDF document",
        )

    content = await file.read()
    file_size = len(content)

    if file_size > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds 10MB limit",
        )

    unique_name = f"{current_user.id}_{uuid.uuid4().hex[:8]}_{file.filename}"
    file_path = os.path.join(RESUMES_UPLOAD_DIR, unique_name)
    with open(file_path, "wb") as f:
        f.write(content)

    extracted = parse_resume(content)
    parsed_skills = extracted.get("skills", [])
    parsed_projects = extracted.get("projects", [])
    full_content = extracted.get("full_content", "")

    resume_record = UserResume(
        user_id=current_user.id,
        cv_name=cv_name.strip() or "My Resume",
        cv_type=cv_type.strip() or "Software Developer",
        file_name=file.filename,
        file_path=file_path,
        file_size=file_size,
        resume_text=full_content,
        parsed_skills=parsed_skills,
        parsed_projects=parsed_projects,
    )
    db.add(resume_record)
    db.commit()
    db.refresh(resume_record)

    return UserResumeResponse.model_validate(resume_record)


@router.get("/resumes", response_model=list[UserResumeResponse], summary="List all resumes uploaded by user")
def list_my_resumes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List resumes uploaded by current student."""
    resumes = (
        db.query(UserResume)
        .filter(UserResume.user_id == current_user.id)
        .order_by(UserResume.id.desc())
        .all()
    )
    return [UserResumeResponse.model_validate(r) for r in resumes]


@router.delete("/resumes/{resume_id}", summary="Delete an uploaded resume")
def delete_student_resume(
    resume_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a resume uploaded by the current student."""
    resume = (
        db.query(UserResume)
        .filter(UserResume.id == resume_id, UserResume.user_id == current_user.id)
        .first()
    )
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found",
        )

    if resume.file_path and os.path.exists(resume.file_path):
        try:
            os.remove(resume.file_path)
        except Exception:
            pass

    db.delete(resume)
    db.commit()
    return {"detail": "Resume deleted successfully", "deleted_id": resume_id}


resume_bearer_scheme = HTTPBearer(auto_error=False)


@router.get("/resumes/{resume_id}/file", summary="Download or view resume file")
def get_resume_file(
    resume_id: int,
    token: Optional[str] = Query(None, description="Access token for direct PDF viewing in browser"),
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(resume_bearer_scheme),
):
    """Download or view resume PDF for authenticated user."""
    resolved_user: Optional[User] = None
    if credentials and credentials.credentials:
        resolved_user = get_current_user_from_token_str(credentials.credentials, db)
    elif token:
        resolved_user = get_current_user_from_token_str(token, db)

    if not resolved_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to view resume file",
        )

    resume = (
        db.query(UserResume)
        .filter(UserResume.id == resume_id)
        .first()
    )
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    if resolved_user.role not in ("faculty", "tpo", "admin") and resume.user_id != resolved_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this resume")

    if not resume.file_path or not os.path.exists(resume.file_path):
        raise HTTPException(status_code=404, detail="Resume file not found on disk")

    return FileResponse(
        resume.file_path,
        media_type="application/pdf",
        filename=resume.file_name,
    )
