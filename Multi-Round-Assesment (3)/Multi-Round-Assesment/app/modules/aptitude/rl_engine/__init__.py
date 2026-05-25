"""
RL Engine — public API for adaptive difficulty selection.

Import all engine functions from this single entry point::

    from app.modules.aptitude.rl_engine import (
        select_action, update_q_table, build_state,
        calculate_reward, apply_policy, log_attempt,
    )
"""

from .q_learning import select_action, update_q_table
from .state_builder import build_state
from .reward_calculator import calculate_reward
from .policy import apply_policy
from .attempt_logger import log_attempt
from .q_table_store import Action

__all__ = [
    "select_action",
    "update_q_table",
    "build_state",
    "calculate_reward",
    "apply_policy",
    "log_attempt",
    "Action",
]
