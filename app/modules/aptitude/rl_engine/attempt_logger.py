"""
Attempt Logger — writes one row to ``rl_attempt_log`` per question attempt.

Non-blocking: if logging fails it logs a warning but never crashes the
main request.  This data feeds the future DQN replay buffer.
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.rl import RLAttemptLog
from app.modules.aptitude.rl_engine.q_table_store import Action

logger = logging.getLogger(__name__)


def log_attempt(
    user_id: int,
    session_id: int,
    question_id: int,
    difficulty: str,
    state_before: str,
    action_taken: Action,
    reward: float,
    state_after: str,
    response_time: float,
    is_correct: bool,
    db: Session,
) -> None:
    """Record a complete RL step in the audit log.

    Wraps the insert in ``try/except`` — a logging failure must **never**
    propagate to the student's request.

    Args:
        user_id: Authenticated user ID.
        session_id: Current assessment session ID.
        question_id: The question that was answered.
        difficulty: Difficulty of the answered question.
        state_before: Serialized RL state *before* the attempt.
        action_taken: The RL action that was selected.
        reward: Computed reward for this attempt.
        state_after: Serialized RL state *after* the attempt.
        response_time: Seconds the student took.
        is_correct: Whether the answer was correct.
        db: Active SQLAlchemy session.
    """
    try:
        entry = RLAttemptLog(
            user_id=user_id,
            session_id=session_id,
            question_id=question_id,
            difficulty=difficulty,
            state_before=state_before,
            action_taken=action_taken.value,
            reward=reward,
            state_after=state_after,
            response_time=response_time,
            is_correct=is_correct,
        )
        db.add(entry)
        # Caller commits — we just add to the session
    except Exception:
        logger.warning(
            "Failed to log RL attempt for user_id=%s, question_id=%s",
            user_id,
            question_id,
            exc_info=True,
        )
