"""
Question selection for the interview round.

Consolidates the two near-duplicate selection blocks that previously lived in
``interview_router`` — one in ``get_next_question`` (initial load) and one
inside ``submit_response`` (pre-fetch of the next question).

Selection is a progressive relaxation. Starting from the questions that have
not been asked yet, we narrow by phase and then by the RL-selected difficulty,
and fall back one constraint at a time rather than failing:

    unasked ∩ phase ∩ difficulty  →  unasked ∩ phase  →  unasked  →  pool[0]

The RL engine chooses *which* difficulty to aim for; this module only honours
that choice and guarantees a question always comes back if the pool is
non-empty. Difficulty policy stays in ``InterviewRLEngine``.

⚠ THE TWO CALL SITES ARE NOT INTERCHANGEABLE. When every question has been
asked, the pre-fetch path resets the candidate set to the *whole* pool and then
re-applies the phase and difficulty filters, whereas the initial-load path
drops straight through to ``pool[0]``. That difference changes which question a
candidate sees at the end of a long interview, so it is preserved explicitly
via ``reuse_exhausted_pool`` instead of being unified away.

This module is pure: no database, no LLM, no mutation of the pool.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, Iterable, List, Optional, Sequence

logger = logging.getLogger(__name__)

# Turn index at which the interview crosses from HR into technical questioning.
TECHNICAL_PHASE_START_TURN = 5

DEFAULT_DIFFICULTY = "MEDIUM"


def select_question(
    pool: Sequence[Dict[str, Any]],
    *,
    asked_question_ids: Iterable[Any],
    phase: str,
    difficulty: str,
    reuse_exhausted_pool: bool = False,
) -> Optional[Dict[str, Any]]:
    """Pick the next question from the approved pool by progressive relaxation.

    Args:
        pool: The approved question pool. Each entry is expected to carry
            ``question``, and optionally ``id``, ``phase`` and ``difficulty``.
        asked_question_ids: Question ids already used in this interview.
        phase: Target phase to prefer, e.g. ``"HR"`` or ``"TECHNICAL"``.
        difficulty: Target difficulty from the RL engine.
        reuse_exhausted_pool: When True and every question has been asked,
            fall back to the full pool *before* filtering by phase and
            difficulty. Use True for the mid-interview pre-fetch, False for
            initial load. See the module docstring — this is not cosmetic.

    Returns:
        The selected question dict, or ``None`` if the pool is empty.
    """
    if not pool:
        logger.warning("Question selection called with an empty pool")
        return None

    asked = set(asked_question_ids or ())

    available: List[Dict[str, Any]] = [q for q in pool if q.get("id") not in asked]

    if reuse_exhausted_pool and not available:
        logger.warning(
            "Question pool exhausted (%d asked); reusing the full pool", len(asked)
        )
        available = list(pool)

    phase_filtered = [q for q in available if q.get("phase") == phase]
    difficulty_filtered = [
        q for q in phase_filtered if q.get("difficulty") == difficulty
    ]

    if difficulty_filtered:
        return difficulty_filtered[0]
    if phase_filtered:
        return phase_filtered[0]
    if available:
        return available[0]

    logger.warning("Question pool exhausted with no phase match; falling back to pool[0]")
    return pool[0]


def resolve_question_id(question: Dict[str, Any]) -> str:
    """Return a question's stable id, deriving one from its text if absent.

    Older pools were generated without explicit ids. The md5-prefix fallback
    matches what the router used, so ids stay consistent for in-flight
    interviews across this refactor.
    """
    existing = question.get("id")
    if existing:
        return existing
    return hashlib.md5(question["question"].encode()).hexdigest()[:8]


def phase_for_turn(current_turn: int, current_phase: str) -> str:
    """Return the phase the *next* question should be drawn from.

    The interview opens with HR questions and crosses into technical ones at
    turn ``TECHNICAL_PHASE_START_TURN``. Before that boundary the session's
    existing phase is respected, so a session that started in TECHNICAL stays
    there.
    """
    if current_turn >= TECHNICAL_PHASE_START_TURN:
        return "TECHNICAL"
    return current_phase


def find_unasked_alternative(
    candidates: Sequence[Dict[str, Any]],
    asked_question_ids: Iterable[Any],
) -> Optional[Dict[str, Any]]:
    """Find a replacement question whose id has not been asked yet.

    Safety net for the initial-load path: if selection somehow returns a
    question that was already asked, we scan for a genuine alternative rather
    than repeating ourselves to the candidate. Returns ``None`` when every
    candidate is a repeat, in which case the caller keeps its original pick.
    """
    asked = set(asked_question_ids or ())
    for candidate in candidates:
        if resolve_question_id(candidate) not in asked:
            return candidate
    return None
