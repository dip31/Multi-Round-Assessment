"""
Policy — translate a chosen Action into a concrete next difficulty level.

Applies two layers of logic:
1. **Override rules** that fire regardless of the RL action
   (e.g. force decrease on long wrong streaks).
2. **Transition validation** that prevents pedagogically unsound jumps
   (easy → hard is never allowed).
"""

from app.modules.aptitude.rl_engine.q_table_store import Action

# ── Hard constraints ──────────────────────────────────────────────────
VALID_TRANSITIONS: dict[str, list[str]] = {
    "easy":   ["easy", "medium"],
    "medium": ["easy", "medium", "hard"],
    "hard":   ["medium", "hard"],
}

_DIFFICULTY_ORDER: list[str] = ["easy", "medium", "hard"]

# Override thresholds
# Make the engine react faster: 2 wrong → step down, 2 correct → step up.
_WRONG_STREAK_FORCE_DECREASE: int = 2
_CORRECT_STREAK_FORCE_INCREASE: int = 2


def _next_difficulty_for_action(current: str, action: Action) -> str:
    """Compute the proposed next difficulty from an action.

    Args:
        current: Current difficulty (``"easy"`` | ``"medium"`` | ``"hard"``).
        action: The RL action to apply.

    Returns:
        Proposed difficulty string (may be invalid — caller must validate).
    """
    idx = _DIFFICULTY_ORDER.index(current)

    if action == Action.INCREASE:
        return _DIFFICULTY_ORDER[min(idx + 1, len(_DIFFICULTY_ORDER) - 1)]
    if action == Action.DECREASE:
        return _DIFFICULTY_ORDER[max(idx - 1, 0)]
    return current   # Action.SAME


def apply_policy(
    current_difficulty: str,
    action: Action,
    correct_streak: int,
    wrong_streak: int,
) -> str:
    """Apply guard rails and transition validation to produce the next difficulty.

    Args:
        current_difficulty: ``"easy"`` | ``"medium"`` | ``"hard"``.
        action: RL-selected action (``INCREASE`` | ``SAME`` | ``DECREASE``).
        correct_streak: Consecutive correct answers.
        wrong_streak: Consecutive wrong answers.

    Returns:
        Validated next difficulty: ``"easy"`` | ``"medium"`` | ``"hard"``.
    """
    # 1. Override rules — fire before RL action
    if wrong_streak >= _WRONG_STREAK_FORCE_DECREASE:
        action = Action.DECREASE
    elif correct_streak >= _CORRECT_STREAK_FORCE_INCREASE and current_difficulty != "hard":
        action = Action.INCREASE

    # 2. Compute proposed next difficulty
    proposed = _next_difficulty_for_action(current_difficulty, action)

    # 3. Validate against allowed transitions
    if proposed in VALID_TRANSITIONS.get(current_difficulty, []):
        return proposed

    # 4. Invalid transition → stay at current difficulty
    return current_difficulty
