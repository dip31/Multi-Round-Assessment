"""
Q-Learning — epsilon-greedy action selection and Q-value updates.

Uses the Bellman equation:
    Q(s,a) ← Q(s,a) + α · (r + γ · max Q(s',a') − Q(s,a))

Epsilon is stored per-user in memory and decays after each update.

# TODO: upgrade to DQN using rl_attempt_log replay buffer
"""

import random
from typing import Optional

from sqlalchemy.orm import Session

from app.modules.aptitude.rl_engine.q_table_store import (
    Action,
    get_q_values,
    update_q_value,
)

# ── Hyperparameters ───────────────────────────────────────────────────
ALPHA: float         = 0.1     # learning rate
GAMMA: float         = 0.9     # discount factor
# Make exploration more visible within a single 10-question round
EPSILON_START: float = 0.5     # initial exploration rate
EPSILON_MIN: float   = 0.1     # minimum exploration rate
EPSILON_DECAY: float = 0.999   # decay multiplier per step

# Per-user epsilon storage (in-memory, resets on server restart)
_user_epsilons: dict[int, float] = {}


def _get_epsilon(user_id: int) -> float:
    """Return the current epsilon for a user, initializing if needed."""
    return _user_epsilons.get(user_id, EPSILON_START)


def _decay_epsilon(user_id: int) -> None:
    """Decay epsilon for a user, clamping at ``EPSILON_MIN``."""
    current = _get_epsilon(user_id)
    _user_epsilons[user_id] = max(EPSILON_MIN, current * EPSILON_DECAY)


def select_action(
    user_id: int,
    state_key: str,
    db: Session,
) -> Action:
    """Choose an action using epsilon-greedy exploration.

    With probability ε, pick a random action (explore).
    Otherwise, pick the action with highest Q-value (exploit).

    Args:
        user_id: The authenticated user's ID.
        state_key: Serialized state string.
        db: Active SQLAlchemy session.

    Returns:
        The selected ``Action``.
    """
    epsilon = _get_epsilon(user_id)

    # Explore: random action
    if random.random() < epsilon:
        return random.choice(list(Action))

    # Exploit: best Q-value
    q_values = get_q_values(user_id, state_key, db)
    return max(q_values, key=q_values.get)  # type: ignore[arg-type]


def update_q_table(
    user_id: int,
    state_key: str,
    action: Action,
    reward: float,
    next_state_key: str,
    db: Session,
) -> None:
    """Update Q(s,a) using the Bellman equation and decay epsilon.

    Q(s,a) ← Q(s,a) + α · (reward + γ · max Q(s',a') − Q(s,a))

    The caller is responsible for committing the transaction.

    Args:
        user_id: The authenticated user's ID.
        state_key: Current state ``s``.
        action: Action taken ``a``.
        reward: Reward received ``r``.
        next_state_key: Next state ``s'``.
        db: Active SQLAlchemy session.
    """
    # Current Q(s, a)
    current_q_values = get_q_values(user_id, state_key, db)
    current_q = current_q_values[action]

    # max Q(s', a')
    next_q_values = get_q_values(user_id, next_state_key, db)
    max_next_q = max(next_q_values.values())

    # Bellman update
    new_q = current_q + ALPHA * (reward + GAMMA * max_next_q - current_q)

    # Persist
    update_q_value(user_id, state_key, action, new_q, db)

    # Decay exploration rate
    _decay_epsilon(user_id)
