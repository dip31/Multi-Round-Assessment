"""
FastAPI router for EDI5 Identity, Registration & Role Profiles.
"""

import os
import uuid
from datetime import date, datetime, time, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import and_, case, func, or_

from app.core.auth import get_current_user, get_current_user_from_token_str
from app.database.db import get_db
from app.models.user import User
from app.models.profile import UserResume, StudentProfile, TPOProfile
from app.models.assessment import AssessmentSession, AssessmentRound
from app.models.aptitude import AptitudeAttempt
from app.models.coding import CodingSubmission
from app.models.interview import InterviewSession, InterviewTurn
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
from app.services.faculty_access_service import get_faculty_department, require_faculty_student_access
from app.services.faculty_practice_assessment_service import (
    get_faculty_practice_participation_trend,
    get_practice_round_detail,
    get_practice_student_report,
    list_practice_assessment_activity,
)
from app.services.faculty_dashboard_analytics_service import (
    get_faculty_improvement_summary,
    get_faculty_improvement_trend,
)

RESUMES_UPLOAD_DIR = os.path.join(os.getcwd(), "uploads", "resumes")
os.makedirs(RESUMES_UPLOAD_DIR, exist_ok=True)

router = APIRouter(prefix="/profile", tags=["EDI5 Identity & Role Profiles"])


