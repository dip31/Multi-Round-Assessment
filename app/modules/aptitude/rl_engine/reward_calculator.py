"""
Reward Calculator — compute a float reward for a single aptitude attempt.

Reward factors (applied in order):
1. Base reward: ±1.0 × difficulty multiplier
2. Time bonus / penalty based on response_time / time_limit ratio
3. Streak modifier (±0.3 for 3+ consecutive correct/wrong)
4. Final value clamped to [-3.0, +3.0]
"""

# ── Constants ─────────────────────────────────────────────────────────
DIFFICULTY_MULTIPLIER: dict[str, float] = {
    "easy": 0.5,
    "medium": 1.0,
    "hard": 1.8,  # slightly higher reward for hard to encourage challenging questions
}

_REWARD_FLOOR: float = -3.0
_REWARD_CEIL: float = 3.0
_STREAK_THRESHOLD: int = 3
_STREAK_BONUS: float = 0.3

# Default time limit when a question doesn't specify one
DEFAULT_TIME_LIMIT: float = 30.0


def calculate_reward(
    is_correct: bool,
    difficulty: str,
    response_time: float,
    question_time_limit: float,
    correct_streak: int,
    wrong_streak: int,
) -> float:
    """Compute the reward for a single attempt.

    Args:
        is_correct: Whether the student answered correctly.
        difficulty: ``"easy"`` | ``"medium"`` | ``"hard"``.
        response_time: Seconds the student took to answer.
        question_time_limit: Maximum allowed seconds for this question.
        correct_streak: Consecutive correct answers (from state builder).
        wrong_streak: Consecutive wrong answers (from state builder).

    Returns:
        A float reward clamped to ``[-3.0, +3.0]``.
    """
    multiplier = DIFFICULTY_MULTIPLIER.get(difficulty, 1.0)

    # 1. Base reward (difficulty-weighted correctness)
    reward: float = (1.0 if is_correct else -1.0) * multiplier

    # 2. Time bonus / penalty
    time_limit = question_time_limit if question_time_limit > 0 else DEFAULT_TIME_LIMIT
    time_ratio = response_time / time_limit

    if time_ratio < 0.4:
        reward += 0.5       # answered very fast
    elif time_ratio < 0.7:
        reward += 0.2       # comfortable pace
    elif time_ratio > 0.9:
        reward -= 0.3       # nearly timed out

    # 3. Streak modifier
    if correct_streak >= _STREAK_THRESHOLD:
        reward += _STREAK_BONUS
    if wrong_streak >= _STREAK_THRESHOLD:
        reward -= _STREAK_BONUS

    # 4. Clamp
    return max(_REWARD_FLOOR, min(_REWARD_CEIL, reward))
