"""
Assessment session endpoints.

Handles session creation and status retrieval for the authenticated user.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.database.db import get_db
from app.models.user import User
from app.schemas.assessment import SessionResponse
from app.services.session_service import create_session, create_round, get_active_session, complete_session, end_round, get_user_active_round

router = APIRouter(prefix="/session", tags=["Assessment Sessions"])


@router.post(
    "/start",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a new assessment session",
)
def start_session(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionResponse:
    """Create a new assessment session and its first aptitude round.

    Raises:
        HTTPException (409): If the user already has an active session.
    """
    existing = get_active_session(db, user_id=current_user.id)
    if existing:
        # Return the existing session with 200 instead of 409
        # This prevents console errors while maintaining idempotency
        return existing

    session = create_session(db, user_id=current_user.id)

    # Auto-create the first round (aptitude)
    create_round(db, session_id=session.id, round_type="aptitude")

    # Refresh to include the new round in the response
    db.refresh(session)
    return session


@router.get(
    "/status",
    response_model=SessionResponse,
    summary="Get the current active session",
)
def session_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionResponse:
    """Return the active assessment session for the authenticated user.

    If no active session exists, return an empty/default session payload
    so frontend dashboards can render without noisy 404s.
    """
    session = get_active_session(db, user_id=current_user.id)
    if session is None:
        return SessionResponse(
            id=0,
            user_id=current_user.id,
            status="not_started",
            total_score=0,
            time_remaining_seconds=1800,
            rounds=[],
        )

    return session


@router.post(
    "/complete",
    response_model=SessionResponse,
    summary="Complete the current active session",
)
def complete_current_session(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionResponse:
    """Mark the current active session and round as completed."""
    session = get_active_session(db, user_id=current_user.id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active session found")

    active_round = get_user_active_round(db, current_user.id, round_type="aptitude")
    if active_round is not None:
        end_round(db, active_round.id)

    completed_session = complete_session(db, session.id)
    if completed_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active session found")

    return completed_session
