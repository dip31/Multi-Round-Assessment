"""Persistence and authorization for faculty-created practice assignments."""

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.aptitude import AptitudeAttempt
from app.models.assessment import AssessmentRound, AssessmentSession
from app.models.assessment_context import AssessmentContext
from app.models.coding import CodingSubmission
from app.models.faculty_practice_assessment import (
    FacultyPracticeAssessment,
    FacultyPracticeAssessmentRound,
    FacultyPracticeAssignment,
    FacultyPracticeRoundAttempt,
)
from app.models.interview import InterviewSession, InterviewTurn
from app.models.profile import StudentProfile
from app.models.session_problem import SessionProblem
from app.models.user import User
from app.services.faculty_access_service import get_faculty_department

ROUND_TYPES = {"aptitude", "coding", "interview"}
APTITUDE_TYPES = {"mcq", "technical", "combined"}


def finalize_faculty_assigned_attempt(db: Session, user_id: int, round_id: int) -> bool:
    """Close the one-round engine session after its assigned round is finalized.

    The existing assessment engines own submission and evaluation. This helper
    only closes their enclosing session when the completed round is linked to a
    faculty assignment, allowing the next configured round to start in a fresh
    session. Independent practice and Mock Drive sessions are left untouched.
    """
    link = db.query(FacultyPracticeRoundAttempt).filter_by(round_id=round_id).first()
    if link is None:
        return False

    session = db.query(AssessmentSession).filter_by(
        id=link.session_id, user_id=user_id
    ).first()
    engine_round = db.query(AssessmentRound).filter_by(
        id=round_id, session_id=link.session_id, status="completed"
    ).first()
    if session is None or engine_round is None:
        return False
    context = db.query(AssessmentContext).filter_by(id=session.context_id).first()
    if context is None or context.purpose != f"faculty_assignment:{link.assignment_id}":
        return False

    # A linked attempt must not close a session that still has another active
    # engine round. This preserves the existing active-attempt protection.
    active_round = db.query(AssessmentRound).filter_by(
        session_id=session.id, status="active"
    ).first()
    if active_round is not None:
        return False

    if session.status == "in_progress":
        session.total_score = float(
            db.query(func.avg(AssessmentRound.score)).filter_by(
                session_id=session.id, status="completed"
            ).scalar() or 0.0
        )
        db.commit()
        from app.services.session_service import complete_session

        complete_session(db, session.id, user_id)
    elif session.status != "completed":
        return False

    from app.services.assessment_context_service import complete_context

    complete_context(db, context.id)
    return True


def finalize_faculty_assigned_session(db: Session, user_id: int, session_id: int) -> bool:
    """Retry assigned-session finalization after the engine already completed."""
    completed_link = db.query(FacultyPracticeRoundAttempt).join(
        AssessmentRound, AssessmentRound.id == FacultyPracticeRoundAttempt.round_id
    ).filter(
        FacultyPracticeRoundAttempt.session_id == session_id,
        AssessmentRound.status == "completed",
    ).first()
    if completed_link is None:
        return False
    return finalize_faculty_assigned_attempt(db, user_id, completed_link.round_id)


def require_role(user: User, role: str) -> None:
    if user.role != role:
        raise HTTPException(status_code=403, detail=f"{role.capitalize()} access required.")


