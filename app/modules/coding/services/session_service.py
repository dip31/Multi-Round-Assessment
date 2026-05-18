"""
Coding Session Service

AMCAT-style round lifecycle: start, timer, validate, end, result.
Works with existing assessment_rounds table — no new session table.
"""

import random
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_
from fastapi import HTTPException

from app.models.assessment import AssessmentRound, AssessmentSession
from app.models.coding import CodingProblem, CodingSubmission, SessionProblem
from app.config.settings import settings


# ── Private helpers ───────────────────────────────────────────────────────────

def _get_coding_round_for_user(db: Session,
                                user_id: int) -> AssessmentRound:
    """Find the coding AssessmentRound for user's active session.

    Raises:
        HTTPException(404): No active session or no coding round.
    """
    round_obj = (
        db.query(AssessmentRound)
        .join(AssessmentSession,
              AssessmentRound.session_id == AssessmentSession.id)
        .filter(
            AssessmentSession.user_id == user_id,
            AssessmentSession.status == "in_progress",
            AssessmentRound.round_type == "coding"
        )
        .first()
    )
    if not round_obj:
        raise HTTPException(
            404,
            "No active assessment session found. "
            "Call POST /api/v1/session/start first."
        )
    return round_obj


def _verify_round_ownership(db: Session, round_id: int,
                             user_id: int) -> AssessmentRound:
    """Verify round belongs to user. Raises 404 if not."""
    round_obj = (
        db.query(AssessmentRound)
        .join(AssessmentSession,
              AssessmentRound.session_id == AssessmentSession.id)
        .filter(
            AssessmentRound.id == round_id,
            AssessmentSession.user_id == user_id
        )
        .first()
    )
    if not round_obj:
        raise HTTPException(404, "Coding round not found.")
    return round_obj


def _get_problem_status(db: Session, round_id: int,
                         problem_id: int) -> str:
    """Calculate display status for a problem based on submissions.

    Returns:
        "accepted"      — at least one submission scored 100
        "attempted"     — submitted but not fully solved
        "not_attempted" — no submissions yet
    """
    submissions = (
        db.query(CodingSubmission)
        .filter(
            CodingSubmission.round_id == round_id,
            CodingSubmission.problem_id == problem_id
        )
        .all()
    )
    if not submissions:
        return "not_attempted"
    if any(s.score == 100.0 for s in submissions):
        return "accepted"
    return "attempted"


def _auto_expire_round(db: Session,
                        round_obj: AssessmentRound) -> None:
    """Mark round as completed when timer expires."""
    round_obj.status = "completed"
    round_obj.completed_at = datetime.utcnow()
    db.commit()


# ── Public API ────────────────────────────────────────────────────────────────

def start_coding_round(db: Session, user_id: int) -> dict:
    """Start coding round. Randomly assigns problems. Sets timer.

    Steps:
      1. Find coding round row for user's active session.
      2. If round is completed, reset it to pending and clear old data.
      3. Randomly assign CODING_ROUND_PROBLEMS_COUNT problems.
      4. Set status=active, end_time=now+time_limit.

    Raises:
        HTTPException(404): No active session.
        HTTPException(400): Round already active.
        HTTPException(400): Not enough problems in database.
    """
    round_obj = _get_coding_round_for_user(db, user_id)

    if round_obj.status == "active":
        raise HTTPException(400, "Coding round is already in progress.")
    
    # If round is completed, allow restart by clearing old data
    if round_obj.status == "completed":
        # Delete old session problems
        db.query(SessionProblem).filter(
            SessionProblem.round_id == round_obj.id
        ).delete()
        # Reset round status
        round_obj.status = "pending"
        round_obj.score = 0
        round_obj.completed_at = None
        db.commit()

    # Check if problems already assigned (for pending rounds)
    existing = db.query(SessionProblem).filter(
        SessionProblem.round_id == round_obj.id
    ).first()
    if existing:
        raise HTTPException(400, "Coding round has already been started.")

    # Randomly assign problems
    all_problems = db.query(CodingProblem).all()
    count = settings.CODING_ROUND_PROBLEMS_COUNT
    if len(all_problems) < count:
        raise HTTPException(
            400,
            f"Not enough problems in bank. "
            f"Need {count}, found {len(all_problems)}."
        )

    selected = random.sample(all_problems, count)
    session_problems = [
        SessionProblem(
            round_id=round_obj.id,
            problem_id=prob.id,
            problem_order=idx + 1,
            marked_for_review=False
        )
        for idx, prob in enumerate(selected)
    ]
    db.add_all(session_problems)
    db.flush()

    # Activate round and set timer
    now = datetime.utcnow()
    round_obj.status = "active"
    round_obj.started_at = now
    round_obj.time_limit_minutes = settings.CODING_ROUND_TIME_LIMIT_MINUTES
    round_obj.end_time = now + timedelta(
        minutes=settings.CODING_ROUND_TIME_LIMIT_MINUTES
    )
    db.commit()
    db.refresh(round_obj)

    return {
        "round_id": round_obj.id,
        "status": round_obj.status,
        "time_limit_minutes": round_obj.time_limit_minutes,
        "end_time": round_obj.end_time,
        "problems": [
            {
                "id": sp.problem.id,
                "title": sp.problem.title,
                "difficulty": sp.problem.difficulty,
                "tags": sp.problem.tags or [],
                "problem_order": sp.problem_order,
                "status": "not_attempted",
                "marked_for_review": False
            }
            for sp in sorted(session_problems, key=lambda x: x.problem_order)
        ]
    }
