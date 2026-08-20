"""
State Builder — convert raw attempt history into a discrete RL state.

The state is a 5-tuple:
    S = (difficulty_level, correct_streak, wrong_streak,
         avg_response_time_bin, topic_accuracy_bin)

Serialized as ``"medium|2|0|fast|high"`` for DB storage.
"""

from collections import namedtuple
from typing import Optional

# ── Public types ──────────────────────────────────────────────────────
RLState = namedtuple(
    "RLState",
    ["difficulty", "correct_streak", "wrong_streak",
     "response_time_bin", "topic_accuracy_bin"],
)

# ── Constants ─────────────────────────────────────────────────────────
_MAX_STREAK: int = 5
_RECENT_WINDOW: int = 5          # look-back for response-time average
_FAST_THRESHOLD: float = 5.0     # seconds
_SLOW_THRESHOLD: float = 15.0    # seconds
_HIGH_ACCURACY: float = 0.8
_LOW_ACCURACY: float = 0.5


def _compute_streaks(attempts: list[dict]) -> tuple[int, int]:
    """Count consecutive correct / wrong answers from the most recent attempt.

    Returns:
        (correct_streak, wrong_streak) each capped at ``_MAX_STREAK``.
    """
    correct_streak = 0
    wrong_streak = 0

    for attempt in reversed(attempts):
        if attempt["is_correct"]:
            if wrong_streak > 0:
                break
            correct_streak += 1
        else:
            if correct_streak > 0:
                break
            wrong_streak += 1

    return min(correct_streak, _MAX_STREAK), min(wrong_streak, _MAX_STREAK)


def _response_time_bin(attempts: list[dict]) -> str:
    """Bin the mean response time of the last ``_RECENT_WINDOW`` attempts.

    Returns:
        ``"fast"`` (< 5 s), ``"slow"`` (> 15 s), or ``"medium"``.
    """
    recent = attempts[-_RECENT_WINDOW:]
    if not recent:
        return "medium"

    avg_time = sum(a["response_time"] for a in recent) / len(recent)

    if avg_time < _FAST_THRESHOLD:
        return "fast"
    if avg_time > _SLOW_THRESHOLD:
        return "slow"
    return "medium"


def _topic_accuracy_bin(attempts: list[dict]) -> str:
    """Bin accuracy on the most recent topic.

    Returns:
        ``"high"`` (> 0.8), ``"low"`` (< 0.5), or ``"medium"``.
    """
    if not attempts:
        return "medium"

    # Use the topic from the most recent attempt
    current_topic: Optional[str] = attempts[-1].get("topic")
    topic_attempts = [
        a for a in attempts
        if a.get("topic") == current_topic
    ]

    if not topic_attempts:
        return "medium"

    accuracy = sum(1 for a in topic_attempts if a["is_correct"]) / len(topic_attempts)

    if accuracy >= _HIGH_ACCURACY:
        return "high"
    if accuracy < _LOW_ACCURACY:
        return "low"
    return "medium"


def build_state(
    attempts: list[dict],
    current_difficulty: str,
) -> tuple[str, RLState]:
    """Build an RL state from the user's attempt history.

    Args:
        attempts: List of past attempt dicts with keys
            ``is_correct``, ``response_time``, ``difficulty``, ``topic``.
        current_difficulty: The difficulty of the current / most recent question.

    Returns:
        A ``(state_key, RLState)`` tuple.  ``state_key`` is a pipe-delimited
        string suitable for DB storage, e.g. ``"medium|2|0|fast|high"``.
    """
    correct_streak, wrong_streak = _compute_streaks(attempts)
    rt_bin = _response_time_bin(attempts)
    acc_bin = _topic_accuracy_bin(attempts)

    state = RLState(
        difficulty=current_difficulty,
        correct_streak=correct_streak,
        wrong_streak=wrong_streak,
        response_time_bin=rt_bin,
        topic_accuracy_bin=acc_bin,
    )

    state_key = f"{state.difficulty}|{state.correct_streak}|{state.wrong_streak}|{state.response_time_bin}|{state.topic_accuracy_bin}"

    return state_key, state