def create_assessment(db: Session, faculty: User, payload: dict, request_key: str | None = None) -> dict:
    require_role(faculty, "faculty")
    title = (payload.get("title") or "").strip()
    rounds = payload.get("rounds") or []
    student_ids = list(dict.fromkeys(payload.get("student_ids") or []))
    start = payload.get("availability_start")
    end = payload.get("availability_end")
    if not title:
        raise HTTPException(422, "Assessment title is required.")
    if not rounds or len(rounds) > 10:
        raise HTTPException(422, "Add between one and ten assessment rounds.")
    if not student_ids:
        raise HTTPException(422, "Select at least one authorized student.")
    if request_key:
        existing = db.query(FacultyPracticeAssessment).filter_by(faculty_id=faculty.id, request_key=request_key).first()
        if existing:
            return serialize_assessment(db, existing, include_students=True)
    if start and end and end <= start:
        raise HTTPException(422, "Availability end must be later than its start.")
    for item in rounds:
        kind = item.get("round_type")
        practice_type = item.get("practice_type")
        if kind not in ROUND_TYPES:
            raise HTTPException(422, "Unsupported assessment round type.")
        if kind == "aptitude" and practice_type not in APTITUDE_TYPES:
            raise HTTPException(422, "Choose a supported aptitude practice type.")
        if kind == "coding" and practice_type not in (None, "coding"):
            raise HTTPException(422, "Coding rounds use the existing coding practice configuration.")
        if kind == "interview" and practice_type not in (None, "interview"):
            raise HTTPException(422, "Interview rounds use the existing interview practice configuration.")
    department = get_faculty_department(db, faculty)
    authorized_ids = {
        row[0] for row in db.query(User.id).join(
            StudentProfile, StudentProfile.user_id == User.id
        ).filter(
            User.role == "student",
            User.id.in_(student_ids),
            func.lower(StudentProfile.department) == department.lower(),
        ).all()
    }
    if authorized_ids != set(student_ids):
        raise HTTPException(404, detail="One or more selected students are outside your authorized faculty scope.")
    try:
        assessment = FacultyPracticeAssessment(
            faculty_id=faculty.id,
            request_key=request_key,
            title=title,
            description=(payload.get("description") or "").strip() or None,
            instructions=(payload.get("instructions") or "").strip() or None,
            availability_start=start,
            availability_end=end,
        )
        db.add(assessment)
        db.flush()
        for sequence, item in enumerate(rounds, start=1):
            kind = item["round_type"]
            db.add(FacultyPracticeAssessmentRound(
                assessment_id=assessment.id,
                round_type=kind,
                sequence=sequence,
                configuration={"practice_type": item.get("practice_type") or kind},
            ))
        db.add_all([
            FacultyPracticeAssignment(assessment_id=assessment.id, student_id=student_id)
            for student_id in student_ids
        ])
        db.commit()
        db.refresh(assessment)
        return serialize_assessment(db, assessment, include_students=True)
    except Exception:
        db.rollback()
        raise


def _evaluation(db: Session, attempt: FacultyPracticeRoundAttempt | None, round_def: FacultyPracticeAssessmentRound) -> tuple[str, float | None, dict]:
    if attempt is None:
        return "not_started", None, {}
    engine_round = db.query(AssessmentRound).filter_by(id=attempt.round_id, session_id=attempt.session_id).first()
    if engine_round is None:
        return "unavailable", None, {}
    if engine_round.status in {"active", "in_progress", "pending"}:
        return "in_progress", None, {"engine_round_id": engine_round.id, "session_id": attempt.session_id}
    if engine_round.status != "completed":
        return "failed", None, {"engine_round_id": engine_round.id, "session_id": attempt.session_id}

    kind = round_def.round_type
    detail = {"engine_round_id": engine_round.id, "session_id": attempt.session_id}
    if kind == "aptitude":
        rows = db.query(AptitudeAttempt).filter(AptitudeAttempt.round_id == engine_round.id).all()
        evaluated = [row for row in rows if row.is_correct is not None]
        if not evaluated:
            return ("evaluation_pending" if rows else "attempt_completed"), None, detail
        if len(evaluated) != len(rows):
            return "evaluation_pending", None, detail
        score = sum(1 for row in evaluated if row.is_correct is True)
        detail.update({"correct": score, "evaluated_questions": len(evaluated)})
        return "evaluated", float(score), detail
    if kind == "coding":
        submissions = db.query(CodingSubmission).filter(CodingSubmission.round_id == engine_round.id).all()
        assigned_problem_ids = [row[0] for row in db.query(SessionProblem.problem_id).filter_by(round_id=engine_round.id).all()]
        if any(row.status == "running" for row in submissions):
            return "evaluation_pending", None, detail
        if any(row.status == "internal_error" for row in submissions):
            return "failed", None, detail
        evaluated = [row for row in submissions if row.score is not None and row.status is not None]
        evaluated_problem_ids = {row.problem_id for row in evaluated}
        if not assigned_problem_ids and not submissions:
            return "attempt_completed", None, detail
        if not assigned_problem_ids or not set(assigned_problem_ids).issubset(evaluated_problem_ids):
            return "evaluation_pending", None, detail
        best_scores = {
            problem_id: max(float(row.score) for row in evaluated if row.problem_id == problem_id)
            for problem_id in assigned_problem_ids
        }
        score = sum(best_scores.values())
        detail.update({"submission_count": len(submissions), "evaluated_submissions": len(evaluated), "score_max": len(assigned_problem_ids)})
        return "evaluated", score, detail
    interviews = db.query(InterviewSession).filter_by(session_id=attempt.session_id).order_by(InterviewSession.id.desc()).all()
    turns = []
    for interview in interviews:
        turns.extend(db.query(InterviewTurn).filter_by(interview_id=interview.id).all())
    evaluated = [turn for turn in turns if turn.candidate_response and turn.final_score is not None]
    if not evaluated:
        has_response = any(turn.candidate_response for turn in turns)
        return ("evaluation_pending" if has_response else "attempt_completed"), None, detail
    score = sum(float(turn.final_score) for turn in evaluated) / len(evaluated)
    detail.update({"evaluated_turns": len(evaluated)})
    return "evaluated", score, detail


