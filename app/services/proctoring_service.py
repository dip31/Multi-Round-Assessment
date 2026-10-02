"""
Business logic for proctoring event management.

Handles logging and retrieval of proctoring events for assessment sessions.
"""

from datetime import datetime
from typing import List

from sqlalchemy.orm import Session
from sqlalchemy import inspect

from app.models.proctoring import ProctoringEvent


def log_proctoring_event(
    db: Session,
    session_id: int,
    event_type: str,
    event_metadata: dict | None = None,
) -> ProctoringEvent:
    """Log a new proctoring event for an assessment session.

    Args:
        db: Active database session.
        session_id: ID of the assessment session.
        event_type: Type of proctoring event (e.g., "tab_switch", "fullscreen_exit").
        event_metadata: Optional additional event data.

    Returns:
        The created ProctoringEvent instance.
    """
    event = ProctoringEvent(
        session_id=session_id,
        event_type=event_type,
    )
    event.metadata_dict = event_metadata
    
    db.add(event)
    db.commit()
    db.refresh(event)
    
    return event


def get_session_proctoring_events(
    db: Session,
    session_id: int,
) -> List[ProctoringEvent]:
    """Retrieve all proctoring events for a specific session.

    Args:
        db: Active database session.
        session_id: ID of the assessment session.

    Returns:
        List of ProctoringEvent instances ordered by creation time.
    """
    return (
        db.query(ProctoringEvent)
        .filter(ProctoringEvent.session_id == session_id)
        .order_by(ProctoringEvent.created_at.asc())
        .all()
    )


def get_event_count_by_type(
    db: Session,
    session_id: int,
    event_type: str,
) -> int:
    """Count occurrences of a specific event type in a session.

    Args:
        db: Active database session.
        session_id: ID of the assessment session.
        event_type: Type of event to count.

    Returns:
        Number of occurrences of the specified event type.
    """
    return (
        db.query(ProctoringEvent)
        .filter(
            ProctoringEvent.session_id == session_id,
            ProctoringEvent.event_type == event_type,
        )
        .count()
    )


def stop_proctoring_session(db: Session, session_id: int) -> ProctoringEvent | None:
    """Persist the terminal proctoring event for an assessment session.

    The event is idempotent so every completion path can safely call it.
    """
    # Some lightweight migration/test databases omit optional proctoring tables.
    # Assessment completion must remain usable there; deployed schemas persist
    # the terminal event below.
    if db.bind is None or not inspect(db.bind).has_table("proctoring_events"):
        return None

    existing = (
        db.query(ProctoringEvent)
        .filter(
            ProctoringEvent.session_id == session_id,
            ProctoringEvent.event_type == "PROCTORING_STOPPED",
        )
        .order_by(ProctoringEvent.id.desc())
        .first()
    )
    if existing is not None:
        return existing
    return log_proctoring_event(
        db,
        session_id,
        "PROCTORING_STOPPED",
        {"stopped_at": datetime.utcnow().isoformat()},
    )
