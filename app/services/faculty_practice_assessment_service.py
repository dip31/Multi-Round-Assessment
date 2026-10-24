"""Faculty-scoped reads for genuine Practice Assessment records."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import re

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.assessment import AssessmentRound, AssessmentSession
from app.models.assessment_context import AssessmentContext
from app.models.aptitude import AptitudeAttempt, AptitudeQuestion
from app.models.coding import CodingSubmission
from app.models.interview import InterviewSession, InterviewTurn
from app.models.faculty_practice_assessment import (
    FacultyPracticeAssessment,
    FacultyPracticeAssessmentRound,
    FacultyPracticeRoundAttempt,
)
from app.models.profile import StudentProfile
from app.models.session_problem import SessionProblem
from app.models.user import User
from app.modules.practice.services.practice_result_service import (
    get_round_detailed_review,
    get_round_result_summary,
)
from app.services.faculty_access_service import get_faculty_department


PRACTICE_MODE = "practice"
INTERVIEW_ROUND_TYPES = {
    "interview",
    "technical_interview",
    "hr_interview",
    "communication_interview",
}
APTITUDE_ROUND_TYPES = {"aptitude", "mcq", "combined", "technical"}


def _require_faculty(faculty: User) -> str:
    if faculty.role != "faculty":
        raise HTTPException(status_code=403, detail="Faculty access is required.")
    return "faculty"


def _practice_sessions_query(
    db: Session,
    faculty: User,
    *,
    student_id: int | None = None,
    session_id: int | None = None,
    load_details: bool = True,
):
    _require_faculty(faculty)
    department = get_faculty_department(db, faculty)
    query = (
        db.query(AssessmentSession)
        .join(AssessmentContext, AssessmentContext.id == AssessmentSession.context_id)
        .join(User, User.id == AssessmentSession.user_id)
        .join(StudentProfile, StudentProfile.user_id == User.id)
        .filter(
            AssessmentContext.mode == PRACTICE_MODE,
            User.role == "student",
            func.lower(StudentProfile.department) == department.casefold(),
            or_(
                AssessmentContext.student_id.is_(None),
                AssessmentContext.student_id == AssessmentSession.user_id,
            ),
        )
    )
    if load_details:
        query = query.options(
            selectinload(AssessmentSession.user).selectinload(User.student_profile),
            selectinload(AssessmentSession.context),
            selectinload(AssessmentSession.rounds),
        )
    if student_id is not None:
        query = query.filter(AssessmentSession.user_id == student_id)
    if session_id is not None:
        query = query.filter(AssessmentSession.id == session_id)
    return query


def _identity(session: AssessmentSession) -> dict:
    user = session.user
    profile = user.student_profile
    # The session's user FK and one-to-one student profile establish identity.
    # Prefer the academic profile name, then the canonical users.name field;
    # never infer identity from assessment/session/round data.
    def reliable_name(value: str | None) -> str | None:
        candidate = value.strip() if value and value.strip() else None
        # Test/fixture labels on unverified accounts are not safe student names.
        # A verified account or a clean profile value can still supply identity.
        if candidate and not user.is_verified and re.search(r"\b(?:test|demo|fixture)\b", candidate, flags=re.IGNORECASE):
            return None
        return candidate

    profile_name = reliable_name(profile.full_name if profile else None)
    account_name = reliable_name(user.name)
    name = profile_name or account_name
    return {
        "user_id": user.id,
        "name": name.strip() if name and name.strip() else "Student identity unavailable",
        "name_source": "student_profile" if profile_name else "linked_user_account" if account_name else "unavailable",
        "roll_number": profile.roll_number if profile and profile.roll_number else None,
        "department": profile.department if profile else None,
    }


def _activity_status(
    round_item: AssessmentRound,
    *,
    attempt_rows: list[AptitudeAttempt],
    coding_rows: list[CodingSubmission],
    assigned_problem_ids: list[int],
) -> str:
    if round_item.status in {"active", "in_progress"}:
        return "in_progress"
    if round_item.status in {"pending", "not_started"}:
        return "not_started"
    if round_item.status != "completed":
        return "unavailable"

    kind = (round_item.round_type or "").lower()
    if kind in APTITUDE_ROUND_TYPES:
        if not attempt_rows:
            return "unavailable"
        evaluated = sum(row.is_correct is not None for row in attempt_rows)
        return "completed" if evaluated == len(attempt_rows) else "awaiting_evaluation"

    if kind == "coding":
        if not coding_rows or not assigned_problem_ids:
            return "unavailable"
        if any(row.status == "running" for row in coding_rows):
            return "evaluation_in_progress"
        evaluated_problem_ids = {
            row.problem_id
            for row in coding_rows
            if row.score is not None
            and row.status not in {None, "running", "internal_error"}
        }
        if set(assigned_problem_ids).issubset(evaluated_problem_ids):
            return "completed"
        if any(row.status == "internal_error" for row in coding_rows):
            return "failed"
        return "awaiting_evaluation"

    # InterviewTurn is linked to InterviewSession/AssessmentSession, not to a
    # round. Session-level evidence is deliberately not used to mark a round.
    if kind in INTERVIEW_ROUND_TYPES:
        return "unavailable"
    return "unavailable"


def _aptitude_activity_label(attempt_count: int, evaluated_count: int, correct_count: int) -> str:
    if not attempt_count:
        return "No attempt recorded"
    question_label = "question" if attempt_count == 1 else "questions"
    pending = attempt_count - evaluated_count
    if pending:
        return f"{attempt_count} {question_label} attempted; {evaluated_count} evaluated, {pending} awaiting evaluation"
    return f"{attempt_count} {question_label} attempted; {correct_count} correct"


def _coding_activity_label(submission_count: int) -> str:
    if not submission_count:
        return "No submission recorded"
    label = "submission" if submission_count == 1 else "submissions"
    return f"{submission_count} {label}"


def _round_activity_rows(db: Session, sessions: list[AssessmentSession]) -> list[dict]:
    rounds = [item for session in sessions for item in session.rounds]
    round_ids = [item.id for item in rounds]
    if not round_ids:
        return []

    aptitude_records = db.query(AptitudeAttempt).filter(
        AptitudeAttempt.round_id.in_(round_ids)
    ).order_by(AptitudeAttempt.attempted_at.asc(), AptitudeAttempt.id.asc()).all()
    coding_records = db.query(CodingSubmission).filter(
        CodingSubmission.round_id.in_(round_ids)
    ).order_by(CodingSubmission.submitted_at.asc(), CodingSubmission.id.asc()).all()
    assigned_records = db.query(SessionProblem).filter(
        SessionProblem.round_id.in_(round_ids)
    ).order_by(SessionProblem.assigned_at.asc(), SessionProblem.id.asc()).all()
    interview_sessions = db.query(InterviewSession).filter(
        InterviewSession.session_id.in_([item.id for item in sessions])
    ).all()
    interview_ids = [item.id for item in interview_sessions]
    interview_turns = db.query(InterviewTurn).filter(
        InterviewTurn.interview_id.in_(interview_ids)
    ).all() if interview_ids else []
    assignment_links = db.query(FacultyPracticeRoundAttempt, FacultyPracticeAssessment).join(
        FacultyPracticeAssessmentRound,
        FacultyPracticeAssessmentRound.id == FacultyPracticeRoundAttempt.assessment_round_id,
    ).join(
        FacultyPracticeAssessment,
        FacultyPracticeAssessment.id == FacultyPracticeAssessmentRound.assessment_id,
    ).filter(FacultyPracticeRoundAttempt.round_id.in_(round_ids)).all()
    assignment_by_round = {
        link.round_id: {"title": assessment.title, "assessment_id": assessment.id}
        for link, assessment in assignment_links
    }
    interview_responses_by_session: dict[int, int] = {}
    interview_session_by_id = {item.id: item.session_id for item in interview_sessions}
    for turn in interview_turns:
        if turn.candidate_response:
            session_id = interview_session_by_id[turn.interview_id]
            interview_responses_by_session[session_id] = interview_responses_by_session.get(session_id, 0) + 1
    aptitude_by_round: dict[int, list[AptitudeAttempt]] = {}
    coding_by_round: dict[int, list[CodingSubmission]] = {}
    assigned_by_round: dict[int, list[int]] = {}
    for record in aptitude_records:
        aptitude_by_round.setdefault(record.round_id, []).append(record)
    for record in coding_records:
        coding_by_round.setdefault(record.round_id, []).append(record)
    for record in assigned_records:
        assigned_by_round.setdefault(record.round_id, []).append(record.problem_id)

    rows = []
    by_id = {session.id: session for session in sessions}
    for round_item in rounds:
        session = by_id[round_item.session_id]
        kind = (round_item.round_type or "").lower()
        aptitude = aptitude_by_round.get(round_item.id, [])
        coding = coding_by_round.get(round_item.id, [])
        assigned = assigned_by_round.get(round_item.id, [])
        status = _activity_status(
            round_item,
            attempt_rows=aptitude,
            coding_rows=coding,
            assigned_problem_ids=assigned,
        )

        summary = {}
        last_evidence = None
        score = None
        max_score = None
        score_scale = None
        attempt_count = 0
        activity_label = "No response data available"
        if kind in APTITUDE_ROUND_TYPES:
            attempt_count = len(aptitude)
            evaluated = [row for row in aptitude if row.is_correct is not None]
            correct = sum(row.is_correct is True for row in aptitude)
            summary = {
                "question_attempts": len(aptitude),
                "evaluated_answers": len(evaluated),
                "correct_answers": correct,
            }
            last_evidence = max((row.attempted_at for row in aptitude if row.attempted_at), default=None)
            activity_label = _aptitude_activity_label(len(aptitude), len(evaluated), correct)
            if status == "completed" and aptitude:
                result = get_round_result_summary(db, session.id, round_item.id)
                if result:
                    score = result.get("percentage")
                    max_score = 100.0
                    score_scale = "out of 100"
        elif kind == "coding":
            attempt_count = len(coding)
            summary = {"coding_submissions": len(coding)}
            last_evidence = max((row.submitted_at for row in coding if row.submitted_at), default=None)
            activity_label = _coding_activity_label(len(coding))
            if status == "completed" and assigned:
                result = get_round_result_summary(db, session.id, round_item.id)
                if result:
                    score = result.get("score")
                    max_score = result.get("max_score")
                    score_scale = f"out of {max_score:g} problem points" if max_score is not None else None
        elif kind in INTERVIEW_ROUND_TYPES:
            activity_label = (
                "Interview responses available at session level"
                if interview_responses_by_session.get(session.id, 0)
                else "No interview response recorded"
            )

        score = score if status == "completed" else None
        if score is None:
            score_scale = None
        last_activity = max(
            (
                value
                for value in (
                    last_evidence,
                    round_item.completed_at,
                    round_item.started_at,
                    session.completed_at,
                    session.started_at,
                )
                if value is not None
            ),
            default=None,
        )
        rows.append({
            "student": _identity(session),
            "assessment_name": assignment_by_round.get(round_item.id, {}).get("title", "Practice Assessment"),
            "assessment_id": assignment_by_round.get(round_item.id, {}).get("assessment_id"),
            "assessment_source": "faculty_assignment" if round_item.id in assignment_by_round else "independent_practice",
            "assessment_type": PRACTICE_MODE,
              "session_name": f"Practice Session #{session.id}",
            "session_id": session.id,
            "session_status": session.status,
            "session_started_at": session.started_at.isoformat() if session.started_at else None,
            "session_completed_at": session.completed_at.isoformat() if session.completed_at else None,
            "round_id": round_item.id,
            "round_name": kind.replace("_", " ").title() or "Assessment round",
            "round_type": kind,
            "round_status": round_item.status,
            "attempt_count": attempt_count,
            "has_submission_details": bool(aptitude or coding),
            "activity_label": activity_label,
            "attempt_summary": summary,
            "evaluation_status": status,
            "score": score,
            "score_scale": score_scale,
            "score_max": max_score if score is not None else None,
            "last_activity": last_activity.isoformat() if last_activity else None,
            "context_id": session.context_id,
            "mock_drive_id": None,
        })
    return rows


def list_practice_assessment_activity(
    db: Session,
    faculty: User,
    *,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    session_id: int | None = None,
    round_type: str | None = None,
    evaluation_status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    needs_attention: bool = False,
) -> dict:
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=400, detail="The start date must be on or before the end date.")
    sessions = _practice_sessions_query(db, faculty, session_id=session_id).order_by(
        AssessmentSession.id.desc()
    ).all()
    rows = _round_activity_rows(db, sessions)
    all_rows = rows[:]

    if search and search.strip():
        needle = search.strip().casefold()
        rows = [
            row for row in rows
            if needle in " ".join((
                row["student"]["name"],
                row["student"].get("roll_number") or "",
                row["assessment_name"],
                row["session_name"],
                row["round_name"],
            )).casefold()
        ]
    if round_type:
        rows = [row for row in rows if row["round_type"] == round_type]
    if evaluation_status:
        rows = [row for row in rows if row["evaluation_status"] == evaluation_status]
    if needs_attention:
        rows = [row for row in rows if row["evaluation_status"] in {
            "in_progress", "evaluation_in_progress", "awaiting_evaluation", "failed"
        }]
    if date_from:
        start = datetime.combine(date_from, time.min)
        rows = [row for row in rows if row["last_activity"] and datetime.fromisoformat(row["last_activity"]) >= start]
    if date_to:
        end = datetime.combine(date_to + timedelta(days=1), time.min)
        rows = [row for row in rows if row["last_activity"] and datetime.fromisoformat(row["last_activity"]) < end]

    rows.sort(key=lambda row: (row["last_activity"] or "", row["session_id"], row["round_id"]), reverse=True)
    session_options = {}
    students = {}
    for row in all_rows:
        session_options[row["session_id"]] = row["session_name"]
        student = row["student"]
        students[student["user_id"]] = {
            "id": student["user_id"],
            "name": student["name"],
            "roll_number": student["roll_number"],
        }
    total = len(rows)
    offset = (page - 1) * page_size
    return {
        "records": rows[offset:offset + page_size],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
        "filters": {
            "sessions": [{"id": key, "name": value} for key, value in session_options.items()],
            "round_types": sorted({row["round_type"] for row in all_rows}),
            "evaluation_statuses": sorted({row["evaluation_status"] for row in all_rows}),
            "students": sorted(students.values(), key=lambda item: item["name"].casefold()),
        },
    }


def get_faculty_practice_participation_trend(
    db: Session,
    faculty: User,
    *,
    now: datetime | None = None,
) -> dict:
    """Count distinct authorized students starting practice sessions per UTC week.

    AssessmentSession.started_at is set when the practice session is actually
    created in the in-progress state. Session rows are used directly so real
    starts without an AssessmentRound are still represented.
    """
    _require_faculty(faculty)
    current_time = now or datetime.now(timezone.utc).replace(tzinfo=None)
    current_week_start = current_time.date() - timedelta(days=current_time.weekday())
    range_end = datetime.combine(current_week_start, time.min)
    range_start = range_end - timedelta(weeks=12)

    started_sessions = (
        _practice_sessions_query(db, faculty, load_details=False)
        .filter(
            AssessmentSession.status.in_(
                ("in_progress", "completed", "terminated", "expired")
            ),
            AssessmentSession.started_at.is_not(None),
            AssessmentSession.started_at >= range_start,
            AssessmentSession.started_at < range_end,
        )
        .with_entities(AssessmentSession.user_id, AssessmentSession.started_at)
        .all()
    )

    student_ids_by_week: dict[datetime, set[int]] = {}
    for week_index in range(12):
        week_start = range_start + timedelta(weeks=week_index)
        student_ids_by_week[week_start] = set()

    for student_id, started_at in started_sessions:
        week_start_date = started_at.date() - timedelta(days=started_at.weekday())
        week_start = datetime.combine(week_start_date, time.min)
        if week_start in student_ids_by_week:
            student_ids_by_week[week_start].add(student_id)

    weeks = [
        {
            "week_start": week_start.date().isoformat(),
            "week_end": (week_start + timedelta(days=6)).date().isoformat(),
            "participating_students": len(student_ids),
        }
        for week_start, student_ids in student_ids_by_week.items()
    ]
    return {
        "bucket": "week",
        "timezone": "UTC",
        "range_start": range_start.date().isoformat(),
        "range_end": (range_end - timedelta(days=1)).date().isoformat(),
        "expected_weeks": 12,
        "weeks": weeks,
    }


def _authorized_practice_session(
    db: Session,
    faculty: User,
    *,
    student_id: int | None = None,
    session_id: int | None = None,
) -> AssessmentSession:
    result = _practice_sessions_query(
        db, faculty, student_id=student_id, session_id=session_id
    ).order_by(AssessmentSession.id.desc()).first()
    if result is None:
        raise HTTPException(status_code=404, detail="Practice assessment record not found in your faculty scope.")
    return result


def _evidence_for_round(db: Session, round_item: AssessmentRound):
    kind = (round_item.round_type or "").lower()
    if kind in APTITUDE_ROUND_TYPES:
        attempts = db.query(AptitudeAttempt).filter(
            AptitudeAttempt.round_id == round_item.id
        ).order_by(AptitudeAttempt.attempt_number.asc(), AptitudeAttempt.id.asc()).all()
        evaluated = sum(item.is_correct is not None for item in attempts)
        status = "completed" if attempts and evaluated == len(attempts) and round_item.status == "completed" else (
            "awaiting_evaluation" if attempts and evaluated < len(attempts) and round_item.status == "completed" else
            "in_progress" if round_item.status in {"active", "in_progress"} else "unavailable"
        )
        result = get_round_result_summary(db, round_item.session_id, round_item.id) if status == "completed" else None
        answer_items = []
        detailed_attempts = db.query(AptitudeAttempt).options(
            joinedload(AptitudeAttempt.question).joinedload(AptitudeQuestion.topic)
        ).filter(AptitudeAttempt.round_id == round_item.id).order_by(
            AptitudeAttempt.attempt_number.asc(), AptitudeAttempt.id.asc()
        ).all()
        for item in detailed_attempts:
            question = item.question
            answer_items.append({
                "attempt_id": item.id,
                "sequence": item.attempt_number,
                "question_id": item.question_id,
                "question_text": question.question_text if question else "Question unavailable",
                "selected_option": item.selected_option,
                "correct_option": question.correct_option if question else None,
                "is_correct": item.is_correct,
                "topic": question.topic.name if question and question.topic else None,
                "difficulty": item.difficulty or (question.difficulty if question else None),
                "response_time": item.response_time,
                "attempted_at": item.attempted_at.isoformat() if item.attempted_at else None,
            })
        return {
            "attempt_count": len(attempts),
            "has_submission_details": bool(attempts),
            "question_attempts": len(attempts),
            "correct_answers": sum(item.is_correct is True for item in attempts),
            "evaluated_answers": evaluated,
            "evaluation_status": status,
            "score": result.get("percentage") if result else None,
            "score_scale": "out of 100" if result else None,
            "score_max": 100 if result else None,
            "result": result,
            "answers": answer_items,
            "submissions": [],
            "last_activity": max((item.attempted_at for item in attempts if item.attempted_at), default=None),
        }

    if kind == "coding":
        assigned_ids = [item.problem_id for item in db.query(SessionProblem).filter(
            SessionProblem.round_id == round_item.id
        ).order_by(SessionProblem.problem_order.asc()).all()]
        submissions = db.query(CodingSubmission).filter(
            CodingSubmission.round_id == round_item.id
        ).order_by(CodingSubmission.submitted_at.asc(), CodingSubmission.id.asc()).all()
        evaluated_problem_ids = {
            item.problem_id for item in submissions
            if item.score is not None and item.status not in {None, "running", "internal_error"}
        }
        if any(item.status == "running" for item in submissions):
            status = "evaluation_in_progress"
        elif assigned_ids and set(assigned_ids).issubset(evaluated_problem_ids) and round_item.status == "completed":
            status = "completed"
        elif submissions and any(item.status == "internal_error" for item in submissions):
            status = "failed"
        elif submissions:
            status = "awaiting_evaluation"
        elif round_item.status in {"active", "in_progress"}:
            status = "in_progress"
        elif round_item.status in {"pending", "not_started"}:
            status = "not_started"
        else:
            status = "unavailable"
        result = get_round_result_summary(db, round_item.session_id, round_item.id) if status == "completed" else None
        review = get_round_detailed_review(db, round_item.session_id, round_item.id) if status == "completed" else None
        return {
            "attempt_count": len(submissions),
            "has_submission_details": bool(submissions),
            "question_attempts": None,
            "correct_answers": None,
            "evaluated_answers": len(evaluated_problem_ids),
            "evaluation_status": status,
            "score": result.get("score") if result else None,
            "score_scale": f"out of {result.get('max_score'):g} problem points" if result and result.get("max_score") else None,
            "score_max": result.get("max_score") if result else None,
            "result": result,
            "answers": [],
            "submissions": [
                {
                    "id": item.id,
                    "problem_id": item.problem_id,
                    "code": item.code,
                    "language": item.language,
                    "status": item.status or "unavailable",
                    "score": item.score if item.status not in {None, "running", "internal_error"} else None,
                    "submitted_at": item.submitted_at.isoformat() if item.submitted_at else None,
                }
                for item in submissions
            ],
            "submission_review": (review or {}).get("items", []),
            "last_activity": max((item.submitted_at for item in submissions if item.submitted_at), default=None),
        }

    return {
        "attempt_count": 0,
        "has_submission_details": False,
        "question_attempts": None,
        "correct_answers": None,
        "evaluated_answers": 0,
        "evaluation_status": "unavailable",
        "score": None,
        "score_scale": None,
        "score_max": None,
        "result": None,
        "answers": [],
        "submissions": [],
        "last_activity": None,
        "detail_note": "Interview responses are stored at session level and are not linked to this selected round.",
    }


def get_practice_round_detail(
    db: Session,
    faculty: User,
    *,
    student_id: int,
    session_id: int,
    round_id: int,
) -> dict:
    session = _authorized_practice_session(
        db, faculty, student_id=student_id, session_id=session_id
    )
    round_item = next((item for item in session.rounds if item.id == round_id), None)
    if round_item is None:
        raise HTTPException(status_code=404, detail="Practice round not found in your faculty scope.")
    evidence = _evidence_for_round(db, round_item)
    return {
        "student": _identity(session),
        "assessment_name": "Practice Assessment",
        "session_id": session.id,
        "session_name": f"Practice Session #{session.id}",
        "session_started_at": session.started_at.isoformat() if session.started_at else None,
        "round_id": round_item.id,
        "round_name": (round_item.round_type or "Assessment round").replace("_", " ").title(),
        "round_type": round_item.round_type,
        "round_status": round_item.status,
        "started_at": round_item.started_at.isoformat() if round_item.started_at else None,
        "completed_at": round_item.completed_at.isoformat() if round_item.completed_at else None,
        **evidence,
    }


def get_practice_student_report(db: Session, faculty: User, *, student_id: int) -> dict:
    sessions = _practice_sessions_query(db, faculty, student_id=student_id).order_by(
        AssessmentSession.started_at.asc(), AssessmentSession.id.asc()
    ).all()
    if not sessions:
        raise HTTPException(status_code=404, detail="Practice student not found in your faculty scope.")
    student = _identity(sessions[0])
    rounds = [round_item for session in sessions for round_item in session.rounds]
    rounds.sort(key=lambda item: (item.started_at or datetime.min, item.id))
    attempt_ordinals: dict[str, int] = {}
    history = []
    evaluated_rounds = []
    question_attempt_count = 0
    correct_answer_count = 0
    coding_submission_count = 0
    completed_round_count = 0
    pending_evaluation_count = 0
    rounds_with_participation = 0
    sessions_by_id = {item.id: item for item in sessions}
    for round_item in rounds:
        kind = (round_item.round_type or "").lower()
        attempt_ordinals[kind] = attempt_ordinals.get(kind, 0) + 1
        evidence = _evidence_for_round(db, round_item)
        question_attempt_count += evidence.get("question_attempts") or 0
        correct_answer_count += evidence.get("correct_answers") or 0
        coding_submission_count += len(evidence.get("submissions", [])) if kind == "coding" else 0
        if evidence.get("attempt_count", 0) > 0:
            rounds_with_participation += 1
        if round_item.status == "completed":
            completed_round_count += 1
        if evidence["evaluation_status"] == "completed" and evidence.get("score") is not None:
            evaluated_rounds.append({
                "round_type": kind,
                "attempt_number": attempt_ordinals[kind],
                "score": evidence.get("score"),
                "score_scale": evidence.get("score_scale"),
                "score_max": evidence.get("score_max"),
                "date": round_item.completed_at.isoformat() if round_item.completed_at else (
                    round_item.started_at.isoformat() if round_item.started_at else None
                ),
            })
        if evidence["evaluation_status"] in {"awaiting_evaluation", "evaluation_in_progress"}:
            pending_evaluation_count += 1
        session = sessions_by_id[round_item.session_id]
        history.append({
            "session_id": session.id,
            "session_name": f"Practice Session #{session.id}",
            "assessment_name": "Practice Assessment",
            "round_id": round_item.id,
            "round_name": kind.replace("_", " ").title(),
            "round_type": kind,
            "attempt_number": attempt_ordinals[kind],
            "date": round_item.completed_at.isoformat() if round_item.completed_at else (
                round_item.started_at.isoformat() if round_item.started_at else None
            ),
            "round_status": round_item.status,
            "evaluation_status": evidence["evaluation_status"],
            "attempt_count": evidence["attempt_count"],
            "question_attempts": evidence.get("question_attempts"),
            "correct_answers": evidence.get("correct_answers"),
            "evaluated_answers": evidence.get("evaluated_answers"),
            "activity_label": "Awaiting activity classification",
            "score": evidence["score"],
            "score_scale": evidence["score_scale"],
            "score_max": evidence["score_max"],
        })

    interview_activity = []
    interview_sessions = (
        db.query(InterviewSession)
        .filter(InterviewSession.session_id.in_([item.id for item in sessions]))
        .order_by(InterviewSession.created_at.asc(), InterviewSession.id.asc())
        .all()
    )
    interview_response_count = 0
    for interview in interview_sessions:
        turns = db.query(InterviewTurn).filter(
            InterviewTurn.interview_id == interview.id
        ).order_by(InterviewTurn.turn_number.asc(), InterviewTurn.id.asc()).all()
        response_turns = [item for item in turns if item.candidate_response]
        scored_turns = [item for item in response_turns if item.final_score is not None]
        interview_response_count += len(response_turns)
        interview_activity.append({
            "session_id": interview.session_id,
            "phase": interview.phase,
            "status": interview.status,
            "completion_reason": interview.completion_reason,
            "turn_count": len(turns),
            "response_count": len(response_turns),
            "evaluated_response_count": len(scored_turns),
            "turns": [
                {
                    "turn_number": item.turn_number,
                    "question_text": item.question_text,
                    "candidate_response": item.candidate_response,
                    "content_score": item.content_score,
                    "final_score": item.final_score,
                    "intent": item.intent,
                    "is_followup": item.is_followup,
                    "created_at": item.created_at.isoformat() if item.created_at else None,
                }
                for item in turns
            ],
        })

    sessions_with_rounds = {item.session_id for item in rounds}
    for session in sessions:
        if session.id in sessions_with_rounds:
            continue
        history.append({
            "session_id": session.id,
            "session_name": f"Practice Session #{session.id}",
            "assessment_name": "Practice Assessment",
            "round_id": None,
            "round_name": "No round recorded",
            "round_type": None,
            "attempt_number": None,
            "date": session.completed_at.isoformat() if session.completed_at else (
                session.started_at.isoformat() if session.started_at else None
            ),
            "round_status": None,
            "evaluation_status": "unavailable",
            "attempt_count": 0,
            "question_attempts": None,
            "correct_answers": None,
            "activity_label": "No round recorded",
            "score": None,
            "score_scale": None,
            "score_max": None,
        })
    history.sort(key=lambda item: (item["date"] or "", item["session_id"], item["round_id"] or 0))

    interview_response_sessions = {
        item["session_id"] for item in interview_activity if item["response_count"] > 0
    }
    for item in history:
        if item["round_type"] in INTERVIEW_ROUND_TYPES:
            item["activity_label"] = (
                "Interview responses available at session level"
                if item["session_id"] in interview_response_sessions
                else "No interview response recorded"
            )
        elif item["round_type"] in APTITUDE_ROUND_TYPES:
            item["activity_label"] = _aptitude_activity_label(
                item["attempt_count"], item["evaluated_answers"] or 0, item["correct_answers"] or 0
            )
        elif item["round_type"] == "coding":
            item["activity_label"] = (
                _coding_activity_label(item["attempt_count"])
            )

    comparable_groups: dict[tuple, list[dict]] = {}
    for item in evaluated_rounds:
        if item["score"] is None or item["score_max"] is None or item["score_max"] <= 0:
            continue
        key = (item["round_type"], item["score_scale"], item["score_max"])
        comparable_groups.setdefault(key, []).append(item)
    comparisons = []
    for key, values in comparable_groups.items():
        if len(values) < 2:
            continue
        first, last = values[0], values[-1]
        comparisons.append({
            "round_type": key[0],
            "score_scale": key[1],
            "comparable_attempts": len(values),
            "first_score": first["score"],
            "first_date": first.get("date"),
            "latest_score": last["score"],
            "latest_date": last.get("date"),
            "change": round(last["score"] - first["score"], 2),
        })

    return {
        "student": student,
        "data_notes": [
            *( ["A reliable student name is not available for this account; update the student profile to resolve it."] if student.get("name_source") == "unavailable" else [] ),
            *( ["No roll number is available in the authorized student profile."] if not student["roll_number"] else [] ),
            *( ["Evaluation results are still pending for one or more rounds."] if pending_evaluation_count else [] ),
            *( ["Interview responses are stored at session level rather than being assigned to individual rounds."] if interview_activity else [] ),
            "No separate feedback or rubric record is available for these practice rounds.",
        ],
        "summary": {
            "practice_sessions": len(sessions),
            "rounds_with_participation": rounds_with_participation,
            "completed_rounds": completed_round_count,
            "question_attempts": question_attempt_count,
            "correct_answers": correct_answer_count,
            "coding_submissions": coding_submission_count,
            "interview_responses": interview_response_count,
            "evaluated_round_results": len(evaluated_rounds),
            "pending_evaluations": pending_evaluation_count,
        },
        "history": history,
        "session_level_interviews": interview_activity,
        "comparisons": comparisons,
        "progress_message": (
            "Comparable evaluated attempts are available; like-for-like results are summarized below."
            if comparisons else
            "No evaluated practice results are available yet; progress cannot be assessed."
            if not evaluated_rounds else
            "There is one evaluated practice result; a progress trend cannot yet be established."
            if len(evaluated_rounds) == 1 else
            "Evaluated practice results are available, but they are not comparable, so a progress trend cannot be established."
        ),
        "count_definitions": {
            "practice_sessions": "Distinct persisted AssessmentSession rows linked to practice-mode contexts.",
            "rounds_with_participation": "Rounds with one or more persisted aptitude question attempts or coding submissions; session-level interview turns are not attributed to rounds.",
            "completed_rounds": "Persisted AssessmentRound rows whose status is completed; completion does not imply a saved or evaluated result.",
            "question_attempts": "Persisted AptitudeAttempt rows.",
            "coding_submissions": "Persisted CodingSubmission rows.",
            "correct_answers": "Aptitude attempts with persisted is_correct=true; unevaluated answers are not counted as correct.",
            "interview_responses": "InterviewTurn rows with a persisted candidate response; session-level because turns have no round foreign key.",
            "evaluated_round_results": "Practice rounds with a complete result under the existing practice scoring service.",
            "pending_evaluations": "Aptitude or coding rounds with persisted evidence that is still running or awaiting evaluation.",
        },
    }
