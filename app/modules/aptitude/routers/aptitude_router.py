"""
Aptitude Router

Handles all HTTP endpoints related to the Aptitude Round.

Responsibilities:
- Fetch next aptitude question (RL-driven difficulty)
- Submit answer with adaptive difficulty selection
 - Return round result summary

Each endpoint resolves the user's active aptitude round from their
session, ensuring per-user isolation of attempts and scores.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.aptitude import AptitudeAttempt
from app.services.session_service import get_user_active_round, get_active_session

from app.modules.aptitude.schemas.aptitude_schema import (
    NextQuestionResponse,
    SubmitAnswerRequest,
    SubmitAnswerResponse,
    RoundResultResponse,
)

from app.modules.aptitude.services.aptitude_service import (
    get_next_question,
    get_current_difficulty,
    submit_answer_and_adapt,
    get_latest_completed_aptitude_result,
)

router = APIRouter(
    prefix="/aptitude",
    tags=["Aptitude Round"],
)


def _require_active_round(db: Session, user_id: int):
    """Return the user's active aptitude round or raise 404."""
    active_round = get_user_active_round(db, user_id, round_type="aptitude")
    if active_round is None:
        raise HTTPException(
            status_code=404,
            detail="No active aptitude round. Start a session first via POST /api/v1/session/start",
        )
    return active_round


@router.get("/next-question", response_model=NextQuestionResponse)
def next_question(
    practice_type: Optional[str] = Query(None, description="mcq | technical | combined"),
    subject: Optional[str] = Query(None, description="OS | CN | OOPS | DBMS | DSA | all"),
    topic: Optional[str] = Query(None, description="Specific topic name"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Fetch the next aptitude/practice question for authenticated user.

    Supports practice_type: 'mcq' (Aptitude), 'technical' (CS fundamentals with subject filter),
    or 'combined' (50% Aptitude + 50% Technical).
    """
    active_round = _require_active_round(db, current_user.id)
    
    # Get current difficulty from RL session, default to medium for first question
    current_difficulty = get_current_difficulty(db, active_round.id, current_user.id)
    
    # Check attempts already in this round to prevent duplicate questions
    attempted_ids = [
        row[0]
        for row in db.query(AptitudeAttempt.question_id)
        .filter(AptitudeAttempt.round_id == active_round.id)
        .all()
    ]
    is_combined_turn = (len(attempted_ids) % 2 == 1) if practice_type == "combined" else None

    question = get_next_question(
        db,
        difficulty=current_difficulty,
        practice_type=practice_type,
        subject=subject,
        topic=topic,
        exclude_ids=attempted_ids,
        is_combined_technical_turn=is_combined_turn,
    )

    if not question:
        raise HTTPException(
            status_code=404,
            detail="No aptitude questions available",
        )

    return question


@router.post("/submit-answer", response_model=SubmitAnswerResponse)
def submit_answer_endpoint(
    payload: SubmitAnswerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submit an answer and trigger RL-driven difficulty adaptation.

    Returns correctness, reward, next difficulty, and the next question
    pre-selected at the adapted difficulty level.
    """
    active_round = _require_active_round(db, current_user.id)
    active_session = get_active_session(db, current_user.id)

    result = submit_answer_and_adapt(
        db=db,
        user_id=current_user.id,
        session_id=active_session.id if active_session else 0,
        round_id=active_round.id,
        question_id=payload.question_id,
        selected_option=payload.selected_option,
        response_time=payload.response_time,
        practice_type=payload.practice_type,
        subject=payload.subject,
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Question not found",
        )
    return result


@router.get("/result", response_model=RoundResultResponse)
def get_round_result(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return summary statistics for the user's most recent completed aptitude session.
    """
    result = get_latest_completed_aptitude_result(db=db, user_id=current_user.id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="No completed aptitude session found",
        )

    return result