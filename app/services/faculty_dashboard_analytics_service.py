"""Read-only faculty dashboard analytics derived from authorized persisted data."""

from collections import defaultdict
from datetime import datetime
import math

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.models.assessment import AssessmentSession
from app.models.assessment_context import AssessmentContext
from app.models.competency import CompetencyEvidenceMapping
from app.models.profile import StudentProfile
from app.models.user import User
from app.services.competency_scoring_service import SCORING_POLICY_VERSION, score_session_competencies


def get_faculty_improvement_summary(db: Session, department: str) -> dict:
    """Compare eligible Mock Drive readiness attempts within the same drive/blueprint.

    This mirrors TPO readiness scoring (D1-v1) while constraining rows to the
    faculty member's department. A student is counted as improving when at
    least one same-drive, same-blueprint chronological comparison increases.
    """
    eligible_students = {
        row[0]
        for row in db.query(User.id)
        .join(StudentProfile, StudentProfile.user_id == User.id)
        .filter(
            User.role == "student",
            StudentProfile.department.is_not(None),
            func.lower(StudentProfile.department) == department.casefold(),
        )
        .distinct()
        .all()
    }


    contexts = (
        db.query(AssessmentContext)
        .join(User, User.id == AssessmentContext.student_id)
        .join(StudentProfile, StudentProfile.user_id == User.id)
        .filter(
            User.role == "student",
            AssessmentContext.mode == "mock_drive",
            AssessmentContext.purpose == "mock_drive",
            AssessmentContext.status == "completed",
            AssessmentContext.student_id.is_not(None),
            func.lower(StudentProfile.department) == department.casefold(),
        )
        .order_by(AssessmentContext.id.asc())
        .all()
    )
    context_ids = [context.id for context in contexts]
    sessions_by_context = defaultdict(list)
    if context_ids:
        for session in (
            db.query(AssessmentSession)
            .filter(AssessmentSession.context_id.in_(context_ids))
            .order_by(AssessmentSession.id.asc())
            .all()
        ):
            sessions_by_context[session.context_id].append(session)

    # Keying by student + drive + pinned blueprint prevents comparing unrelated
    # assessments or scoring configurations. Reuse only the latest session for
    # each persisted attempt context, matching the TPO readiness calculation.
    attempts_by_comparable_scope = defaultdict(list)
    scoring_errors = 0
    for context in contexts:
        if context.student_id not in eligible_students or not context.blueprint_snapshot:
            continue
        sessions = [
            item for item in sessions_by_context.get(context.id, [])
            if item.user_id == context.student_id
        ]
        if not sessions:
            continue
        session = sessions[-1]
        try:
            scoring = score_session_competencies(db, session)
        except Exception:
            scoring_errors += 1
            continue
        if scoring.get("overall_score_status") not in {"final", "provisional"}:
            continue
        score = scoring.get("overall_score")
        blueprint_id = scoring.get("blueprint_id")
        blueprint_version = scoring.get("blueprint_version")
        if score is None or context.mock_drive_id is None or blueprint_id is None or blueprint_version is None:
            continue
        key = (
            context.student_id,
            context.mock_drive_id,
            blueprint_id,
            blueprint_version,
            SCORING_POLICY_VERSION,
        )
        attempts_by_comparable_scope[key].append((context.completed_at or context.created_at, context.id, float(score)))

    deltas_by_student = defaultdict(list)
    for key, rows in attempts_by_comparable_scope.items():
        if len(rows) < 2:
            continue
        rows.sort(key=lambda row: (
            row[0] is not None,
            row[0].replace(tzinfo=None) if row[0] is not None else datetime.min,
            row[1],
        ))
        deltas_by_student[key[0]].append(rows[-1][2] - rows[0][2])

    improving_students = sum(any(delta > 0 for delta in deltas) for deltas in deltas_by_student.values())
    compared_students = len(deltas_by_student)
    return {
        "available": compared_students > 0,
        "improving_students": improving_students if compared_students else None,
        "students_compared": compared_students,
        "authorized_students": len(eligible_students),
        "comparison_scopes": sum(len(deltas) for deltas in deltas_by_student.values()),
        "scoring_errors": scoring_errors,
        "definition": (
            "Distinct faculty-scoped students with an increase between earliest and latest "
            "eligible completed Mock Drive readiness scores within the same drive, pinned "
            "blueprint version, and D1-v1 scoring policy."
        ),
        "reason": None if compared_students else (
            f"Competency scoring was unavailable for {scoring_errors} completed attempt(s); "
            "comparable history could not be confirmed."
            if scoring_errors else
            "No student has two eligible completed attempts for the same Mock Drive and pinned blueprint."
        ),
    }


