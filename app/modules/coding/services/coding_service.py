from typing import Dict, Any, List, Optional
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.coding import CodingProblem, CodingTestCase, CodingSubmission
from app.models.session_problem import SessionProblem
from app.modules.coding.utils.code_evaluator import evaluate_submission
from app.services import session_service
from app.config.settings import settings
from app.models.assessment import AssessmentRound, AssessmentSession


CODING_ROUND_PROBLEMS_COUNT = 3


def list_problems(db: Session) -> List[CodingProblem]:
    # Return a small set of problems for the round (visible test cases only)
    problems = (
        db.query(CodingProblem)
        .order_by(CodingProblem.id)
        .limit(CODING_ROUND_PROBLEMS_COUNT)
        .all()
    )
    # Eager load only non-hidden test cases
    for p in problems:
        p.test_cases = [t for t in p.test_cases if not t.is_hidden]
    return problems


def start_coding_round(db: Session, user_id: int) -> dict:
    """Create an active coding round for the user's active session and assign problems."""
    session = session_service.get_active_session(db, user_id)
    if session is None:
        # Allow coding round to be started directly from dashboard by creating a session.
        session = session_service.create_session(db, user_id=user_id)

    existing_active = session_service.get_user_active_round(db, user_id, round_type="coding")
    if existing_active is not None:
        assigned_existing = db.query(SessionProblem).filter(SessionProblem.round_id == existing_active.id).order_by(SessionProblem.problem_order.asc()).all()
        # If the round exists but has no assigned problems (e.g. started by practice router),
        # assign problems now so /run validation can succeed.
        if not assigned_existing:
            problems_to_assign = db.query(CodingProblem).order_by(func.random()).limit(CODING_ROUND_PROBLEMS_COUNT).all()
            assigned_existing = []
            for idx, p in enumerate(problems_to_assign, start=1):
                sp = SessionProblem(
                    round_id=existing_active.id,
                    problem_id=p.id,
                    problem_order=idx,
                    marked_for_review=False,
                    assigned_at=datetime.now(),
                )
                db.add(sp)
                assigned_existing.append(sp)
            db.commit()
            for sp in assigned_existing:
                db.refresh(sp)
        problems_existing = []
        for sp in assigned_existing:
            problem = db.query(CodingProblem).filter(CodingProblem.id == sp.problem_id).first()
            if problem is not None:
                problem.test_cases = [t for t in problem.test_cases if not t.is_hidden]
                problems_existing.append(problem)
        return {"round": existing_active, "assigned": assigned_existing, "problems": problems_existing}

    # Create round
    round_obj = session_service.create_round(db, session_id=session.id, round_type="coding")

    # Select random problems
    problems = db.query(CodingProblem).order_by(func.random()).limit(CODING_ROUND_PROBLEMS_COUNT).all()

    # Persist assignments
    assigned = []
    for idx, p in enumerate(problems, start=1):
        sp = SessionProblem(
            round_id=round_obj.id,
            problem_id=p.id,
            problem_order=idx,
            marked_for_review=False,
            assigned_at=datetime.now(),
        )
        db.add(sp)
        assigned.append(sp)

    db.commit()
    # Refresh to get ids
    for sp in assigned:
        db.refresh(sp)

    return {"round": round_obj, "assigned": assigned, "problems": problems}


def run_and_evaluate(
    db: Session,
    problem_id: int,
    code: str,
    language: str,
    visible_only: bool = True,
    round_id: Optional[int] = None,
) -> Dict[str, Any]:
    # Load test cases
    test_cases = (
        db.query(CodingTestCase)
        .filter(CodingTestCase.problem_id == problem_id)
        .order_by(CodingTestCase.case_order)
        .all()
    )
    if visible_only:
        test_cases = [t for t in test_cases if not t.is_hidden]

    result = evaluate_submission(code=code, language=language, test_cases=test_cases, visible_only=visible_only)

    status = result.get("status")
    if status not in {"running", "accepted", "wrong_answer", "runtime_error", "time_limit_exceeded", "compilation_error", "memory_limit_exceeded", "internal_error"}:
        status = "accepted" if (result.get("score") or 0) >= 1.0 else "wrong_answer"
    result["status"] = status

# If this is a full submit, persist a CodingSubmission row
    if not visible_only:
        if round_id is None:
            raise ValueError("round_id is required for submissions")
        
        submission = CodingSubmission(
            round_id=round_id,
            problem_id=problem_id,
            code=code,
            language=language,
            judge0_token=result.get("judge0_token"),
            status=result.get("status"),
            score=result.get("score"),
            execution_time=result.get("execution_time"),
            memory_used=result.get("memory_used"),
        )
        db.add(submission)
        db.commit()
        db.refresh(submission)
        result["submission_id"] = submission.id

    return result


def finalize_coding_round(db: Session, round_id: int) -> float:
    """Compute best submission per assigned problem for the round and update round/session scores.

    Returns the computed round score (0..1).
    """
    # Get assigned problems
    assigned = db.query(SessionProblem).filter(SessionProblem.round_id == round_id).all()
    if not assigned:
        # No problems assigned — still mark the round completed so result endpoint works
        rnd = db.query(AssessmentRound).filter(AssessmentRound.id == round_id).first()
        if rnd and rnd.status != "completed":
            rnd.score = 0.0
            rnd.status = "completed"
            rnd.completed_at = datetime.utcnow()
            db.commit()
        return 0.0

    best_scores = []
    for sp in assigned:
        best = (
            db.query(func.max(CodingSubmission.score))
            .filter(CodingSubmission.round_id == round_id, CodingSubmission.problem_id == sp.problem_id)
            .scalar()
        )
        best_scores.append(float(best or 0.0))

    round_score = sum(best_scores) / len(best_scores) if best_scores else 0.0

    # Update round record
    rnd = db.query(AssessmentRound).filter(AssessmentRound.id == round_id).first()

    if rnd:
        # Idempotent: only update if not already completed
        if rnd.status != "completed":
            rnd.score = round_score
            rnd.status = "completed"
            rnd.completed_at = datetime.utcnow()
            db.commit()

            # Update session total as average of completed rounds
            session_id = rnd.session_id
            completed_scores = (
                db.query(func.avg(AssessmentRound.score))
                .filter(AssessmentRound.session_id == session_id, AssessmentRound.status == "completed")
                .scalar()
            )
            sess = db.query(AssessmentSession).filter(AssessmentSession.id == session_id).first()
            if sess:
                sess.total_score = float(completed_scores or 0.0)
                db.commit()

            # M2-E: Do NOT auto-create interview round.
            # Practice uses independent progression — the user selects the next
            # round themselves from the dashboard. Auto-creating interview here
            # blocks the user from starting other round types (409 conflict).

    return round_score
