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
from app.services.assessment_service import create_session, get_active_session

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

    Raises:
        HTTPException (409): If the user already has an active session.
    """
    existing = get_active_session(db, user_id=current_user.id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active session already exists",
        )

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
