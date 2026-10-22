"""Deterministic validation for LLM-generated question pools.

These are pure functions executed AFTER the LLM returns a pool and BEFORE any
row is persisted or any pool is marked complete. A pool that fails validation
is recorded as ``incomplete``/``failed`` on the registry and blocks publishing;
it is never served to a candidate and never silently substituted.

The topic/difficulty schedule produced by ``weighted_schedule`` is the
"mathematically closest" distribution to the approved blueprint weights, so the
validators enforce that schedule exactly for aptitude and coding pools.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

APTITUDE_DIFFICULTIES = {"easy", "medium", "hard"}
CODING_DIFFICULTIES = {"easy", "medium", "hard"}
INTERVIEW_DIFFICULTIES = {"EASY", "MEDIUM", "HARD"}

# Primary text field per round type (drives duplicate detection).
ROUND_TEXT_KEYS = {
    "aptitude": "question_text",
    "coding": "title",
    "technical_interview": "question",
    "hr_interview": "question",
}


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _topic_key(value: Any) -> str:
    """Case/whitespace-insensitive key for matching a topic label."""
    return _clean(value).casefold()


def deduplicate_pool(
    items: List[Dict[str, Any]], round_type: str
) -> List[Dict[str, Any]]:
    """Drop repeat items before validation, keeping the first occurrence.

    Batched generation can re-emit identical text across provider calls; the
    strict validators would otherwise fail the whole pool on duplicates. Only
    exact (trimmed, case-insensitive) matches on the round's primary text are
    dropped - items are never reworded, merged, or substituted.
    """
    text_key = ROUND_TEXT_KEYS.get(round_type)
    if not text_key:
        return list(items)
    seen = set()
    unique: List[Dict[str, Any]] = []
    for item in items:
        key = _clean(item.get(text_key)).casefold()
        if key:
            if key in seen:
                continue
            seen.add(key)
        unique.append(item)
    return unique


def _duplicate_keys(items: List[Dict[str, Any]], text_key: str) -> List[str]:
    seen = set()
    dupes = []
    for item in items:
        key = _clean(item.get(text_key))
        if not key:
            continue
        if key.casefold() in seen:
            dupes.append(key[:80])
        seen.add(key.casefold())
    return dupes


def _require_pool_size(items: List[Dict[str, Any]], pool_size: int) -> List[str]:
    if len(items) != pool_size:
        return [f"expected exactly {pool_size} items, got {len(items)}"]
    return []


def _clean_difficulty(value: Any) -> str:
    return _clean(value).casefold()


def select_deterministic_pool(
    items: List[Dict[str, Any]],
    spec: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Deterministically meet the exact requested pool size after the LLM call.

    - ``len(items) <= pool_size``: returned unchanged (the strict validators
      reject any shortage afterwards — no partial pool is ever persisted).
    - ``len(items) > pool_size``: candidates are trimmed to exactly ``pool_size``
      by first matching the blueprint's topic/difficulty schedule position by
      position (stable order), then filling any remaining capacity from leftover
      candidates in their original order. Extra/unrelated content is dropped, so
      the resulting pool still satisfies the approved schedule or fails
      validation cleanly.

    Deterministic: identical input yields identical output (no randomness).
    """
    pool_size = int(spec.get("pool_size") or 0)
    if pool_size <= 0:
        return list(items)
    candidates = list(items)
    if len(candidates) <= pool_size:
        return candidates

    positions = spec.get("positions") or []
    if not positions:
        return _topic_cover_select(candidates, spec, pool_size)

    remaining = list(candidates)
    selected: List[Dict[str, Any]] = []
    for position in positions:
        topic = _clean(position.get("topic"))
        difficulty = _clean_difficulty(position.get("difficulty"))
        match_idx = None
        for idx, candidate in enumerate(remaining):
            if _clean(candidate.get("topic")) != topic:
                continue
            candidate_difficulty = _clean_difficulty(candidate.get("difficulty"))
            if difficulty and candidate_difficulty != difficulty:
                continue
            match_idx = idx
            break
        if match_idx is None:
            continue
        selected.append(remaining.pop(match_idx))

    for candidate in remaining:
        if len(selected) >= pool_size:
            break
        selected.append(candidate)
    return selected


