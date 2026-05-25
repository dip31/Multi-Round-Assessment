"""
Assessment session endpoints.

Handles session creation and status retrieval for the authenticated user.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from shared.db.database import SyncSessionLocal
from services.session_service import create_session, create_round, get_active_session

# Temporary auth bypass
class DummyUser:
    id = 1
    email = "admin@system.com"

def get_current_user():
    return DummyUser()

def get_sync_db():
    """Sync database session for compatibility with session_service."""
    db = SyncSessionLocal()
    try:
        yield db
    finally:
        db.close()

router = APIRouter(prefix="/session", tags=["Assessment Sessions"])


@router.post(
    "/start",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Start a new assessment session",
)
def start_session(
    db: Session = Depends(get_sync_db),
    current_user: DummyUser = Depends(get_current_user),
) -> dict:
    """Create a new assessment session and its first aptitude round.

    Raises:
        HTTPException (409): If the user already has an active session.
    """
    existing = get_active_session(db, user_id=current_user.id)
    if existing:
        return {"session_id": existing.id, "status": "active"}

    session = create_session(db, user_id=current_user.id)
    create_round(db, session_id=session.id, round_type="aptitude")
    db.refresh(session)
    return {"session_id": session.id, "status": "active"}


@router.get(
    "/status",
    response_model=dict,
    summary="Get the current active session",
)
def session_status(
    db: Session = Depends(get_sync_db),
    current_user: DummyUser = Depends(get_current_user),
) -> dict:
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

    return {"session_id": session.id, "status": session.status}
