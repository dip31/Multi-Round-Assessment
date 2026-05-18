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
from app.services.session_service import create_session, get_active_session

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
    """Create a new assessment session for the authenticated user.
    
    If an active session exists, returns it.
    If no active session exists, creates a new one.
    This allows users to continue their session or start fresh after completion.
    """
    existing = get_active_session(db, user_id=current_user.id)
    if existing:
        # Return existing active session
        return existing

    # Create new session
    session = create_session(db, user_id=current_user.id)
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

    Raises:
        HTTPException (404): If no active session exists.
    """
    session = get_active_session(db, user_id=current_user.id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active session found",
        )

    return session


@router.post(
    "/restart",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Restart assessment - terminate old session and create new one",
)
def restart_session(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionResponse:
    """Terminate any existing active session and create a fresh new one.
    
    This allows users to start completely fresh rounds.
    The old session will be marked as 'terminated'.
    """
    # Terminate any existing active session
    existing = get_active_session(db, user_id=current_user.id)
    if existing:
        existing.status = "terminated"
        existing.completed_at = datetime.now(timezone.utc)
        # Also terminate all active rounds
        for round in existing.rounds:
            if round.status in ["pending", "active"]:
                round.status = "terminated"
                round.completed_at = datetime.now(timezone.utc)
        db.commit()

    # Create new session
    session = create_session(db, user_id=current_user.id)
    return session
