"""
Business logic for assessment sessions and rounds.

Provides the full session lifecycle: creation → round management → completion.

This service handles ONLY session-level operations. Module-specific logic
(aptitude, coding, interview) should be in their respective module services.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from shared.db.assessment import AssessmentRound, AssessmentSession


# ── Constants ─────────────────────────────────────────────────────────
SESSION_TIMEOUT_MINUTES: int = 30


# ── Session operations ────────────────────────────────────────────────

from sqlalchemy import text

def _expire_stale_session(db: Session, user_id: int) -> None:
    """Auto-close any in_progress session that has exceeded the timeout.

    This ensures stale sessions (e.g. user left without completing) are
    cleaned up automatically so a new session can be started.
    """
    cutoff = text(f"NOW() - INTERVAL '{SESSION_TIMEOUT_MINUTES} minutes'")

    stale = (
        db.query(AssessmentSession)
        .filter(
            AssessmentSession.user_id == user_id,
            AssessmentSession.status == "in_progress",
            AssessmentSession.started_at < cutoff,
        )
        .all()
    )

    for s in stale:
        s.status = "expired"
        s.completed_at = datetime.now(timezone.utc)

    if stale:
        # Also close any active rounds in those sessions
        stale_ids = [s.id for s in stale]
        db.query(AssessmentRound).filter(
            AssessmentRound.session_id.in_(stale_ids),
            AssessmentRound.status == "active",
        ).update(
            {"status": "expired", "completed_at": datetime.now(timezone.utc)},
            synchronize_session="fetch",
        )
        db.commit()


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

    Automatically expires sessions older than ``SESSION_TIMEOUT_MINUTES``.

    Returns:
        The ``AssessmentSession`` if one is active, otherwise ``None``.
    """
    # Clean up stale sessions first
    _expire_stale_session(db, user_id)

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


def get_user_active_round(
    db: Session,
    user_id: int,
    round_type: str = "aptitude",
) -> Optional[AssessmentRound]:
    """Return the active round of *round_type* for a user's in-progress session.

    Chains: user_id → active session → active round of the given type.

    Args:
        db: Active database session.
        user_id: The authenticated user's ID.
        round_type: ``aptitude``, ``coding``, or ``interview``.

    Returns:
        The ``AssessmentRound`` if found, otherwise ``None``.
    """
    active_session = get_active_session(db, user_id)
    if active_session is None:
        return None

    return (
        db.query(AssessmentRound)
        .filter(
            AssessmentRound.session_id == active_session.id,
            AssessmentRound.round_type == round_type,
            AssessmentRound.status == "active",
        )
        .first()
    )