def restart_coding_round(db: Session, user_id: int) -> dict:
    """Restart coding round by resetting it completely.

    This function:
    1. Finds the coding round for the user's active session
    2. Deletes all old session problems and submissions
    3. Resets the round status to pending
    4. Calls start_coding_round to assign new problems

    This allows users to take the assessment again with fresh problems.
    """
    round_obj = _get_coding_round_for_user(db, user_id)

    # Delete old session problems
    db.query(SessionProblem).filter(
        SessionProblem.round_id == round_obj.id
    ).delete()

    # Delete old submissions (optional - comment out if you want to keep history)
    from app.models.coding import CodingSubmission
    db.query(CodingSubmission).filter(
        CodingSubmission.round_id == round_obj.id
    ).delete()

    # Reset round
    round_obj.status = "pending"
    round_obj.score = 0
    round_obj.completed_at = None
    round_obj.started_at = None
    round_obj.end_time = None
    db.commit()

    # Now start fresh
    return start_coding_round(db, user_id)



def get_session_status(db: Session, round_id: int,
                        user_id: int) -> dict:
    """Get live session with countdown timer and per-problem statuses.

    Auto-expires round if time ran out since last request.

    Raises:
        HTTPException(400): Round not started yet.
    """
    round_obj = _verify_round_ownership(db, round_id, user_id)

    if round_obj.status == "pending":
        raise HTTPException(
            400,
            "Coding round not started. "
            "Call POST /api/v1/coding/start-round first."
        )

    remaining = (round_obj.end_time - datetime.utcnow()).total_seconds()
    time_remaining = max(0, int(remaining))

    if time_remaining == 0 and round_obj.status == "active":
        _auto_expire_round(db, round_obj)
        db.refresh(round_obj)

    session_problems = (
        db.query(SessionProblem)
        .filter(SessionProblem.round_id == round_id)
        .order_by(SessionProblem.problem_order)
        .all()
    )

    # Check if all problems have been submitted (attempted or accepted), not necessarily solved correctly
    all_problems_submitted = True
    problems_data = []
    
    for sp in session_problems:
        status = _get_problem_status(db, round_id, sp.problem_id)
        # Problem is considered "submitted" if status is "attempted" or "accepted"
        if status == "not_attempted":
            all_problems_submitted = False
            
        problems_data.append({
            "id": sp.problem.id,
            "title": sp.problem.title,
            "difficulty": sp.problem.difficulty,
            "tags": sp.problem.tags or [],
            "problem_order": sp.problem_order,
            "status": status,
            "marked_for_review": sp.marked_for_review
        })

    return {
        "round_id": round_obj.id,
        "status": round_obj.status,
        "time_limit_minutes": round_obj.time_limit_minutes,
        "end_time": round_obj.end_time,
        "time_remaining_seconds": time_remaining,
        "problems": problems_data,
        "all_problems_solved": all_problems_submitted  # This field indicates if all problems have been submitted (attempted or accepted)
    }