def _topic_cover_select(
    candidates: List[Dict[str, Any]],
    spec: Dict[str, Any],
    pool_size: int,
) -> List[Dict[str, Any]]:
    """Trim to ``pool_size`` keeping at least one candidate per blueprint topic."""
    expected_topics = {_clean(t) for t in spec.get("topics") or []}
    selected: List[Dict[str, Any]] = []
    used: set = set()
    for topic in expected_topics:
        for idx, candidate in enumerate(candidates):
            if idx in used:
                continue
            if _clean(candidate.get("topic")) == topic:
                selected.append(candidate)
                used.add(idx)
                break
    for idx, candidate in enumerate(candidates):
        if idx in used:
            continue
        if len(selected) >= pool_size:
            break
        selected.append(candidate)
        used.add(idx)
    return selected


def _build_schedule(positions: List[Dict[str, Any]]) -> Tuple[
    Counter, Counter, Counter, bool
]:
    """Return (topic_totals, diff_totals, pair_totals, uses_difficulty)."""
    topic_totals: Counter = Counter()
    diff_totals: Counter = Counter()
    pair_totals: Counter = Counter()
    for item in positions:
        topic = _clean(item.get("topic"))
        diff = _clean(item.get("difficulty"))
        topic_totals[topic] += 1
        if diff:
            diff_totals[diff.casefold()] += 1
            pair_totals[(topic, diff.casefold())] += 1
        else:
            pair_totals[(topic, "__any__")] += 1
    uses_difficulty = bool(diff_totals)
    return topic_totals, diff_totals, pair_totals, uses_difficulty


