"""
Practice Result Service — EDI5 M2-D

Reads persisted evaluation data to produce historical result summaries
and detailed question-by-question reviews for completed practice rounds.

Design rules:
- NEVER recalculates correctness; reads persisted is_correct / score.
- Uses relational joins to AptitudeQuestion for question text (no snapshots).
- Ownership is enforced at the router layer; this service trusts its callers.
- Returns dicts suitable for direct JSON serialization by FastAPI.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.aptitude import AptitudeAttempt, AptitudeQuestion
from app.models.assessment import AssessmentRound, AssessmentSession
from app.models.coding import CodingProblem, CodingSubmission
from app.models.interview import InterviewSession, InterviewTurn
from app.models.session_problem import SessionProblem


# ── Result Summary ────────────────────────────────────────────────────


def get_round_result_summary(
    db: Session,
    session_id: int,
    round_id: int,
) -> Optional[dict[str, Any]]:
    """Build the common result contract for one historical round.

    Returns None if the round doesn't exist or isn't completed.
    """
    assessment_round = (
        db.query(AssessmentRound)
        .filter(
            AssessmentRound.id == round_id,
            AssessmentRound.session_id == session_id,
        )
        .first()
    )
    if assessment_round is None:
        return None
    if assessment_round.status != "completed":
        return None

    round_type = assessment_round.round_type
    base = {
        "session_id": session_id,
        "round_id": round_id,
        "round_type": round_type,
        "status": assessment_round.status,
        "completed_at": assessment_round.completed_at.isoformat() if assessment_round.completed_at else None,
        "review_available": True,
    }

    # Aptitude-family round types share the same attempt model.
    if round_type in ("aptitude", "mcq", "technical", "combined"):
        return {**base, **_aptitude_result_summary(db, round_id)}
    elif round_type == "coding":
        return {**base, **_coding_result_summary(db, round_id)}
    elif round_type == "interview":
        return {**base, **_interview_result_summary(db, session_id)}
    else:
        # Unknown round type — return the base with the persisted score.
        base["score"] = float(assessment_round.score or 0)
        base["max_score"] = float(assessment_round.max_questions or 0)
        base["percentage"] = 0.0
        return base


def _aptitude_result_summary(db: Session, round_id: int) -> dict[str, Any]:
    """Aggregate counts from AptitudeAttempt for one round."""
    attempts = (
        db.query(AptitudeAttempt)
        .filter(AptitudeAttempt.round_id == round_id)
        .all()
    )
    total = len(attempts)
    correct = sum(1 for a in attempts if a.is_correct is True)
    # Incorrect: has a selected_option AND is_correct is False.
    incorrect = sum(
        1 for a in attempts
        if a.selected_option is not None and a.is_correct is False
    )
    # Skipped: selected_option is None (question was presented but not answered).
    skipped = sum(1 for a in attempts if a.selected_option is None)
    percentage = round((correct / total) * 100, 1) if total > 0 else 0.0

    return {
        "score": correct,
        "max_score": total,
        "percentage": percentage,
        "correct_count": correct,
        "incorrect_count": incorrect,
        "skipped_count": skipped,
    }


def _coding_result_summary(db: Session, round_id: int) -> dict[str, Any]:
    """Aggregate from CodingSubmission for one round."""
    assigned = (
        db.query(SessionProblem)
        .filter(SessionProblem.round_id == round_id)
        .all()
    )
    total_problems = len(assigned)

    best_scores: list[float] = []
    for sp in assigned:
        best = (
            db.query(func.max(CodingSubmission.score))
            .filter(
                CodingSubmission.round_id == round_id,
                CodingSubmission.problem_id == sp.problem_id,
            )
            .scalar()
        )
        best_scores.append(float(best or 0.0))

    total_score = sum(best_scores)
    max_score = float(total_problems)  # Each problem max score is 1.0
    percentage = round((total_score / max_score) * 100, 1) if max_score > 0 else 0.0

    return {
        "score": round(total_score, 2),
        "max_score": max_score,
        "percentage": percentage,
        "problems_attempted": total_problems,
        "problems_solved": sum(1 for s in best_scores if s >= 1.0),
    }


def _interview_result_summary(db: Session, session_id: int) -> dict[str, Any]:
    """Aggregate from InterviewTurn for one session's interview."""
    interview = (
        db.query(InterviewSession)
        .filter(InterviewSession.session_id == session_id)
        .order_by(InterviewSession.id.desc())
        .first()
    )
    if interview is None:
        return {
            "score": 0.0,
            "max_score": 0.0,
            "percentage": 0.0,
            "total_turns": 0,
            "average_content_score": 0.0,
            "average_final_score": 0.0,
        }

    turns = (
        db.query(InterviewTurn)
        .filter(InterviewTurn.interview_id == interview.id)
        .order_by(InterviewTurn.turn_number.asc())
        .all()
    )
    total_turns = len(turns)
    scored_turns = [t for t in turns if t.final_score is not None]

    if scored_turns:
        avg_content = sum(t.content_score or 0 for t in scored_turns) / len(scored_turns)
        avg_final = sum(t.final_score or 0 for t in scored_turns) / len(scored_turns)
    else:
        avg_content = 0.0
        avg_final = 0.0

    # Normalize to 0-100 scale (scores are typically 0-10).
    percentage = round(avg_final * 10, 1) if avg_final else 0.0

    return {
        "score": round(avg_final, 2),
        "max_score": 10.0,
        "percentage": min(percentage, 100.0),
        "total_turns": total_turns,
        "average_content_score": round(avg_content, 2),
        "average_final_score": round(avg_final, 2),
    }


