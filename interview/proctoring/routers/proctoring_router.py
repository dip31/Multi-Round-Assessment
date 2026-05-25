"""
Proctoring module routers.

Handles API endpoints for logging and retrieving proctoring events
during assessment sessions.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.database.db import get_db
from app.models.user import User
from app.schemas.proctoring import ProctorEventRequest, ProctorEventResponse
from app.services.proctoring_service import log_proctoring_event, get_session_proctoring_events

router = APIRouter(prefix="/proctoring", tags=["Proctoring"])


@router.post(
    "/log-event",
    response_model=ProctorEventResponse,
    summary="Log a proctoring event",
)
def log_proctoring_event_endpoint(
    payload: ProctorEventRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProctorEventResponse:
    """Log a new proctoring event for the authenticated user's session.
    
    This endpoint records suspicious behavior or policy violations during
    assessment sessions for later administrative review.
    
    Args:
        payload: Event data including session_id, event_type, and optional metadata.
        db: Active database session.
        current_user: Authenticated user making the request.
    
    Returns:
        Confirmation that the event was logged successfully.
    
    Raises:
        HTTPException (404): If the session doesn't exist or doesn't belong to the user.
    """
    # Verify the session belongs to the authenticated user
    from app.models.assessment import AssessmentSession
    
    session = db.query(AssessmentSession).filter(
        AssessmentSession.id == payload.session_id,
        AssessmentSession.user_id == current_user.id,
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or access denied",
        )
    
    # Log the event
    event = log_proctoring_event(
        db=db,
        session_id=payload.session_id,
        event_type=payload.event_type,
        event_metadata=payload.event_metadata,
    )
    
    return ProctorEventResponse(
        status="logged",
        event_id=event.id,
    )


@router.get(
    "/events/{session_id}",
    summary="Get all proctoring events for a session",
)
def get_proctoring_events(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Retrieve all proctoring events for a specific session.
    
    This endpoint is primarily for administrative review of candidate behavior.
    
    Args:
        session_id: ID of the assessment session.
        db: Active database session.
        current_user: Authenticated user making the request.
    
    Returns:
        List of proctoring events with timestamps and metadata.
    
    Raises:
        HTTPException (404): If the session doesn't exist or doesn't belong to the user.
    """
    # Verify the session belongs to the authenticated user
    from app.models.assessment import AssessmentSession
    
    session = db.query(AssessmentSession).filter(
        AssessmentSession.id == session_id,
        AssessmentSession.user_id == current_user.id,
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or access denied",
        )
    
    events = get_session_proctoring_events(db, session_id)
    
    return [
        {
            "id": event.id,
            "event_type": event.event_type,
            "event_metadata": event.event_metadata,
            "created_at": event.created_at.isoformat(),
        }
        for event in events
    ]
