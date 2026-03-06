"""
Business logic for assessment sessions and rounds.

Provides the full session lifecycle: creation → round management → completion.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.assessment import AssessmentRound, AssessmentSession


# ── Session operations ────────────────────────────────────────────────

def create_session(db: Session, user_id: int) -> AssessmentSession:
    """Create a new assessment session for *user_id*.

    The session is initialised with status ``in_progress``.

    Returns:
        The newly created ``AssessmentSession``.
    """
    session = AssessmentSession(
        user_id=user_id,
        status="in_progress",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_active_session(db: Session, user_id: int) -> Optional[AssessmentSession]:
    """Return the currently active (``in_progress``) session for *user_id*.

    Returns:
        The ``AssessmentSession`` if one is active, otherwise ``None``.
    """
    return (
        db.query(AssessmentSession)
        .filter(
            AssessmentSession.user_id == user_id,
            AssessmentSession.status == "in_progress",
        )
        .first()
    )


def complete_session(db: Session, session_id: int) -> Optional[AssessmentSession]:
    """Mark an assessment session as ``completed`` and set *completed_at*.

    Returns:
        The updated ``AssessmentSession``, or ``None`` if not found.
    """
    session = (
        db.query(AssessmentSession)
        .filter(AssessmentSession.id == session_id)
        .first()
    )
    if session is None:
        return None

    session.status = "completed"
    session.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return session


# ── Round operations ──────────────────────────────────────────────────

def create_round(
    db: Session,
    session_id: int,
    round_type: str,
) -> AssessmentRound:
    """Create a new round of *round_type* within the given session.

    The round is initialised with status ``active``.

    Returns:
        The newly created ``AssessmentRound``.
    """
    assessment_round = AssessmentRound(
        session_id=session_id,
        round_type=round_type,
        status="active",
    )
    db.add(assessment_round)
    db.commit()
    db.refresh(assessment_round)
    return assessment_round


def get_active_round(db: Session, session_id: int) -> Optional[AssessmentRound]:
    """Return the currently active round for the given session.

    Returns:
        The ``AssessmentRound`` if one is active, otherwise ``None``.
    """
    return (
        db.query(AssessmentRound)
        .filter(
            AssessmentRound.session_id == session_id,
            AssessmentRound.status == "active",
        )
        .first()
    )


def end_round(db: Session, round_id: int) -> Optional[AssessmentRound]:
    """Mark a round as ``completed`` and set *completed_at*.

    Returns:
        The updated ``AssessmentRound``, or ``None`` if not found.
    """
    assessment_round = (
        db.query(AssessmentRound)
        .filter(AssessmentRound.id == round_id)
        .first()
    )
    if assessment_round is None:
        return None

    assessment_round.status = "completed"
    assessment_round.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(assessment_round)
    return assessment_round