# ── Detailed Review ───────────────────────────────────────────────────


def get_round_detailed_review(
    db: Session,
    session_id: int,
    round_id: int,
) -> Optional[dict[str, Any]]:
    """Build the detailed review payload for one historical round.

    Returns None if the round doesn't exist or isn't completed.
    """
    assessment_round = (
        db.query(AssessmentRound)
        .filter(
            AssessmentRound.id == round_id,
            AssessmentRound.session_id == session_id,
        )
        .first()
    )
    if assessment_round is None:
        return None
    if assessment_round.status != "completed":
        return None

    round_type = assessment_round.round_type
    base = {
        "session_id": session_id,
        "round_id": round_id,
        "round_type": round_type,
    }

    if round_type in ("aptitude", "mcq", "technical", "combined"):
        return {**base, **_aptitude_detailed_review(db, round_id)}
    elif round_type == "coding":
        return {**base, **_coding_detailed_review(db, round_id)}
    elif round_type == "interview":
        return {**base, **_interview_detailed_review(db, session_id)}
    else:
        return base


def _aptitude_detailed_review(db: Session, round_id: int) -> dict[str, Any]:
    """Question-by-question review from persisted AptitudeAttempt data."""
    attempts = (
        db.query(AptitudeAttempt)
        .options(
            joinedload(AptitudeAttempt.question).joinedload(AptitudeQuestion.topic)
        )
        .filter(AptitudeAttempt.round_id == round_id)
        .order_by(AptitudeAttempt.attempt_number.asc())
        .all()
    )

    items = []
    for a in attempts:
        q = a.question
        topic_name = None
        if q and q.topic:
            topic_name = q.topic.name

        items.append({
            "sequence": a.attempt_number,
            "question_id": a.question_id,
            "question_text": q.question_text if q else "[Question unavailable]",
            "options": {
                "A": q.option_a if q else "",
                "B": q.option_b if q else "",
                "C": q.option_c if q else "",
                "D": q.option_d if q else "",
            } if q else {},
            "selected_option": a.selected_option,
            "correct_option": q.correct_option if q else None,
            "is_correct": bool(a.is_correct) if a.is_correct is not None else None,
            "marks_obtained": 1 if a.is_correct else 0,
            "max_marks": 1,
            "explanation": None,  # AptitudeQuestion doesn't have an explanation column
            "topic": topic_name,
            "difficulty": a.difficulty or (q.difficulty if q else "medium"),
            "response_time": float(a.response_time) if a.response_time is not None else None,
        })

    return {
        "total_questions": len(items),
        "items": items,
    }


def _coding_detailed_review(db: Session, round_id: int) -> dict[str, Any]:
    """Problem-by-problem review from persisted CodingSubmission data."""
    assigned = (
        db.query(SessionProblem)
        .filter(SessionProblem.round_id == round_id)
        .order_by(SessionProblem.problem_order.asc())
        .all()
    )

    items = []
    for sp in assigned:
        problem = db.query(CodingProblem).filter(CodingProblem.id == sp.problem_id).first()

        # Get the best submission for this problem in this round.
        best_submission = (
            db.query(CodingSubmission)
            .filter(
                CodingSubmission.round_id == round_id,
                CodingSubmission.problem_id == sp.problem_id,
            )
            .order_by(CodingSubmission.score.desc().nullslast())
            .first()
        )

        # Get all submissions for this problem in this round.
        all_submissions = (
            db.query(CodingSubmission)
            .filter(
                CodingSubmission.round_id == round_id,
                CodingSubmission.problem_id == sp.problem_id,
            )
            .order_by(CodingSubmission.submitted_at.asc())
            .all()
        )

        items.append({
            "sequence": sp.problem_order,
            "problem_id": sp.problem_id,
            "problem_title": problem.title if problem else "[Problem unavailable]",
            "problem_difficulty": problem.difficulty if problem else None,
            "best_score": float(best_submission.score) if best_submission and best_submission.score is not None else 0.0,
            "best_status": best_submission.status if best_submission else "not_submitted",
            "language": best_submission.language if best_submission else None,
            "execution_time": float(best_submission.execution_time) if best_submission and best_submission.execution_time is not None else None,
            "memory_used": best_submission.memory_used if best_submission else None,
            "submission_count": len(all_submissions),
        })

    return {
        "total_problems": len(items),
        "items": items,
    }


def _interview_detailed_review(db: Session, session_id: int) -> dict[str, Any]:
    """Turn-by-turn review from persisted InterviewTurn data."""
    interview = (
        db.query(InterviewSession)
        .filter(InterviewSession.session_id == session_id)
        .order_by(InterviewSession.id.desc())
        .first()
    )
    if interview is None:
        return {"total_turns": 0, "items": []}

    turns = (
        db.query(InterviewTurn)
        .filter(InterviewTurn.interview_id == interview.id)
        .order_by(InterviewTurn.turn_number.asc())
        .all()
    )

    items = []
    for t in turns:
        items.append({
            "sequence": t.turn_number,
            "question_text": t.question_text,
            "question_difficulty": t.question_difficulty,
            "candidate_response": t.candidate_response,
            "content_score": float(t.content_score) if t.content_score is not None else None,
            "final_score": float(t.final_score) if t.final_score is not None else None,
            "intent": t.intent,
            "is_followup": t.is_followup,
            "response_time_sec": float(t.response_time_sec) if t.response_time_sec is not None else None,
        })

    return {
        "total_turns": len(items),
        "interview_status": interview.status,
        "completion_reason": interview.completion_reason,
        "items": items,
    }