def get_faculty_improvement_trend(db: Session, department: str) -> dict:
    """Build a fixed-cohort trend from comparable completed Mock Drive attempts.

    An attempt is comparable only within the same student, drive, pinned
    blueprint ID/version, and D1 scoring policy. One latest session is scored
    per completed attempt context, matching the existing faculty improvement
    summary. Only final 0..100 scores are used. To keep every plotted point on
    the same cohort, all eligible series are truncated to the shortest series
    length (at least two attempts). Scores are averaged across a student's
    comparable series first, then across distinct students, so students with
    multiple drives do not receive extra weight.
    """
    eligible_students = {
        row[0]
        for row in db.query(User.id)
        .join(StudentProfile, StudentProfile.user_id == User.id)
        .filter(
            User.role == "student",
            StudentProfile.department.is_not(None),
            func.lower(StudentProfile.department) == department.casefold(),
        )
        .distinct()
        .all()
    }
    contexts = (
        db.query(AssessmentContext)
        .join(User, User.id == AssessmentContext.student_id)
        .join(StudentProfile, StudentProfile.user_id == User.id)
        .filter(
            User.role == "student",
            AssessmentContext.mode == "mock_drive",
            AssessmentContext.purpose == "mock_drive",
            AssessmentContext.status == "completed",
            AssessmentContext.student_id.is_not(None),
            func.lower(StudentProfile.department) == department.casefold(),
        )
        .order_by(AssessmentContext.id.asc())
        .all()
    )
    context_ids = [context.id for context in contexts]
    sessions_by_context = defaultdict(list)
    if context_ids:
        for session in (
            db.query(AssessmentSession)
            .options(selectinload(AssessmentSession.context))
            .filter(AssessmentSession.context_id.in_(context_ids))
            .order_by(AssessmentSession.id.asc())
            .all()
        ):
            sessions_by_context[session.context_id].append(session)

    latest_sessions = []
    for context in contexts:
        sessions = [
            item for item in sessions_by_context.get(context.id, [])
            if item.user_id == context.student_id and item.status == "completed"
        ]
        if sessions:
            latest_sessions.append(sessions[-1])
    mappings_by_session = defaultdict(list)
    session_ids = [session.id for session in latest_sessions]
    if session_ids:
        for mapping in db.query(CompetencyEvidenceMapping).filter(
            CompetencyEvidenceMapping.session_id.in_(session_ids)
        ).all():
            mappings_by_session[mapping.session_id].append(mapping)

    series_by_key = defaultdict(list)
    scoring_errors = 0
    excluded_attempts = 0
    scored_attempt_count = 0
    for context in contexts:
        if context.student_id not in eligible_students or not context.blueprint_snapshot:
            excluded_attempts += 1
            continue
        sessions = [
            item for item in sessions_by_context.get(context.id, [])
            if item.user_id == context.student_id and item.status == "completed"
        ]
        if not sessions:
            excluded_attempts += 1
            continue
        session = sessions[-1]
        try:
            scoring = score_session_competencies(
                db, session, evidence_mappings=mappings_by_session.get(session.id, [])
            )
        except Exception:
            scoring_errors += 1
            continue
        raw_score = scoring.get("overall_score")
        try:
            score = float(raw_score) if raw_score is not None and not isinstance(raw_score, bool) else None
        except (TypeError, ValueError, OverflowError):
            score = None
        blueprint_id = scoring.get("blueprint_id")
        blueprint_version = scoring.get("blueprint_version")
        if (
            scoring.get("overall_score_status") != "final"
            or score is None
            or not math.isfinite(score)
            or not 0 <= score <= 100
            or context.mock_drive_id is None
            or blueprint_id is None
            or blueprint_version is None
        ):
            excluded_attempts += 1
            continue
        timestamp = context.completed_at or context.created_at or session.completed_at or session.started_at
        key = (
            context.student_id,
            context.mock_drive_id,
            blueprint_id,
            blueprint_version,
            SCORING_POLICY_VERSION,
        )
        series_by_key[key].append((timestamp, context.id, score))
        scored_attempt_count += 1

    comparable_series = {}
    for key, attempts in series_by_key.items():
        if len(attempts) < 2:
            continue
        attempts.sort(key=lambda row: (
            row[0] is not None,
            row[0].replace(tzinfo=None) if row[0] is not None else datetime.min,
            row[1],
        ))
        comparable_series[key] = attempts

    if not comparable_series:
        total_excluded_attempts = excluded_attempts + scored_attempt_count
        return {
            "available": False,
            "points": [],
            "distinct_students": 0,
            "comparable_series": 0,
            "scored_attempts": scored_attempt_count,
            "excluded_attempts": total_excluded_attempts,
            "scoring_errors": scoring_errors,
            "partial_coverage": bool(total_excluded_attempts or scoring_errors),
            "definition": "Final D1-v1 scores from completed Mock Drive contexts, compared only within the same student, drive, and pinned blueprint version.",
            "reason": "No student has two final scored attempts for the same drive and pinned blueprint version.",
        }

    shared_attempt_count = min(len(attempts) for attempts in comparable_series.values())
    scores_by_student_and_attempt = defaultdict(lambda: defaultdict(list))
    for key, attempts in comparable_series.items():
        student_id = key[0]
        for index, (_, _, score) in enumerate(attempts[:shared_attempt_count], start=1):
            scores_by_student_and_attempt[index][student_id].append(score)

    points = []
    previous_average = None
    for attempt_number in range(1, shared_attempt_count + 1):
        student_scores = {
            student_id: sum(scores) / len(scores)
            for student_id, scores in scores_by_student_and_attempt[attempt_number].items()
        }
        average = sum(student_scores.values()) / len(student_scores)
        points.append({
            "attempt_number": attempt_number,
            "average_score": average,
            "distinct_students": len(student_scores),
            "comparable_series": len(comparable_series),
            "score_change_percentage_points": average - previous_average if previous_average is not None else None,
        })
        previous_average = average

    included_attempts = shared_attempt_count * len(comparable_series)
    total_excluded_attempts = excluded_attempts + max(0, scored_attempt_count - included_attempts)
    return {
        "available": len(points) >= 2,
        "points": points,
        "distinct_students": len({key[0] for key in comparable_series}),
        "comparable_series": len(comparable_series),
        "scored_attempts": scored_attempt_count,
        "included_attempts": included_attempts,
        "excluded_attempts": total_excluded_attempts,
        "scoring_errors": scoring_errors,
        "partial_coverage": bool(total_excluded_attempts or scoring_errors),
        "definition": "Final D1-v1 Mock Drive scores are compared chronologically only within the same student, drive, and pinned blueprint version. All plotted points use the same matched student cohort and shared attempt depth.",
        "reason": None,
    }
