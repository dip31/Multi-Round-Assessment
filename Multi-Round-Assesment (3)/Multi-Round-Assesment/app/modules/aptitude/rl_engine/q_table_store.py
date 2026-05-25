"""
Q-Table Store — PostgreSQL-backed Q-table read/write.

Provides per-user Q-value storage via the ``rl_q_table`` table.
All actions use the ``Action`` enum — never hardcode action strings.
"""

from enum import Enum
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.rl import RLQTable

# ── Actions enum — use everywhere ─────────────────────────────────────
class Action(str, Enum):
    """RL actions for difficulty adjustment."""
    INCREASE = "increase"
    SAME     = "same"
    DECREASE = "decrease"


# Optimistic default — encourages exploration of unseen state-action pairs
_DEFAULT_Q_VALUE: float = 0.1


def get_q_values(
    user_id: int,
    state_key: str,
    db: Session,
) -> dict[Action, float]:
    """Fetch Q-values for all 3 actions in a single query.

    If a ``(user_id, state, action)`` row doesn't exist, returns the
    optimistic default ``0.1`` for that action.

    Args:
        user_id: The authenticated user's ID.
        state_key: Serialized state string (e.g. ``"medium|2|0|fast|high"``).
        db: Active SQLAlchemy session.

    Returns:
        Dict mapping each ``Action`` to its Q-value.
    """
    rows = (
        db.query(RLQTable)
        .filter(
            RLQTable.user_id == user_id,
            RLQTable.state == state_key,
        )
        .all()
    )

    # Start with optimistic defaults
    q_values: dict[Action, float] = {a: _DEFAULT_Q_VALUE for a in Action}

    # Override with stored values
    for row in rows:
        try:
            action = Action(row.action)
            q_values[action] = row.q_value
        except ValueError:
            pass  # ignore unknown action strings in DB

    return q_values


def update_q_value(
    user_id: int,
    state_key: str,
    action: Action,
    new_q_value: float,
    db: Session,
) -> None:
    """Upsert a Q-value row, incrementing ``visit_count``.

    The caller is responsible for committing the transaction.

    Args:
        user_id: The authenticated user's ID.
        state_key: Serialized state string.
        action: The RL action to update.
        new_q_value: The new Q-value to store.
        db: Active SQLAlchemy session.
    """
    existing: Optional[RLQTable] = (
        db.query(RLQTable)
        .filter(
            RLQTable.user_id == user_id,
            RLQTable.state == state_key,
            RLQTable.action == action.value,
        )
        .first()
    )

    if existing:
        existing.q_value = new_q_value
        existing.visit_count = (existing.visit_count or 0) + 1
        existing.updated_at = datetime.now(timezone.utc)
    else:
        new_row = RLQTable(
            user_id=user_id,
            state=state_key,
            action=action.value,
            q_value=new_q_value,
            visit_count=1,
        )
        db.add(new_row)