def validate_active_session(db: Session, round_id: int,
                              user_id: int, problem_id: int) -> None:
    """Validate submission is allowed. Called before every submit/run.

    Checks:
      1. Round is active.
      2. Time has not expired.
      3. Problem is assigned to this candidate's session.

    Raises:
        HTTPException(403): Round not active, time expired,
                            or problem not assigned.
    """
    round_obj = _verify_round_ownership(db, round_id, user_id)

    if round_obj.status != "active":
        raise HTTPException(
            403,
            f"Coding round is not active. Current status: {round_obj.status}"
        )

    if datetime.utcnow() > round_obj.end_time:
        _auto_expire_round(db, round_obj)
        raise HTTPException(
            403,
            "Time limit exceeded. Submissions are no longer accepted."
        )

    assignment = db.query(SessionProblem).filter(
        and_(
            SessionProblem.round_id == round_id,
            SessionProblem.problem_id == problem_id
        )
    ).first()
    if not assignment:
        raise HTTPException(
            403,
            "This problem is not assigned to your session."
        )


def toggle_mark_for_review(db: Session, round_id: int,
                            problem_id: int,
                            user_id: int) -> SessionProblem:
    """Toggle marked_for_review for a problem.

    Raises:
        HTTPException(403): Problem not in session.
    """
    _verify_round_ownership(db, round_id, user_id)

    sp = db.query(SessionProblem).filter(
        and_(
            SessionProblem.round_id == round_id,
            SessionProblem.problem_id == problem_id
        )
    ).first()
    if not sp:
        raise HTTPException(403, "Problem not assigned to your session.")

    sp.marked_for_review = not sp.marked_for_review
    db.commit()
    db.refresh(sp)
    return sp


def end_coding_round(db: Session, round_id: int,
                      user_id: int) -> dict:
    """End round. Calculate best-submission score per problem.

    Final score = average of best score per assigned problem.

    Raises:
        HTTPException(400): Round not active.
    """
    round_obj = _verify_round_ownership(db, round_id, user_id)

    if round_obj.status != "active":
        raise HTTPException(
            400,
            f"Cannot end round with status: {round_obj.status}"
        )

    session_problems = db.query(SessionProblem).filter(
        SessionProblem.round_id == round_id
    ).all()
    assigned_ids = [sp.problem_id for sp in session_problems]

    submissions = db.query(CodingSubmission).filter(
        CodingSubmission.round_id == round_id
    ).all()

    problems_attempted = 0
    problems_solved = 0
    total_score = 0.0

    for pid in assigned_ids:
        prob_subs = [s for s in submissions if s.problem_id == pid]
        if not prob_subs:
            continue
        problems_attempted += 1
        best = max(prob_subs, key=lambda s: s.score or 0.0)
        total_score += best.score or 0.0
        if (best.score or 0.0) >= 100.0:
            problems_solved += 1

    final_score = round(
        total_score / len(assigned_ids) if assigned_ids else 0.0, 2
    )

    round_obj.status = "completed"
    round_obj.completed_at = datetime.utcnow()
    round_obj.score = final_score
    db.commit()

    return {
        "round_id": round_id,
        "status": "completed",
        "total_score": final_score,
        "problems_attempted": problems_attempted,
        "problems_solved": problems_solved
    }


def get_session_result(db: Session, round_id: int,
                        user_id: int) -> dict:
    """Get final result. Round must be completed.

    Raises:
        HTTPException(400): Round not yet completed.
    """
    round_obj = _verify_round_ownership(db, round_id, user_id)

    if round_obj.status == "pending":
        raise HTTPException(400, "Round was never started.")
    if round_obj.status == "active":
        raise HTTPException(
            400,
            "Round still in progress. "
            "Call POST /api/v1/coding/session/{round_id}/end first."
        )

    session_problems = db.query(SessionProblem).filter(
        SessionProblem.round_id == round_id
    ).all()
    submissions = db.query(CodingSubmission).filter(
        CodingSubmission.round_id == round_id
    ).all()

    # Count total problems assigned to this session (not submission count)
    total_problems = len(session_problems)
    
    # Count problems that have at least one submission with 100% score
    solved = sum(
        1 for sp in session_problems
        if any(s.problem_id == sp.problem_id and s.score == 100.0
               for s in submissions)
    )

    return {
        "round_id": round_id,
        "status": round_obj.status,
        "total_score": round_obj.score or 0.0,
        "problems_attempted": total_problems,  # Total problems in test
        "problems_solved": solved
    }
