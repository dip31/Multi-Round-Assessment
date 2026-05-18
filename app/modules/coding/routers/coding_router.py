"""
Coding Round Router

HTTP endpoints for the AMCAT-style coding assessment round.
Zero business logic — all logic lives in coding_service and session_service.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.database.db import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.schemas.coding import (
    StartRoundResponse, SessionStatusResponse, SessionResultResponse,
    CodingProblemListResponse, CodingProblemDetailResponse,
    RunCodeRequest, RunCodeResponse,
    SubmitCodeRequest, SubmitCodeResponse,
    SubmissionHistoryItem, MarkReviewResponse
)
from app.modules.coding.services import coding_service, session_service

router = APIRouter(prefix="/coding", tags=["Coding Assessment (Round 2)"])


# ── SESSION MANAGEMENT ────────────────────────────────────────────────────────

@router.post("/start-round", response_model=StartRoundResponse,
             status_code=201)
def start_round(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Start coding round. Assigns 3 random problems. Begins 90-min timer.
    Can only be called once per session.
    """
    return session_service.start_coding_round(db, current_user.id)
@router.post("/restart-round", response_model=StartRoundResponse,
             status_code=201)
def restart_round(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Restart coding round. Resets completed/active round and assigns new problems.
    Allows users to take the assessment again with fresh problems.
    """
    return session_service.restart_coding_round(db, current_user.id)



@router.get("/session/{round_id}", response_model=SessionStatusResponse)
def get_session(
    round_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Live session status with countdown and per-problem statuses.
    Frontend polls this to update timer and color-coded problem list.
    """
    return session_service.get_session_status(db, round_id, current_user.id)


@router.post("/session/{round_id}/end",
             response_model=SessionResultResponse)
def end_round(
    round_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Manually end the coding round. Calculates final score."""
    return session_service.end_coding_round(db, round_id, current_user.id)


@router.get("/session/{round_id}/result",
            response_model=SessionResultResponse)
def get_result(
    round_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Final result after round is completed."""
    return session_service.get_session_result(db, round_id, current_user.id)


# ── PROBLEMS ──────────────────────────────────────────────────────────────────

@router.get("/problems/{round_id}",
            response_model=List[CodingProblemListResponse])
def get_problems(
    round_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List only problems assigned to this candidate's session.
    Each problem shows status (not_attempted/attempted/accepted)
    and marked_for_review flag for frontend color coding.
    """
    return coding_service.get_assigned_problems(db, round_id, current_user.id)


@router.get("/problem/{round_id}/{problem_id}",
            response_model=CodingProblemDetailResponse)
def get_problem(
    round_id: int,
    problem_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Full problem details with visible test cases only.
    Hidden test cases are NEVER returned.
    """
    return coding_service.get_problem_detail(
        db, round_id, problem_id, current_user.id)


# ── CODE EXECUTION ────────────────────────────────────────────────────────────

@router.post("/run", response_model=RunCodeResponse)
def run_code(
    body: RunCodeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Run code against visible test cases only.
    Does NOT affect score. Used for the Run Code button.
    """
    return coding_service.run_code(
        db=db,
        round_id=body.round_id,
        problem_id=body.problem_id,
        code=body.code,
        language=body.language,
        user_id=current_user.id
    )


@router.post("/submit", response_model=SubmitCodeResponse, status_code=200)
def submit_code(
    body: SubmitCodeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Submit code against ALL test cases including hidden ones.
    Returns full verdict, score, and pass/fail counts immediately.
    Submission stored in database. Rejected if time expired.
    """
    return coding_service.submit_code(
        db=db,
        round_id=body.round_id,
        problem_id=body.problem_id,
        code=body.code,
        language=body.language,
        user_id=current_user.id
    )


# ── SUBMISSION HISTORY & REVIEW ───────────────────────────────────────────────

@router.get("/submissions/{round_id}/{problem_id}",
            response_model=List[SubmissionHistoryItem])
def get_submission_history(
    round_id: int,
    problem_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """All submissions for a problem. Most recent first.
    Best score counts for final round score.
    """
    return coding_service.get_submission_history(
        db, round_id, problem_id, current_user.id)


@router.post("/problem/{round_id}/{problem_id}/mark-review",
             response_model=MarkReviewResponse)
def mark_for_review(
    round_id: int,
    problem_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Toggle mark-for-review on a problem.
    Frontend shows purple indicator when marked.
    """
    sp = session_service.toggle_mark_for_review(
        db, round_id, problem_id, current_user.id)
    return {
        "problem_id": problem_id,
        "marked_for_review": sp.marked_for_review,
        "message": (
            "Marked for review" if sp.marked_for_review
            else "Review mark removed"
        )
    }