def validate_aptitude_pool(
    items: List[Dict[str, Any]],
    spec: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    """Validate a generated aptitude MCQ pool against the blueprint schedule.

    ``spec`` keys: pool_size, positions, topics (set of expected topic names).
    """
    errors: List[str] = []
    pool_size = int(spec.get("pool_size") or 0)
    expected_topics = {_clean(t) for t in spec.get("topics") or []}
    if pool_size <= 0:
        errors.append("invalid pool_size in spec")
        return False, errors

    errors += _require_pool_size(items, pool_size)

    for idx, item in enumerate(items, start=1):
        if not _clean(item.get("question_text")):
            errors.append(f"question {idx}: missing question_text")
        for option in ("option_a", "option_b", "option_c", "option_d"):
            if not _clean(item.get(option)):
                errors.append(f"question {idx}: missing {option}")
        correct = _clean(item.get("correct_option")).upper()
        if correct not in {"A", "B", "C", "D"}:
            errors.append(f"question {idx}: correct_option must be A|B|C|D")
        difficulty = _clean(item.get("difficulty")).casefold()
        if difficulty not in APTITUDE_DIFFICULTIES:
            errors.append(f"question {idx}: difficulty must be easy|medium|hard")
        topic = _clean(item.get("topic"))
        if not topic:
            errors.append(f"question {idx}: missing topic")
        elif expected_topics and topic not in expected_topics:
            errors.append(f"question {idx}: topic {topic!r} not in blueprint topics")

    for dupe in _duplicate_keys(items, "question_text"):
        errors.append(f"duplicate question_text: {dupe!r}")

    if errors:
        return False, errors[:50]

    topic_totals, diff_totals, pair_totals, uses_difficulty = _build_schedule(
        spec.get("positions") or []
    )
    actual_topic_totals: Counter = Counter(_clean(item.get("topic")) for item in items)
    if actual_topic_totals != topic_totals:
        missing = topic_totals - actual_topic_totals
        excess = actual_topic_totals - topic_totals
        notes = []
        for name, count in list(missing.items())[:5]:
            notes.append(f"short {count} by topic {name!r}")
        for name, count in list(excess.items())[:5]:
            notes.append(f"excess {count} by topic {name!r}")
        errors.append("topic distribution does not match the approved schedule: " + "; ".join(notes))

    if uses_difficulty:
        actual_diff_totals: Counter = Counter(
            _clean(item.get("difficulty")).casefold() for item in items
        )
        if actual_diff_totals != diff_totals:
            errors.append("difficulty distribution does not match the approved schedule")
        actual_pair_totals: Counter = Counter(
            (_clean(item.get("topic")), _clean(item.get("difficulty")).casefold())
            for item in items
        )
        if actual_pair_totals != pair_totals:
            errors.append(
                "per-topic/per-difficulty pairing does not match the approved schedule"
            )
    else:
        missing_topics = {
            name for name, count in topic_totals.items() if count > 0
        } - set(_clean(item.get("topic")) for item in items)
        if missing_topics:
            errors.append(
                "no question authored for topic(s): "
                + ", ".join(sorted(missing_topics)[:5])
            )

    return not errors, errors[:50]


def validate_coding_pool(
    items: List[Dict[str, Any]],
    spec: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    """Validate a generated coding problem pool against the blueprint schedule.

    ``spec`` keys: pool_size, positions, topics (set of expected topic names).
    """
    errors: List[str] = []
    pool_size = int(spec.get("pool_size") or 0)
    expected_topics = {_clean(t) for t in spec.get("topics") or []}
    if pool_size <= 0:
        errors.append("invalid pool_size in spec")
        return False, errors

    errors += _require_pool_size(items, pool_size)

    for idx, item in enumerate(items, start=1):
        if not _clean(item.get("title")):
            errors.append(f"problem {idx}: missing title")
        if not _clean(item.get("description")):
            errors.append(f"problem {idx}: missing description")
        if not _clean(item.get("input_format")):
            errors.append(f"problem {idx}: missing input_format")
        if not _clean(item.get("output_format")):
            errors.append(f"problem {idx}: missing output_format")
        difficulty = _clean(item.get("difficulty")).casefold()
        if difficulty not in CODING_DIFFICULTIES:
            errors.append(f"problem {idx}: difficulty must be easy|medium|hard")
        topic = _clean(item.get("topic"))
        if not topic:
            errors.append(f"problem {idx}: missing topic")
        elif expected_topics and topic not in expected_topics:
            errors.append(f"problem {idx}: topic {topic!r} not in blueprint topics")

        test_cases = item.get("test_cases")
        if not isinstance(test_cases, list) or len(test_cases) < 2:
            errors.append(f"problem {idx}: needs at least 2 test cases (1 visible + 1 hidden)")
        else:
            visible = 0
            hidden = 0
            for case_idx, case in enumerate(test_cases, start=1):
                if not _clean(case.get("input_data")):
                    errors.append(f"problem {idx} case {case_idx}: missing input_data")
                if not _clean(case.get("expected_output")):
                    errors.append(f"problem {idx} case {case_idx}: missing expected_output")
                if bool(case.get("is_hidden")):
                    hidden += 1
                else:
                    visible += 1
            if visible < 1:
                errors.append(f"problem {idx}: must expose at least 1 visible sample case")
            if hidden < 1:
                errors.append(f"problem {idx}: must include at least 1 hidden test case")

    for dupe in _duplicate_keys(items, "title"):
        errors.append(f"duplicate problem title: {dupe!r}")

    if errors:
        return False, errors[:50]

    topic_totals, diff_totals, pair_totals, uses_difficulty = _build_schedule(
        spec.get("positions") or []
    )
    actual_topic_totals: Counter = Counter(_clean(item.get("topic")) for item in items)
    if actual_topic_totals != topic_totals:
        errors.append("topic distribution does not match the approved schedule")

    if uses_difficulty:
        actual_diff_totals: Counter = Counter(
            _clean(item.get("difficulty")).casefold() for item in items
        )
        actual_pair_totals: Counter = Counter(
            (_clean(item.get("topic")), _clean(item.get("difficulty")).casefold())
            for item in items
        )
        if actual_diff_totals != diff_totals:
            errors.append("difficulty distribution does not match the approved schedule")
        if actual_pair_totals != pair_totals:
            errors.append(
                "per-topic/per-difficulty pairing does not match the approved schedule"
            )
    else:
        missing_topics = {
            name for name, count in topic_totals.items() if count > 0
        } - set(_clean(item.get("topic")) for item in items)
        if missing_topics:
            errors.append(
                "no problem authored for topic(s): "
                + ", ".join(sorted(missing_topics)[:5])
            )

    return not errors, errors[:50]


def missing_interview_topics(
    items: List[Dict[str, Any]], spec: Dict[str, Any]
) -> List[str]:
    """Return configured topics with no authored question (case-insensitive).

    Comparison ignores surrounding whitespace and case, so an LLM that returns a
    topic label with different capitalization is not falsely reported missing.
    The original configured casing is returned, in configured order.
    """
    covered = {_topic_key(item.get("topic")) for item in items}
    return [
        topic
        for topic in (spec.get("topics") or [])
        if _topic_key(topic) and _topic_key(topic) not in covered
    ]


def validate_interview_pool(
    items: List[Dict[str, Any]],
    spec: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    """Validate a generated interview question pool.

    ``spec`` keys: pool_size, phase ("TECHNICAL"|"HR"), topics (set of names).
    Questions are consumed by the interview turn engine, so the shape must match
    ``ApprovedQuestionPool.question_pool`` dicts. Topic coverage is compared
    case-insensitively so a differently-cased label is not falsely "missing".
    """
    errors: List[str] = []
    pool_size = int(spec.get("pool_size") or 0)
    phase = str(spec.get("phase") or "").upper()
    expected_topics = {_topic_key(t) for t in spec.get("topics") or [] if _topic_key(t)}
    if pool_size <= 0:
        errors.append("invalid pool_size in spec")
        return False, errors

    errors += _require_pool_size(items, pool_size)

    for idx, item in enumerate(items, start=1):
        if not _clean(item.get("question")):
            errors.append(f"question {idx}: missing question")
        if _clean(item.get("difficulty")).upper() not in INTERVIEW_DIFFICULTIES:
            errors.append(f"question {idx}: difficulty must be EASY|MEDIUM|HARD")
        if not _clean(item.get("expected_answer")):
            errors.append(f"question {idx}: missing expected_answer")
        if not _clean(item.get("evaluation_criteria")):
            errors.append(f"question {idx}: missing evaluation_criteria")
        item_phase = _clean(item.get("phase")).upper()
        if item_phase != phase:
            errors.append(f"question {idx}: phase must be {phase}")
        topic = _clean(item.get("topic"))
        if not topic:
            errors.append(f"question {idx}: missing topic")
        elif expected_topics and _topic_key(topic) not in expected_topics:
            errors.append(f"question {idx}: topic {topic!r} not in blueprint topics")

    for dupe in _duplicate_keys(items, "question"):
        errors.append(f"duplicate question: {dupe!r}")

    missing = missing_interview_topics(items, spec)
    if missing:
        errors.append(
            "no question authored for topic(s): " + ", ".join(sorted(missing)[:5])
        )

    return not errors, errors[:50]


def normalize_difficulty(item: Dict[str, Any], round_type: str) -> str:
    """Normalize a generated item's difficulty for persistence."""
    difficulty = _clean(item.get("difficulty"))
    if round_type in ("aptitude", "coding"):
        return difficulty.casefold()
    return difficulty.upper()
