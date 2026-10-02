"""
Follow-up decision policy for the interview round.

This module owns ONE question: given a classified answer and the current
per-question counters, does the interviewer ask a follow-up or move on?

Extracted verbatim from the inline decision block that previously lived in
``interview_router.submit_response`` (STEP 5). The branch ordering here is
load-bearing and must not be "tidied":

1. ``force_next`` wins over everything (second consecutive silence).
2. The follow-up hard cap is checked BEFORE any quality/intent branch, so a
   candidate can never receive a third follow-up on one question.
3. Intent is checked before quality, so a NEGATIVE answer is treated as a
   disinterest signal even when its quality would otherwise be SHORT/PARTIAL.
4. An unrecognised ``quality`` value falls through to NEXT rather than raising.

This module is deliberately pure: no database, no LLM, no mutation of its
inputs. It reports which counters *should* be incremented and lets the caller
apply them, which keeps the policy unit-testable without a session.

NOTE ON SCOPE: this is interview *intelligence*, not interviewer
*presentation*. Nothing about the selected interviewer (persona, voice, name)
may influence the decisions made here — swapping interviewers must never
change whether a follow-up is asked.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Maximum follow-ups allowed on a single main question.
MAX_FOLLOWUPS_PER_QUESTION = 2

# Counters that are scoped to the current question and reset on turn advance.
# ``asked_question_ids``, ``conversation_history``, ``q_table`` and ``epsilon``
# are cumulative and must NOT appear here.
TURN_COUNTER_KEYS = (
    "followup_count",
    "irrelevant_count",
    "negative_count",
    "silence_count",
)

# Quality values that trigger an unconditional follow-up (subject to the cap).
_ALWAYS_FOLLOWUP_QUALITIES = ("SHORT", "PARTIAL")

# Quality/intent values that get exactly one follow-up per question, tracked by
# their own counter so a repeat offence moves the interview along instead of
# looping.
_ONCE_ONLY_COUNTER = {
    "NEGATIVE": "negative_count",
    "IRRELEVANT": "irrelevant_count",
}


@dataclass(frozen=True)
class FollowupDecision:
    """Outcome of the follow-up policy for a single submitted answer.

    Attributes:
        action: ``"FOLLOWUP"`` or ``"NEXT"``. Note that ``"COMPLETE"`` is *not*
            produced here — promoting NEXT to COMPLETE depends on turn budget
            and is the orchestrator's job.
        followup_type: ``SHORT`` | ``PARTIAL`` | ``IRRELEVANT`` | ``NEGATIVE``
            when following up, otherwise ``None``. Drives interviewer wording.
        counter_increments: Counter name -> amount to add. Empty when moving on.
        reason: Human-readable explanation, for logs and debugging only. Never
            surfaced to the candidate.
    """

    action: str
    followup_type: Optional[str] = None
    counter_increments: Dict[str, int] = field(default_factory=dict)
    reason: str = ""

    @property
    def is_followup(self) -> bool:
        return self.action == "FOLLOWUP"


def decide(
    *,
    force_next: bool,
    quality: str,
    intent: str,
    followup_count: int = 0,
    irrelevant_count: int = 0,
    negative_count: int = 0,
) -> FollowupDecision:
    """Decide whether to follow up on the candidate's answer or move on.

    Keyword-only by design: the arguments are four counters and two
    classification labels of similar type, and positional calls would be far
    too easy to transpose silently.

    Args:
        force_next: Skip all deliberation and move on. Set when the candidate
            has been silent twice in a row and has already been re-prompted.
        quality: ``IRRELEVANT`` | ``SHORT`` | ``PARTIAL`` | ``GOOD``.
        intent: ``POSITIVE`` | ``NEUTRAL`` | ``NEGATIVE``.
        followup_count: Follow-ups already asked on the current question.
        irrelevant_count: Irrelevant-answer follow-ups already spent.
        negative_count: Negative-intent follow-ups already spent.

    Returns:
        A :class:`FollowupDecision`. Never raises on unexpected label values.
    """

    if force_next:
        return FollowupDecision(
            action="NEXT",
            reason="force_next set (repeated silence) — moving on with a zero score",
        )

    # Hard cap first, before any quality/intent branch. This is what guarantees
    # the interview always makes forward progress.
    if followup_count >= MAX_FOLLOWUPS_PER_QUESTION:
        return FollowupDecision(
            action="NEXT",
            reason=(
                f"follow-up cap reached "
                f"({followup_count}/{MAX_FOLLOWUPS_PER_QUESTION}) — moving on"
            ),
        )

    # Intent outranks quality: disinterest is worth probing even if the answer
    # was otherwise well-formed.
    if intent == "NEGATIVE":
        return _once_only_decision(
            label="NEGATIVE",
            spent=negative_count,
            reason_when_allowed="negative intent detected — probing once",
        )

    if quality == "IRRELEVANT":
        return _once_only_decision(
            label="IRRELEVANT",
            spent=irrelevant_count,
            reason_when_allowed="answer was off-topic — redirecting once",
        )

    if quality in _ALWAYS_FOLLOWUP_QUALITIES:
        return FollowupDecision(
            action="FOLLOWUP",
            followup_type=quality,
            counter_increments={"followup_count": 1},
            reason=f"quality={quality} — asking candidate to elaborate",
        )

    if quality == "GOOD":
        return FollowupDecision(
            action="NEXT",
            reason="quality=GOOD — answer was sufficient",
        )

    # Defensive: an unrecognised quality label must not stall the interview.
    # The classifier already normalises its output, so this means either the
    # fallback path or a future label that nobody wired up here.
    logger.warning(
        "Unrecognised answer quality %r in follow-up policy; defaulting to NEXT",
        quality,
    )
    return FollowupDecision(
        action="NEXT",
        reason=f"unrecognised quality={quality!r} — defaulting to NEXT",
    )


def _once_only_decision(
    *,
    label: str,
    spent: int,
    reason_when_allowed: str,
) -> FollowupDecision:
    """Grant at most one follow-up for a self-limiting signal.

    ``NEGATIVE`` and ``IRRELEVANT`` each get a single probe per question. A
    second occurrence means the probe did not land, so pressing again would
    just antagonise the candidate.
    """
    counter = _ONCE_ONLY_COUNTER[label]

    if spent == 0:
        return FollowupDecision(
            action="FOLLOWUP",
            followup_type=label,
            # Both the specific counter and the shared cap counter advance.
            counter_increments={counter: 1, "followup_count": 1},
            reason=reason_when_allowed,
        )

    return FollowupDecision(
        action="NEXT",
        reason=f"{label} follow-up already spent ({counter}={spent}) — moving on",
    )


def apply_increments(state: Dict, decision: FollowupDecision) -> None:
    """Apply a decision's counter increments to an ``rl_state`` dict in place.

    Mirrors the original inline ``state[k] = state.get(k, 0) + 1`` pattern, so
    a missing counter is treated as zero rather than raising.

    The caller is still responsible for reassigning the mutated dict back onto
    ``InterviewSession.rl_state`` — SQLAlchemy does not detect in-place JSONB
    mutation.
    """
    for key, amount in decision.counter_increments.items():
        state[key] = state.get(key, 0) + amount


def reset_turn_counters(state: Dict) -> None:
    """Zero the per-question counters when advancing to a new main question.

    Cumulative fields are intentionally untouched. See ``TURN_COUNTER_KEYS``.
    """
    for key in TURN_COUNTER_KEYS:
        state[key] = 0