@router.get("/cohort/department-distribution", summary="Aggregate students by authorized institution scope")
def get_cohort_department_distribution(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return department counts only to institution-level reporting roles."""
    if current_user.role not in ("tpo", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Institution-wide department statistics require TPO or admin privileges.",
        )

    institution = None
    if current_user.role == "tpo":
        tpo_profile = db.query(TPOProfile).filter(TPOProfile.user_id == current_user.id).first()
        institution = tpo_profile.institution.strip() if tpo_profile and tpo_profile.institution else ""
        if not institution:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="An institution must be assigned to the TPO profile for this report.",
            )

    department_value = func.trim(func.coalesce(StudentProfile.department, ""))
    department_label = case(
        (
            func.lower(department_value).in_(
                ("", "unassigned", "unspecified", "unknown", "department not specified")
            ),
            "Department Not Specified",
        ),
        else_=department_value,
    )
    base_query = db.query(User.id).outerjoin(
        StudentProfile, StudentProfile.user_id == User.id
    ).filter(User.role == "student")
    if institution is not None:
        base_query = base_query.filter(
            func.lower(func.trim(StudentProfile.institution)) == institution.casefold()
        )

    total_students = base_query.with_entities(func.count(func.distinct(User.id))).scalar() or 0
    grouped_query = db.query(
        func.min(department_label).label("department"),
        func.count(func.distinct(User.id)).label("student_count"),
    ).select_from(User).outerjoin(StudentProfile, StudentProfile.user_id == User.id).filter(
        User.role == "student"
    )
    if institution is not None:
        grouped_query = grouped_query.filter(
            func.lower(func.trim(StudentProfile.institution)) == institution.casefold()
        )
    rows = grouped_query.group_by(func.lower(department_label)).order_by(
        func.count(func.distinct(User.id)).desc(), func.min(department_label).asc()
    ).all()

    return {
        "scope": "institution" if institution is not None else "all_institutions",
        "institution": institution,
        "total_students": int(total_students),
        "departments": [
            {"department": row.department, "count": int(row.student_count)}
            for row in rows
        ],
    }


@router.get("/cohort/improvement", summary="Faculty-scoped comparable assessment improvement")
def get_cohort_improvement(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aggregate readiness improvement without exposing candidate identities."""
    if current_user.role != "faculty":
        raise HTTPException(status_code=403, detail="Faculty access is required.")
    department = get_faculty_department(db, current_user)
    return get_faculty_improvement_summary(db, department)


@router.get("/cohort/improvement-trend", summary="Faculty-scoped comparable assessment score trend")
def get_cohort_improvement_trend(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return aggregate matched-cohort history without candidate identities."""
    if current_user.role != "faculty":
        raise HTTPException(status_code=403, detail="Faculty access is required.")
    department = get_faculty_department(db, current_user)
    return get_faculty_improvement_trend(db, department)


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
    if current_user.role == "faculty" and payload.department is not None:
        assigned_department = get_faculty_department(db, current_user)
        if payload.department.strip().casefold() != assigned_department.casefold():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Faculty department assignments can only be changed by an authorized administrator.",
            )
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
    department: str | None = Query(default=None),
    student_id: int | None = Query(default=None, ge=1),
    page: int | None = Query(default=None, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    search: str | None = Query(default=None, max_length=120),
    session_status_filter: str | None = Query(default=None, alias="status"),
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

    # Authorization policy: faculty are scoped to the department on their
    # authenticated FacultyProfile. A query parameter can narrow that scope,
    # but cannot select another department. TPO/admin may request a department
    # or omit it for institution-wide access.
    target_dept = department
    if current_user.role == "faculty":
        faculty_department = get_faculty_department(db, current_user)
        if department and department.strip().casefold() != faculty_department.casefold():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Faculty access is limited to the department in the faculty profile.",
            )
        target_dept = faculty_department

    if session_status_filter not in (None, "all", "completed", "in_progress", "not_started"):
        raise HTTPException(status_code=400, detail="Unsupported cohort status filter.")

    latest_session_ranked = db.query(
        AssessmentSession.id.label("session_id"),
        AssessmentSession.user_id.label("user_id"),
        AssessmentSession.status.label("status"),
        func.row_number().over(
            partition_by=AssessmentSession.user_id,
            order_by=(AssessmentSession.started_at.desc(), AssessmentSession.id.desc()),
        ).label("session_rank"),
    ).subquery()
    latest_session_ids_for_filter = (
        db.query(latest_session_ranked.c.session_id)
        .filter(latest_session_ranked.c.session_rank == 1)
        .subquery()
    )
    latest_status = db.query(
        latest_session_ranked.c.user_id,
        latest_session_ranked.c.status,
    ).filter(latest_session_ranked.c.session_rank == 1).subquery()
    scope_query = db.query(User).filter(User.role == "student")
    if target_dept:
        scope_query = scope_query.join(
            StudentProfile, StudentProfile.user_id == User.id
        ).filter(func.lower(StudentProfile.department) == target_dept.strip().lower())
    authorized_total = scope_query.with_entities(func.count(func.distinct(User.id))).scalar() or 0

    query = db.query(User).filter(User.role == "student").outerjoin(
        latest_status, latest_status.c.user_id == User.id
    )
    if student_id is not None:
        query = query.filter(User.id == student_id)
    if target_dept:
        # An explicit department scope excludes students whose profile or
        # department is missing; they must not bleed into every department.
        query = query.join(StudentProfile, StudentProfile.user_id == User.id).filter(
            func.lower(StudentProfile.department) == target_dept.strip().lower()
        )
    if search and search.strip():
        needle = f"%{search.strip().lower()}%"
        query = query.filter(
            func.lower(User.name).like(needle)
            | User.student_profile.has(
                func.lower(func.coalesce(StudentProfile.roll_number, "")).like(needle)
                | func.lower(func.coalesce(StudentProfile.target_role, "")).like(needle)
            )
        )
    if session_status_filter and session_status_filter != "all":
        if session_status_filter == "not_started":
            query = query.filter(
                (latest_status.c.status == "not_started") | (latest_status.c.status.is_(None))
            )
        else:
            if session_status_filter == "in_progress":
                query = query.filter(latest_status.c.status.in_(("in_progress", "active")))
            else:
                query = query.filter(latest_status.c.status == session_status_filter)
    query = query.options(
        selectinload(User.student_profile),
        selectinload(User.assessment_sessions).selectinload(AssessmentSession.rounds),
        selectinload(User.assessment_sessions).selectinload(AssessmentSession.context),
    ).order_by(User.id.asc())
    total = query.order_by(None).count()
    if page is not None:
        query = query.offset((page - 1) * page_size).limit(page_size)
    students = query.all()

    latest_sessions_by_user = {
        student.id: max(
            student.assessment_sessions,
            key=lambda item: (item.started_at or datetime.min, item.id),
            default=None,
        )
        for student in students
    }
    selected_sessions = [session for session in latest_sessions_by_user.values() if session]
    selected_rounds = [round_item for session in selected_sessions for round_item in session.rounds]
    selected_round_ids = [round_item.id for round_item in selected_rounds]
    aptitude_evidence = {}
    coding_evidence = {}
    interview_average_scores = {}
    if selected_round_ids:
        aptitude_evidence = {
            row[0]: {"total": int(row[1] or 0), "evaluated": int(row[2] or 0), "correct": int(row[3] or 0)}
            for row in db.query(
                AptitudeAttempt.round_id,
                func.count(AptitudeAttempt.id),
                func.count(AptitudeAttempt.is_correct),
                func.sum(case((AptitudeAttempt.is_correct.is_(True), 1), else_=0)),
            )
            .filter(
                AptitudeAttempt.round_id.in_(selected_round_ids),
            )
            .group_by(AptitudeAttempt.round_id)
            .all()
        }
        coding_evidence = dict(
            db.query(CodingSubmission.round_id, func.count(CodingSubmission.id))
            .filter(
                CodingSubmission.round_id.in_(selected_round_ids),
                CodingSubmission.score.is_not(None),
                CodingSubmission.status.is_not(None),
                CodingSubmission.status.notin_(("internal_error", "running")),
            )
            .group_by(CodingSubmission.round_id)
            .all()
        )
        interview_session_ids = [session.id for session in selected_sessions]
        interview_rows = db.query(
            InterviewSession.id, InterviewSession.session_id
        ).filter(InterviewSession.session_id.in_(interview_session_ids)).all()
        interview_ids = [row.id for row in interview_rows]
        if interview_ids:
            interview_average_scores = dict(
                db.query(InterviewSession.session_id, func.avg(InterviewTurn.final_score))
                .join(InterviewTurn, InterviewTurn.interview_id == InterviewSession.id)
                .filter(
                    InterviewSession.id.in_(interview_ids),
                    InterviewTurn.is_followup.is_(False),
                    InterviewTurn.final_score.is_not(None),
                )
                .group_by(InterviewSession.session_id)
                .all()
            )

    def faculty_round_score(round_item, assessment_session):
        if round_item.status != "completed":
            return None
        round_type = (round_item.round_type or "").lower()
        if round_type in {"aptitude", "mcq", "combined", "technical"}:
            evidence = aptitude_evidence.get(round_item.id, {})
            has_result = evidence.get("total", 0) > 0 and evidence.get("evaluated", 0) == evidence.get("total", 0)
        elif round_type == "coding":
            has_result = coding_evidence.get(round_item.id, 0) > 0
        elif round_type in {"interview", "technical_interview", "hr_interview", "communication_interview"}:
            interview_score = interview_average_scores.get(assessment_session.id)
            has_result = interview_score is not None
        else:
            has_result = False
        if not has_result:
            return None
        if round_type in {"aptitude", "mcq", "combined", "technical"}:
            # The Aptitude engine's persisted rule is correct evaluated answers
            # divided by attempted answers, expressed as a percentage. Derive
            # from the source rows so a stale/default AssessmentRound.score is
            # never mistaken for evaluated evidence.
            evidence = aptitude_evidence[round_item.id]
            return round((evidence["correct"] / evidence["total"]) * 100, 1)
        if round_type in {"interview", "technical_interview", "hr_interview", "communication_interview"}:
            return float(interview_score)
        return round_item.score

    results = []
    for s in students:
        sp = s.student_profile
        if target_dept and sp and sp.department and sp.department.lower() != target_dept.lower():
            continue

        latest_session = latest_sessions_by_user[s.id]

        rounds_info = {
            "aptitude": {"status": "pending", "score": None},
            "coding": {"status": "pending", "score": None},
            "interview": {"status": "pending", "score": None},
        }
        round_records = []

        session_status = "not_started"
        overall_score = None
        if latest_session:
            session_status = latest_session.status
            if current_user.role != "faculty" and latest_session.status == "completed" and any(
                round_item.status == "completed" for round_item in latest_session.rounds
            ):
                overall_score = latest_session.total_score
            for r in latest_session.rounds:
                aptitude_result = aptitude_evidence.get(r.id, {})
                record = {
                    "round_type": r.round_type,
                    "status": r.status,
                    "score": faculty_round_score(r, latest_session) if current_user.role == "faculty" else (r.score if r.status == "completed" else None),
                    "started_at": r.started_at.isoformat() if r.started_at else None,
                    "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                }
                if current_user.role == "faculty":
                    round_type = (r.round_type or "").lower()
                    record["score_max"] = 100 if round_type in {"aptitude", "mcq", "combined", "technical"} else 1 if round_type in {"coding", "interview", "technical_interview", "hr_interview", "communication_interview"} else None
                    record["evaluation_evidence"] = (
                        {"evaluated": aptitude_result.get("evaluated", 0), "total": aptitude_result.get("total", 0), "correct": aptitude_result.get("correct", 0)}
                        if round_type in {"aptitude", "mcq", "combined", "technical"}
                        else None
                    )
                round_records.append(record)
                if r.round_type in rounds_info:
                    rounds_info[r.round_type] = {
                        "status": r.status,
                        "score": faculty_round_score(r, latest_session) if current_user.role == "faculty" else (r.score if r.status == "completed" else None),
                    }

        result = {
            "user_id": s.id,
            "name": s.name,
            "full_name": (sp.full_name if sp and sp.full_name else s.name),
            "roll_number": sp.roll_number if sp else None,
            "department": sp.department if sp else None,
            "cgpa": sp.cgpa if sp else None,
            "graduation_year": sp.graduation_year if sp else None,
            "backlogs_count": sp.backlogs_count if sp else None,
            "target_role": sp.target_role if sp else None,
            "overall_score": round(overall_score, 2) if overall_score is not None else None,
            "session_status": session_status,
            "session_started_at": latest_session.started_at.isoformat() if latest_session and latest_session.started_at else None,
            "session_completed_at": latest_session.completed_at.isoformat() if latest_session and latest_session.completed_at else None,
            "rounds": rounds_info,
            "round_records": round_records,
        }
        if current_user.role == "faculty":
            # Competency scoring is supported only for a session with its
            # pinned Mock Drive blueprint snapshot. Practice/legacy sessions
            # have no safe competency interpretation.
            context = latest_session.context if latest_session else None
            if latest_session and context and context.mode == "mock_drive":
                from app.services.competency_scoring_service import score_session_competencies
                score = score_session_competencies(db, latest_session)
                result["competency_result"] = {
                    "status": score["overall_score_status"],
                    "evidence_coverage": score["evidence_coverage"],
                    "assessed_competency_count": score["assessed_competency_count"],
                    "required_competency_count": score["required_competency_count"],
                    "competencies": [
                        {
                            "name": competency["competency_name"],
                            "score": competency["normalized_score"],
                            "status": competency["status"],
                            "evidence_count": competency["evidence_count"],
                        }
                        for competency in score["competencies"]
                    ],
                }
            else:
                result["competency_result"] = {
                    "status": "unavailable",
                    "reason": "No latest session with a pinned Mock Drive blueprint is available.",
                    "competencies": [],
                }
        else:
            # Existing TPO/admin consumers rely on these fields. Faculty roster
            # responses intentionally contain only mentoring-relevant data.
            result["email"] = s.email
            result["skills"] = sp.skills_json if (sp and isinstance(sp.skills_json, list)) else []
            result["mobile_no"] = (sp.mobile_no or sp.phone_number) if sp else None
            result["college_email_id"] = sp.college_email_id if sp else None
            result["gender"] = sp.gender if sp else None
            result["date_of_birth"] = sp.date_of_birth if sp else None
            result["nationality"] = sp.nationality if sp else None
            result["tenth_marks"] = sp.tenth_marks if sp else None
            result["twelfth_marks"] = sp.twelfth_marks if sp else None
            result["session_id"] = latest_session.id if latest_session else None
            result["session_time_remaining_seconds"] = (
                latest_session.time_remaining_seconds if latest_session else None
            )
        results.append(result)

    # Values cover the whole authorized cohort, regardless of the requested
    # page. An assessed student has a completed latest session with at least
    # one completed round; evaluation availability is not part of this
    # completion definition.
    latest_session_ids = (
        db.query(latest_session_ranked.c.session_id)
        .join(User, User.id == latest_session_ranked.c.user_id)
        .filter(
            User.role == "student",
            latest_session_ranked.c.session_rank == 1,
        )
    )
    if target_dept:
        latest_session_ids = latest_session_ids.join(
            StudentProfile, StudentProfile.user_id == User.id
        ).filter(func.lower(StudentProfile.department) == target_dept.strip().lower())
    latest_session_ids = latest_session_ids.subquery()
    eligible_count = (
        db.query(func.count(AssessmentSession.id))
        .join(latest_session_ids, latest_session_ids.c.session_id == AssessmentSession.id)
        .filter(
            AssessmentSession.status == "completed",
            AssessmentSession.rounds.any(AssessmentRound.status == "completed"),
        )
        .scalar()
    )
    cohort_summary = {
        "authorized_students": authorized_total,
        "assessed_students": int(eligible_count or 0),
        "latest_attempt_completion_rate": round(eligible_count / authorized_total * 100, 1) if authorized_total and eligible_count is not None else None,
        "average_score": None,
        "average_score_status": "unavailable",
        "average_score_reason": "Score scales have not been verified as comparable across the latest session types.",
    }

    return {
        "total": total,
        "page": page,
        "page_size": page_size if page is not None else None,
        "pages": ((total + page_size - 1) // page_size) if page is not None else 1,
        "department_filter": target_dept,
        "summary": cohort_summary,
        "students": results,
    }


@router.get("/cohort/assessment-activity", summary="List authorized assessment rounds for faculty monitoring")
def get_cohort_assessment_activity(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=120),
    assessment_type: str | None = Query(default=None),
    session_id: int | None = Query(default=None, ge=1),
    round_type: str | None = Query(default=None),
    evaluation_status: str | None = Query(default=None),
    mock_drive_id: int | None = Query(default=None, ge=1),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    needs_attention: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return actual round activity, scoped to the authenticated faculty department."""
    if current_user.role != "faculty":
        raise HTTPException(status_code=403, detail="Faculty access is required.")
    department = get_faculty_department(db, current_user)
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=400, detail="The start date must be on or before the end date.")

    sessions = (
        db.query(AssessmentSession)
        .join(User, User.id == AssessmentSession.user_id)
        .join(StudentProfile, StudentProfile.user_id == User.id)
        .options(
            selectinload(AssessmentSession.user).selectinload(User.student_profile),
            selectinload(AssessmentSession.context),
            selectinload(AssessmentSession.rounds),
        )
        .filter(
            User.role == "student",
            func.lower(StudentProfile.department) == department.casefold(),
        )
        .order_by(AssessmentSession.id.desc())
        .all()
    )
    session_by_id = {session.id: session for session in sessions}
    rounds = [round_item for session in sessions for round_item in session.rounds]
    round_ids = [round_item.id for round_item in rounds]
    session_ids = list(session_by_id)

    aptitude_rows = db.query(
        AptitudeAttempt.round_id,
        func.count(AptitudeAttempt.id),
        func.sum(case((AptitudeAttempt.is_correct.is_(True), 1), else_=0)),
        func.max(AptitudeAttempt.attempted_at),
    ).filter(
        AptitudeAttempt.round_id.in_(round_ids),
        AptitudeAttempt.is_correct.is_not(None),
    ).group_by(AptitudeAttempt.round_id).all() if round_ids else []
    aptitude_data = {row[0]: {"count": int(row[1] or 0), "correct": int(row[2] or 0), "last": row[3]} for row in aptitude_rows}

    coding_rows = db.query(
        CodingSubmission.round_id,
        func.count(CodingSubmission.id),
        func.max(CodingSubmission.submitted_at),
        func.sum(case((and_(
            CodingSubmission.score.is_not(None),
            CodingSubmission.status.is_not(None),
            CodingSubmission.status.notin_(("internal_error", "running")),
        ), 1), else_=0)),
        func.sum(case((CodingSubmission.status == "internal_error", 1), else_=0)),
        func.sum(case((CodingSubmission.status == "running", 1), else_=0)),
    ).filter(CodingSubmission.round_id.in_(round_ids)).group_by(CodingSubmission.round_id).all() if round_ids else []
    coding_data = {row[0]: {"count": int(row[1] or 0), "last": row[2], "evaluated": int(row[3] or 0), "failed": bool(row[4]), "evaluating": bool(row[5])} for row in coding_rows}
    coding_submissions = db.query(
        CodingSubmission.round_id,
        CodingSubmission.status,
        CodingSubmission.score,
        CodingSubmission.submitted_at,
    ).filter(CodingSubmission.round_id.in_(round_ids)).order_by(
        CodingSubmission.submitted_at.asc(), CodingSubmission.id.asc()
    ).all() if round_ids else []
    coding_details_by_round = {}
    for submission in coding_submissions:
        coding_details_by_round.setdefault(submission.round_id, []).append({
            "status": submission.status or "unavailable",
            "score": submission.score if submission.status not in (None, "internal_error", "running") else None,
            "submitted_at": submission.submitted_at.isoformat() if submission.submitted_at else None,
        })

    interview_rows = db.query(
        InterviewSession.session_id,
        InterviewSession.phase,
        func.count(InterviewTurn.id),
        func.count(InterviewTurn.final_score),
        func.max(InterviewTurn.created_at),
        func.avg(InterviewTurn.final_score),
    ).join(InterviewTurn, InterviewTurn.interview_id == InterviewSession.id).filter(
        InterviewSession.session_id.in_(session_ids),
        InterviewTurn.is_followup.is_(False),
    ).group_by(InterviewSession.session_id, InterviewSession.phase).all() if session_ids else []
    interview_data = {
        (row[0], (row[1] or "").upper()): {
            "count": int(row[2] or 0), "evaluated": int(row[3] or 0), "last": row[4], "score": row[5]
        }
        for row in interview_rows
    }

    rows = []
    for session in sessions:
        student = session.user
        profile = student.student_profile
        context = session.context
        mode = context.mode if context else "unknown"
        assessment_name = (
            context.company_name or "Mock Drive" if mode == "mock_drive" and context else
            "Practice assessment" if mode == "practice" else
            "Portfolio assessment" if mode == "portfolio_verification" else
            "Assessment"
        )
        session_name = " - ".join(part for part in [context.company_name, context.target_role] if part) if context and (context.company_name or context.target_role) else ("Assessment session" if session.rounds else "Assessment session")
        for round_item in session.rounds:
            kind = (round_item.round_type or "").lower()
            apt = aptitude_data.get(round_item.id, {})
            coding = coding_data.get(round_item.id, {})
            interview = {}
            if kind in {"interview", "technical_interview", "hr_interview", "communication_interview"}:
                expected_phase = "HR" if kind == "hr_interview" else "TECHNICAL" if kind == "technical_interview" else None
                matching_interviews = [
                    value for (sid, phase), value in interview_data.items()
                    if sid == session.id and (expected_phase is None or phase == expected_phase)
                ]
                if matching_interviews:
                    interview = {
                        "count": sum(item["count"] for item in matching_interviews),
                        "evaluated": sum(item["evaluated"] for item in matching_interviews),
                        "last": max((item["last"] for item in matching_interviews if item["last"]), default=None),
                    }
            if kind in {"aptitude", "mcq", "combined", "technical"}:
                evidence_count = apt.get("count", 0)
                evidence_last = apt.get("last")
                score_scale = "out of 100"
            elif kind == "coding":
                evidence_count = coding.get("evaluated", 0)
                evidence_last = coding.get("last")
                score_scale = "out of 1"
            elif interview:
                evidence_count = interview.get("evaluated", 0)
                evidence_last = interview.get("last")
                score_scale = "out of 1"
            else:
                evidence_count = 0
                evidence_last = None
                score_scale = None
            if round_item.status in ("active", "in_progress"):
                evaluation = "in_progress"
            elif coding.get("evaluating"):
                evaluation = "evaluation_in_progress"
            elif coding.get("failed") and not evidence_count:
                evaluation = "failed"
            elif round_item.status == "completed" and evidence_count:
                evaluation = "completed"
            elif round_item.status == "completed":
                evaluation = "awaiting_evaluation"
            elif round_item.status in ("pending", "not_started"):
                evaluation = "not_started"
            else:
                evaluation = "unavailable"
            score = round_item.score if evidence_count else None
            last_activity = max(
                (value for value in (evidence_last, round_item.completed_at, round_item.started_at, session.completed_at, session.started_at) if value),
                default=None,
            )
            row = {
                "student": {
                    "user_id": student.id,
                    "name": profile.full_name if profile and profile.full_name else student.name,
                    "roll_number": profile.roll_number if profile else None,
                    "department": profile.department if profile else None,
                },
                "assessment_name": assessment_name,
                "assessment_type": mode,
                "session_name": session_name,
                "session_id": session.id,
                "session_status": session.status,
                "session_started_at": session.started_at.isoformat() if session.started_at else None,
                "session_completed_at": session.completed_at.isoformat() if session.completed_at else None,
                "round_id": round_item.id,
                "round_name": kind.replace("_", " ").title() or "Assessment round",
                "round_type": kind,
                "round_status": round_item.status,
                "attempt_count": apt.get("count", 0) if apt else coding.get("count", 0) if coding else evidence_count,
                "attempt_summary": ({"attempted": apt.get("count", 0), "correct": apt.get("correct", 0)} if apt else ({"submissions": coding.get("count", 0)} if coding else ({"evaluated_turns": interview.get("evaluated", 0)} if interview else {}))),
                "submission_details": coding_details_by_round.get(round_item.id, []) if kind == "coding" else [],
                "evaluation_status": evaluation,
                "score": score,
                "score_scale": score_scale if score is not None else None,
                "last_activity": last_activity.isoformat() if last_activity else None,
                "context_id": context.id if context else None,
                "mock_drive_id": context.mock_drive_id if context else None,
            }
            rows.append(row)

    all_rows = rows.copy()
    if search and search.strip():
        needle = search.strip().casefold()
        rows = [row for row in rows if needle in " ".join((row["student"]["name"], row["student"].get("roll_number") or "", row["assessment_name"], row["session_name"], row["round_name"])).casefold()]
    if assessment_type:
        rows = [row for row in rows if row["assessment_type"] == assessment_type]
    if session_id:
        rows = [row for row in rows if row["session_id"] == session_id]
    if mock_drive_id:
        rows = [row for row in rows if row["mock_drive_id"] == mock_drive_id]
    if round_type:
        rows = [row for row in rows if row["round_type"] == round_type]
    if evaluation_status:
        rows = [row for row in rows if row["evaluation_status"] == evaluation_status]
    if needs_attention:
        rows = [row for row in rows if row["evaluation_status"] in {"in_progress", "evaluation_in_progress", "awaiting_evaluation", "failed"}]
    if date_from:
        start_dt = datetime.combine(date_from, time.min)
        rows = [row for row in rows if row["last_activity"] and datetime.fromisoformat(row["last_activity"]) >= start_dt]
    if date_to:
        end_dt = datetime.combine(date_to + timedelta(days=1), time.min)
        rows = [row for row in rows if row["last_activity"] and datetime.fromisoformat(row["last_activity"]) < end_dt]

    rows.sort(key=lambda row: (row["last_activity"] or "", row["session_id"], row["round_id"]), reverse=True)
    total = len(rows)
    session_options = {}
    for row in all_rows:
        session_options[row["session_id"]] = row["session_name"]
    start = (page - 1) * page_size
    return {
        "records": rows[start:start + page_size],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
        "filters": {
            "assessment_types": sorted({row["assessment_type"] for row in all_rows}),
            "sessions": [{"id": key, "name": value} for key, value in session_options.items()],
            "round_types": sorted({row["round_type"] for row in all_rows}),
            "evaluation_statuses": sorted({row["evaluation_status"] for row in all_rows}),
        },
    }


# ── Student Resume Endpoints ──────────────────────────────────────────

@router.get(
    "/cohort/practice-assessment-activity",
    summary="List faculty-authorized Practice Assessment rounds",
)
def get_cohort_practice_assessment_activity(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=120),
    session_id: int | None = Query(default=None, ge=1),
    round_type: str | None = Query(default=None),
    evaluation_status: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    needs_attention: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return practice-mode sessions only, within the current faculty department."""
    return list_practice_assessment_activity(
        db,
        current_user,
        page=page,
        page_size=page_size,
        search=search,
        session_id=session_id,
        round_type=round_type,
        evaluation_status=evaluation_status,
        date_from=date_from,
        date_to=date_to,
        needs_attention=needs_attention,
    )


@router.get(
    "/cohort/practice-assessment-participation",
    summary="Get faculty-scoped weekly Practice session participation",
)
def get_cohort_practice_assessment_participation(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return complete weekly counts for the authenticated faculty scope."""
    return get_faculty_practice_participation_trend(db, current_user)


@router.get(
    "/cohort/practice-assessment-activity/students/{student_id}/report",
    summary="Get an authorized student's Practice Assessment history",
)
def get_cohort_practice_student_report(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_practice_student_report(db, current_user, student_id=student_id)


@router.get(
    "/cohort/practice-assessment-activity/students/{student_id}/sessions/{session_id}/rounds/{round_id}",
    summary="Get one authorized Practice Assessment round detail",
)
def get_cohort_practice_round_detail(
    student_id: int,
    session_id: int,
    round_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_practice_round_detail(
        db,
        current_user,
        student_id=student_id,
        session_id=session_id,
        round_id=round_id,
    )


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

    if resolved_user.role == "faculty" and resume.user_id != resolved_user.id:
        require_faculty_student_access(db, resolved_user, resume.user_id)
    elif resolved_user.role not in ("faculty", "tpo", "admin") and resume.user_id != resolved_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this resume")

    if not resume.file_path or not os.path.exists(resume.file_path):
        raise HTTPException(status_code=404, detail="Resume file not found on disk")

    return FileResponse(
        resume.file_path,
        media_type="application/pdf",
        filename=resume.file_name,
    )
