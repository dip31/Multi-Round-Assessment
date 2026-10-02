"""
Answer understanding for the interview round.

Turns a raw candidate transcript into the structured verdict the rest of the
pipeline consumes: quality, intent, content score, and the notable missing
concept. Also owns the silence rules, which previously sat inline in
``interview_router.submit_response`` (STEP 1 and STEP 2).

This is a thin, deliberate seam. The classification prompt itself still lives
in ``GroqService.classify_answer`` and is unchanged by this refactor — the point
here is to give callers a typed result instead of a bare dict, and to put the
"what counts as silence" rule in one named place instead of a magic ``< 5``
buried in a route handler.

Silence is handled in two stages, which is why it lives alongside
classification rather than in the follow-up policy:

* First silence — the candidate is re-prompted and nothing is scored. No LLM
  call is made, and no turn is consumed.
* Second silence — we stop waiting, score the turn as an empty answer, and let
  the follow-up policy force the interview forward.

Classification never raises: ``GroqService`` degrades to a heuristic fallback
if the LLM is unavailable, so a provider outage slows the interview down but
does not fail it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# A transcript shorter than this is treated as "nothing was said" rather than as
# a terse answer. Whisper emits stray one- or two-character artefacts on silent
# audio, which is what this threshold is really guarding against.
SILENCE_MIN_TRANSCRIPT_CHARS = 5

VALID_QUALITIES = ("IRRELEVANT", "SHORT", "PARTIAL", "GOOD")
VALID_INTENTS = ("POSITIVE", "NEUTRAL", "NEGATIVE")

DEFAULT_QUALITY = "SHORT"
DEFAULT_INTENT = "NEUTRAL"


@dataclass(frozen=True)
class AnswerUnderstanding:
    """Structured verdict on a single candidate answer.

    Attributes:
        quality: How well the answer addressed the question. One of
            ``VALID_QUALITIES``.
        intent: The candidate's attitude. One of ``VALID_INTENTS``.
        content_score: Substance of the answer, 0.0–1.0.
        missing_part: The specific concept the candidate omitted, when the
            classifier identified one. Used to aim the follow-up wording.
        was_classified: False when this verdict was assigned without calling the
            classifier — i.e. the silence path. Useful for telemetry and for
            explaining a zero score in the report.
    """

    quality: str
    intent: str
    content_score: float
    missing_part: Optional[str] = None
    was_classified: bool = True


def is_silence(transcript: Optional[str]) -> bool:
    """Return True when a transcript is too short to be a real answer."""
    if not transcript:
        return True
    return len(transcript.strip()) < SILENCE_MIN_TRANSCRIPT_CHARS


def normalize_transcript(transcript: Optional[str]) -> str:
    """Trim a transcript, tolerating ``None`` from the STT layer."""
    return (transcript or "").strip()


def silent_answer() -> AnswerUnderstanding:
    """The verdict for a candidate who stayed silent through a re-prompt.

    Scored as an empty answer: no content, neutral intent. Quality is SHORT
    rather than IRRELEVANT because nothing off-topic was actually said — there
    is no evidence of a misunderstanding, only of non-response. This also keeps
    the RL reward from taking the IRRELEVANT penalty on top of the zero score.
    """
    return AnswerUnderstanding(
        quality=DEFAULT_QUALITY,
        intent=DEFAULT_INTENT,
        content_score=0.0,
        missing_part=None,
        was_classified=False,
    )


def understand(
    groq_service: Any,
    *,
    question: str,
    transcript: str,
    interview_type: str = "technical",
) -> AnswerUnderstanding:
    """Classify a candidate answer into a structured verdict.

    Args:
        groq_service: Anything exposing ``classify_answer(question, answer,
            interview_type=...) -> dict``. Injected rather than imported so the
            pipeline can be tested with a stub.
        question: The question actually asked, as read from session state.
        transcript: The candidate's transcribed answer.
        interview_type: ``technical`` | ``hr`` | ``communication``. Selects the
            evaluation rubric.

    Returns:
        An :class:`AnswerUnderstanding`. Falls back to a conservative verdict
        rather than raising if the classifier returns something unusable.
    """
    raw: Dict[str, Any] = groq_service.classify_answer(
        question,
        transcript,
        interview_type=interview_type,
    )

    return _from_classifier_result(raw)


def _from_classifier_result(raw: Dict[str, Any]) -> AnswerUnderstanding:
    """Coerce a classifier dict into a validated ``AnswerUnderstanding``.

    ``GroqService`` already validates its own output, so this is belt-and-braces
    for the case where a future classifier implementation is swapped in behind
    the same interface.
    """
    if not isinstance(raw, dict):
        logger.warning(
            "Classifier returned %s rather than a dict; using conservative default",
            type(raw).__name__,
        )
        return AnswerUnderstanding(
            quality=DEFAULT_QUALITY,
            intent=DEFAULT_INTENT,
            content_score=0.0,
        )

    quality = str(raw.get("quality", DEFAULT_QUALITY)).strip().upper()
    if quality not in VALID_QUALITIES:
        logger.warning("Classifier returned unknown quality %r; using %s", quality, DEFAULT_QUALITY)
        quality = DEFAULT_QUALITY

    intent = str(raw.get("intent", DEFAULT_INTENT)).strip().upper()
    if intent not in VALID_INTENTS:
        logger.warning("Classifier returned unknown intent %r; using %s", intent, DEFAULT_INTENT)
        intent = DEFAULT_INTENT

    try:
        content_score = float(raw.get("content_score", 0.0))
    except (TypeError, ValueError):
        logger.warning(
            "Classifier returned non-numeric content_score %r; using 0.0",
            raw.get("content_score"),
        )
        content_score = 0.0

    return AnswerUnderstanding(
        quality=quality,
        intent=intent,
        content_score=max(0.0, min(1.0, content_score)),
        missing_part=raw.get("missing_part"),
        was_classified=True,
    )