def assignment_rounds(db: Session, assignment: FacultyPracticeAssignment) -> list[dict]:
    definitions = db.query(FacultyPracticeAssessmentRound).filter_by(
        assessment_id=assignment.assessment_id
    ).order_by(FacultyPracticeAssessmentRound.sequence).all()
    records = db.query(FacultyPracticeRoundAttempt).filter_by(assignment_id=assignment.id).all()
    attempts = {record.assessment_round_id: record for record in records}
    result = []
    for definition in definitions:
        state, score, evidence = _evaluation(db, attempts.get(definition.id), definition)
        result.append({
            "id": definition.id,
            "round_type": definition.round_type,
            "sequence": definition.sequence,
            "practice_type": (definition.configuration or {}).get("practice_type"),
            "status": state,
            "score": score,
            "evidence": evidence,
        })
    return result


def serialize_assignment(db: Session, assignment: FacultyPracticeAssignment) -> dict:
    assessment = db.query(FacultyPracticeAssessment).filter_by(id=assignment.assessment_id).first()
    rounds = assignment_rounds(db, assignment)
    attempts = {
        record.assessment_round_id: record
        for record in db.query(FacultyPracticeRoundAttempt).filter_by(assignment_id=assignment.id).all()
    }
    current_round = next((item for item in rounds if item["status"] == "in_progress"), None)
    next_round = current_round or next((item for item in rounds if item["status"] == "not_started"), None)
    # Sequential rules: a later round is not available until the previous attempt completes.
    previous_rounds = [item for item in rounds if next_round and item["sequence"] < next_round["sequence"]]
    previous_attempts_finalized = True
    for item in previous_rounds:
        previous_attempt = attempts.get(item["id"])
        previous_session = db.query(AssessmentSession).filter_by(
            id=previous_attempt.session_id if previous_attempt else None,
            user_id=assignment.student_id,
        ).first()
        previous_context = db.query(AssessmentContext).filter_by(
            id=previous_session.context_id if previous_session else None,
        ).first()
        if (
            previous_session is None
            or previous_session.status != "completed"
            or previous_context is None
            or previous_context.status != "completed"
        ):
            previous_attempts_finalized = False
            break
    eligible = (
        next_round
        if next_round
        and previous_attempts_finalized
        and all(item["status"] in {"evaluated", "evaluation_pending", "attempt_completed"} for item in previous_rounds)
        else None
    )
    started_states = {"in_progress", "attempt_completed", "evaluation_pending", "evaluated", "failed"}
    started = [item for item in rounds if item["status"] in started_states]
    if len(started) == 0:
        assignment_status = "not_started"
    elif any(item["status"] == "failed" for item in rounds):
        assignment_status = "failed"
    elif all(item["status"] == "evaluated" for item in rounds):
        assignment_status = "completed"
    elif all(item["status"] in {"evaluated", "evaluation_pending", "attempt_completed"} for item in rounds):
        assignment_status = "evaluation_pending" if any(item["status"] == "evaluation_pending" for item in rounds) else "attempt_completed"
    else:
        assignment_status = "in_progress"
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    available = bool(assessment and assessment.status == "published")
    if assessment and assessment.availability_start and now < assessment.availability_start:
        available = False
    if assessment and assessment.availability_end and now > assessment.availability_end:
        available = False
    return {
        "assignment_id": assignment.id,
        "assessment_id": assessment.id if assessment else None,
        "title": assessment.title if assessment else "Assessment unavailable",
        "description": assessment.description if assessment else None,
        "instructions": assessment.instructions if assessment else None,
        "status": assignment_status,
        "assessment_status": assessment.status if assessment else None,
        "availability_start": assessment.availability_start if assessment else None,
        "availability_end": assessment.availability_end if assessment else None,
        "available": available,
        "rounds": rounds,
        "next_round": eligible if available else None,
        "progress": sum(item["status"] in started_states for item in rounds),
        "completed_rounds": sum(item["status"] in {"evaluated", "evaluation_pending", "attempt_completed"} for item in rounds),
        "round_count": len(rounds),
    }


