"""
Coding Service

Problem fetching, run code, submit code, submission history.
All submissions validated through session_service.
"""

from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.coding import (
    CodingProblem, CodingTestCase, CodingSubmission, SessionProblem
)
from app.modules.coding.utils.judge0_client import LANGUAGE_MAP
from app.modules.coding.utils.code_evaluator import evaluate_submission
from app.modules.coding.services import session_service


def get_assigned_problems(db: Session, round_id: int,
                           user_id: int) -> list:
    """Return only problems assigned to candidate's session.

    Raises:
        HTTPException(400): Round not started yet (no assignments).
    """
    session_problems = (
        db.query(SessionProblem)
        .filter(SessionProblem.round_id == round_id)
        .order_by(SessionProblem.problem_order)
        .all()
    )
    if not session_problems:
        raise HTTPException(
            400,
            "Coding round not started. "
            "Call POST /api/v1/coding/start-round first."
        )

    return [
        {
            "id": sp.problem.id,
            "title": sp.problem.title,
            "difficulty": sp.problem.difficulty,
            "tags": sp.problem.tags or [],
            "problem_order": sp.problem_order,
            "status": session_service._get_problem_status(
                db, round_id, sp.problem_id),
            "marked_for_review": sp.marked_for_review
        }
        for sp in session_problems
    ]


def get_problem_detail(db: Session, round_id: int,
                        problem_id: int, user_id: int) -> dict:
    """Get full problem with visible test cases only.

    NEVER returns hidden test cases.

    Raises:
        HTTPException(403): Problem not in session or round not active.
        HTTPException(404): Problem not found.
    """
    session_service.validate_active_session(db, round_id, user_id, problem_id)

    problem = db.query(CodingProblem).filter(
        CodingProblem.id == problem_id
    ).first()
    if not problem:
        raise HTTPException(404, "Problem not found.")

    # ONLY visible test cases — hidden ones must never be exposed
    visible = (
        db.query(CodingTestCase)
        .filter(
            CodingTestCase.problem_id == problem_id,
            CodingTestCase.is_hidden == False      # noqa: E712
        )
        .order_by(CodingTestCase.case_order)
        .all()
    )

    return {
        "id": problem.id,
        "title": problem.title,
        "description": problem.description,
        "difficulty": problem.difficulty,
        "tags": problem.tags or [],
        "input_format": problem.input_format,
        "output_format": problem.output_format,
        "constraints": problem.constraints,
        "visible_test_cases": [
            {
                "id": tc.id,
                "input_data": tc.input_data,
                "expected_output": tc.expected_output,
                "case_order": tc.case_order
            }
            for tc in visible
        ]
    }


def run_code(db: Session, round_id: int, problem_id: int,
             code: str, language: str, user_id: int) -> dict:
    """Run code against visible test cases only. Does NOT store results.

    Used for the "Run Code" button — no effect on scoring.

    Raises:
        HTTPException(400): Unsupported language.
        HTTPException(403): Round not active or problem not assigned.
        HTTPException(404): No visible test cases found.
    """
    if language not in LANGUAGE_MAP:
        raise HTTPException(
            400, "Unsupported language. Allowed: python, cpp, java")

    session_service.validate_active_session(db, round_id, user_id, problem_id)

    language_id = LANGUAGE_MAP[language]

    # Only visible test cases for run
    visible_cases = (
        db.query(CodingTestCase)
        .filter(
            CodingTestCase.problem_id == problem_id,
            CodingTestCase.is_hidden == False      # noqa: E712
        )
        .order_by(CodingTestCase.case_order)
        .all()
    )
    if not visible_cases:
        raise HTTPException(404, "No visible test cases for this problem.")

    result = evaluate_submission(code, language_id, visible_cases)

    return {
        "results": [
            {
                "input_data":      r["input_data"],
                "expected_output": r["expected_output"],
                "actual_output":   r["actual_output"],
                "passed":          r["passed"]
            }
            for r in result["results"]
        ]
    }


def submit_code(db: Session, round_id: int, problem_id: int,
                code: str, language: str, user_id: int) -> dict:
    """Submit code against ALL test cases (visible + hidden).

    Stores result in coding_submissions table.
    Best submission per problem counts for final score.

    Raises:
        HTTPException(400): Unsupported language.
        HTTPException(403): Round not active, time expired,
                            or problem not in session.
        HTTPException(404): No test cases found.
    """
    if language not in LANGUAGE_MAP:
        raise HTTPException(
            400, "Unsupported language. Allowed: python, cpp, java")

    session_service.validate_active_session(db, round_id, user_id, problem_id)

    language_id = LANGUAGE_MAP[language]

    # Fetch ALL test cases — hidden + visible
    all_cases = (
        db.query(CodingTestCase)
        .filter(CodingTestCase.problem_id == problem_id)
        .order_by(CodingTestCase.case_order)
        .all()
    )
    if not all_cases:
        raise HTTPException(404, "No test cases found for this problem.")

    # Evaluate against all test cases via Judge0 (synchronous wait=true)
    eval_result = evaluate_submission(code, language_id, all_cases)

    # Store submission
    submission = CodingSubmission(
        round_id=round_id,
        problem_id=problem_id,
        code=code,
        language=language,
        status=eval_result["verdict"],
        score=eval_result["score"],
        execution_time=eval_result["execution_time"],
        memory_used=eval_result["memory_used"],
        submitted_at=datetime.utcnow()
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    return {
        "submission_id": submission.id,
        "verdict":       eval_result["verdict"],
        "score":         eval_result["score"],
        "passed_cases":  eval_result["passed_cases"],
        "total_cases":   eval_result["total_cases"],
        "execution_time": eval_result["execution_time"],
        "memory_used":   eval_result["memory_used"]
    }


def get_submission_history(db: Session, round_id: int,
                            problem_id: int,
                            user_id: int) -> list:
    """Return all submissions for a problem in this round.

    Most recent submission first.
    """
    submissions = (
        db.query(CodingSubmission)
        .filter(
            CodingSubmission.round_id == round_id,
            CodingSubmission.problem_id == problem_id
        )
        .order_by(CodingSubmission.submitted_at.desc())
        .all()
    )
    return [
        {
            "submission_id": s.id,
            "status":        s.status,
            "score":         s.score,
            "submitted_at":  s.submitted_at
        }
        for s in submissions
    ]
