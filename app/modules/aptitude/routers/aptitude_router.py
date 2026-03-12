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

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.services.session_service import get_user_active_round, get_active_session

from app.modules.aptitude.schemas.aptitude_schema import (
    NextQuestionResponse,
    SubmitAnswerRequest,
    SubmitAnswerResponse,
    RoundResultResponse,
)

from app.modules.aptitude.services.aptitude_service import (
    get_next_question,
    submit_answer_and_adapt,
    calculate_round_result,
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Fetch the next aptitude question for the authenticated user.

    For the first question in a session, returns a medium-difficulty question.
    After submissions, difficulty is managed by the RL engine.
    """
    _require_active_round(db, current_user.id)

    question = get_next_question(db)

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
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Question not found",
        )

    return result


from app.services.session_service import end_round, complete_session

@router.get("/result", response_model=RoundResultResponse)
def get_round_result(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return summary statistics for the user's active aptitude round.
    Auto-closes the round and session once the result is fetched.
    """
    active_round = _require_active_round(db, current_user.id)

    result = calculate_round_result(
        db=db,
        round_id=active_round.id,
    )

    # Clean up so user can start a new session immediately
    end_round(db, active_round.id)
    complete_session(db, active_round.session_id)

    return result