def serialize_assessment(db: Session, assessment: FacultyPracticeAssessment, include_students: bool = False) -> dict:
    definitions = db.query(FacultyPracticeAssessmentRound).filter_by(
        assessment_id=assessment.id
    ).order_by(FacultyPracticeAssessmentRound.sequence).all()
    assignments = db.query(FacultyPracticeAssignment).filter_by(assessment_id=assessment.id).all()
    owner = db.query(User).filter_by(id=assessment.faculty_id).first()
    if owner and owner.role == "faculty" and assignments:
        department = get_faculty_department(db, owner)
        requested_student_ids = [item.student_id for item in assignments]
        authorized_ids = {
            row[0] for row in db.query(User.id).join(
                StudentProfile, StudentProfile.user_id == User.id
            ).filter(
                User.role == "student",
                User.id.in_(requested_student_ids),
                func.lower(StudentProfile.department) == department.lower(),
            ).all()
        }
        assignments = [item for item in assignments if item.student_id in authorized_ids]
    assignment_ids = [item.id for item in assignments]
    links = db.query(FacultyPracticeRoundAttempt).join(
        FacultyPracticeAssessmentRound,
        FacultyPracticeAssessmentRound.id == FacultyPracticeRoundAttempt.assessment_round_id,
    ).filter(FacultyPracticeRoundAttempt.assignment_id.in_(assignment_ids)).all() if assignment_ids else []
    engine_rounds = db.query(AssessmentRound).filter(
        AssessmentRound.id.in_([item.round_id for item in links])
    ).all() if links else []
    engine_round_by_id = {item.id: item for item in engine_rounds}
    activity_times = [value for item in engine_rounds for value in (item.started_at, item.completed_at) if value]
    progress_by_assignment = {
        assignment.id: assignment_rounds(db, assignment)
        for assignment in assignments
    }
    round_states = [
        round_item["status"]
        for assignment_rounds_list in progress_by_assignment.values()
        for round_item in assignment_rounds_list
    ]
    completed_attempt_states = {"attempt_completed", "evaluation_pending", "evaluated"}
    result = {
        "id": assessment.id,
        "title": assessment.title,
        "description": assessment.description,
        "instructions": assessment.instructions,
        "status": assessment.status,
        "created_at": assessment.created_at,
        "availability_start": assessment.availability_start,
        "availability_end": assessment.availability_end,
        "rounds": [{"id": r.id, "round_type": r.round_type, "sequence": r.sequence,
                    "practice_type": (r.configuration or {}).get("practice_type")} for r in definitions],
        "assigned_students": len(assignments),
        "overall_attempts": len(links),
        "overall_progress": sum(engine_round_by_id.get(item.round_id) is not None and engine_round_by_id[item.round_id].status == "completed" for item in links),
        "rounds_total": len(round_states),
        "rounds_started": sum(state in {"in_progress", "attempt_completed", "evaluation_pending", "evaluated", "failed"} for state in round_states),
        "rounds_attempt_completed": sum(state in completed_attempt_states for state in round_states),
        "rounds_evaluated": sum(state == "evaluated" for state in round_states),
        "rounds_evaluation_pending": sum(state == "evaluation_pending" for state in round_states),
        "rounds_in_progress": sum(state == "in_progress" for state in round_states),
        "rounds_failed": sum(state == "failed" for state in round_states),
        "rounds_unavailable": sum(state == "unavailable" for state in round_states),
        "last_activity": max(activity_times).isoformat() if activity_times else None,
    }
    if include_students:
        students = []
        for assignment in assignments:
            user = db.query(User).filter_by(id=assignment.student_id).first()
            if not user:
                continue
            students.append({
                **serialize_assignment(db, assignment),
                "student": {"id": user.id, "name": user.student_profile.full_name or user.name if user.student_profile else user.name,
                            "roll_number": user.student_profile.roll_number if user.student_profile else None},
            })
        result["students"] = students
    return result


def get_owned_assessment(db: Session, faculty: User, assessment_id: int) -> FacultyPracticeAssessment:
    require_role(faculty, "faculty")
    assessment = db.query(FacultyPracticeAssessment).filter_by(id=assessment_id, faculty_id=faculty.id).first()
    if assessment is None:
        raise HTTPException(404, "Practice assessment not found.")
    return assessment


def get_student_assignment(db: Session, student: User, assignment_id: int) -> FacultyPracticeAssignment:
    require_role(student, "student")
    assignment = db.query(FacultyPracticeAssignment).filter_by(id=assignment_id, student_id=student.id).first()
    if assignment is None:
        raise HTTPException(404, "Assigned practice assessment not found.")
    return assignment


def cancel_assessment(db: Session, faculty: User, assessment_id: int) -> dict:
    assessment = get_owned_assessment(db, faculty, assessment_id)
    assessment.status = "cancelled"
    db.commit()
    db.refresh(assessment)
    # Attempts/results remain linked and readable after cancellation.
    return serialize_assessment(db, assessment, include_students=True)


def validate_assigned_round_start(db: Session, student: User, assignment_id: int, assessment_round_id: int):
    """Authorize and enforce availability/order before reusing the practice engine."""
    assignment = get_student_assignment(db, student, assignment_id)
    assessment = db.query(FacultyPracticeAssessment).filter_by(id=assignment.assessment_id).first()
    if assessment is None or assessment.status != "published":
        raise HTTPException(404, "Assigned practice assessment not found.")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if assessment.availability_start and now < assessment.availability_start:
        raise HTTPException(403, "This assessment is not available yet.")
    if assessment.availability_end and now > assessment.availability_end:
        raise HTTPException(403, "This assessment is no longer available.")
    selected = db.query(FacultyPracticeAssessmentRound).filter_by(
        id=assessment_round_id, assessment_id=assessment.id
    ).first()
    if selected is None:
        raise HTTPException(404, "Assigned assessment round not found.")
    existing = db.query(FacultyPracticeRoundAttempt).filter_by(
        assignment_id=assignment.id, assessment_round_id=selected.id
    ).first()
    if existing:
        session = db.query(AssessmentSession).filter_by(id=existing.session_id, user_id=student.id).first()
        engine_round = db.query(AssessmentRound).filter_by(id=existing.round_id, session_id=existing.session_id).first()
        if session and session.status == "in_progress" and engine_round and engine_round.status == "active":
            return assignment, assessment, selected, existing
        raise HTTPException(409, "This assigned round has already been attempted.")
    previous = db.query(FacultyPracticeAssessmentRound).filter(
        FacultyPracticeAssessmentRound.assessment_id == assessment.id,
        FacultyPracticeAssessmentRound.sequence < selected.sequence,
    ).order_by(FacultyPracticeAssessmentRound.sequence).all()
    for previous_round in previous:
        previous_attempt = db.query(FacultyPracticeRoundAttempt).filter_by(
            assignment_id=assignment.id, assessment_round_id=previous_round.id
        ).first()
        if previous_attempt is None:
            raise HTTPException(409, "Complete the earlier required round before starting this one.")
        previous_engine_round = db.query(AssessmentRound).filter_by(
            id=previous_attempt.round_id, session_id=previous_attempt.session_id
        ).first()
        previous_session = db.query(AssessmentSession).filter_by(
            id=previous_attempt.session_id, user_id=student.id
        ).first()
        previous_context = db.query(AssessmentContext).filter_by(
            id=previous_session.context_id if previous_session else None,
        ).first()
        if (
            previous_engine_round is None
            or previous_engine_round.status != "completed"
            or previous_session is None
            or previous_session.status != "completed"
            or previous_context is None
            or previous_context.status != "completed"
        ):
            raise HTTPException(409, "Complete the earlier required round before starting this one.")
    return assignment, assessment, selected, None
