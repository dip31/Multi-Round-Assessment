"""Blueprint-driven competency scoring (EDI5 Phase 4, milestone D1).

Read-only derivation of competency-level and overall scores from:

* the competencies configured on the session's **pinned** blueprint snapshot, and
* the persisted ``competency_evidence_mappings`` evidence rows.

Design contract
---------------
* No competency score is stored. Scoring is a pure function of persisted evidence
  plus the pinned blueprint, so repeated reads are reproducible.
* Normalization reuses the persisted evidence metrics. Nothing is inferred from
  question text, question titles, or LLM output.
* A competency without countable evidence is ``not_assessed`` with a null score,
  never a fabricated zero. A competency whose evidence is all-zero is still
  ``assessed`` with score ``0.0`` (a legitimate zero).
* Weights are blueprint ``weight_pct`` percentages. Invalid weights fail closed:
  they are never replaced by equal weights and never silently redistributed.
* Missing evidence is never redistributed into the provisional overall score.
* An infrastructure / non-final evidence record (e.g. a coding submission that
  Judge0 never executed) is not countable, so a system failure never becomes a
  candidate score of zero.
"""

from __future__ import annotations

import math
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.assessment import AssessmentSession
from app.models.competency import CompetencyEvidenceMapping
from app.services.assessment_blueprint_service import get_session_blueprint_snapshot
from app.services.competency_mapping_service import (
    configured_competencies,
    competency_identifier,
)

# Bump when the normalization/aggregation policy changes, so a stored result can
# be reproduced against the exact policy that produced it.
SCORING_POLICY_VERSION = "d1-v1"

# Overall score states.
STATUS_FINAL = "final"
STATUS_PROVISIONAL = "provisional"
STATUS_UNAVAILABLE = "unavailable"

# Per-competency states.
COMPETENCY_ASSESSED = "assessed"
COMPETENCY_NOT_ASSESSED = "not_assessed"

# Blueprint competency weights are percentages that must sum to ~100.
_WEIGHT_SUM_TOLERANCE = 0.1

# Coding statuses that are not candidate performance (infrastructure / non-final)
# and therefore never countable evidence.
_NON_COUNTABLE_CODING_STATUSES = frozenset({"internal_error", "running"})


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _normalize_coding_score(raw: Any) -> float | None:
    """Coding submission scores are persisted as a 0..1 fraction."""
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return _clamp(value, 0.0, 1.0) * 100.0


def _countable_score(mapping: CompetencyEvidenceMapping) -> float | None:
    """Normalized 0..100 score for one evidence row, or None if not countable.

    ``None`` means "this evidence must not contribute a score" (unknown evidence
    type, non-final coding status, or a missing raw metric). It never means zero.
    """
    metric = mapping.raw_metric or {}
    if mapping.evidence_type == "coding_submission":
        if metric.get("status") in _NON_COUNTABLE_CODING_STATUSES:
            return None
        return _normalize_coding_score(metric.get("score"))
    if mapping.evidence_type == "aptitude_attempt":
        is_correct = metric.get("is_correct")
        if is_correct is None:
            return None
        return 100.0 if bool(is_correct) else 0.0
    return None


def _coerce_weight(raw: Any) -> float | None:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return value


def validate_competency_weights(competencies: list[dict]) -> list[str]:
    """Return a list of weight-configuration errors (empty when valid).

    Weights are blueprint ``weight_pct`` percentages and must be finite,
    non-negative, and sum to 100 (tolerance 0.1). Any error fails the overall
    score closed rather than inventing or redistributing weights.
    """
    errors: list[str] = []
    weights: list[float] = []
    for competency in competencies:
        name = str(competency.get("name", "")).strip() or "?"
        raw = competency.get("weight_pct")
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            errors.append(f"'{name}' has a missing or non-numeric weight")
            continue
        value = float(raw)
        if math.isnan(value) or math.isinf(value):
            errors.append(f"'{name}' has a non-finite weight")
            continue
        if value < 0:
            errors.append(f"'{name}' has a negative weight")
            continue
        weights.append(value)
    if errors:
        return errors
    if not weights or sum(weights) <= 0:
        return ["no positive competency weight is configured"]
    total = sum(weights)
    if abs(total - 100.0) > 0.1:
        return [f"competency weights must sum to 100 (got {round(total, 4)})"]
    return []


def _safe_snapshot(db: Session, session: AssessmentSession):
    try:
        return get_session_blueprint_snapshot(db, session), None
    except HTTPException:
        # Unapproved or mismatched pinned snapshot: scoring fails closed.
        return None, "blueprint_snapshot_unavailable"


def score_session_competencies(
    db: Session, session: AssessmentSession
) -> dict:
    """Compute the competency scoring view for one session (read-only)."""
    snapshot, snapshot_error = _safe_snapshot(db, session)
    competencies = configured_competencies(snapshot)

    blueprint_id = snapshot.get("blueprint_id") if snapshot else None
    blueprint_version = snapshot.get("blueprint_version") if snapshot else None

    mappings = (
        db.query(CompetencyEvidenceMapping)
        .filter(CompetencyEvidenceMapping.session_id == session.id)
        .all()
    )
    by_competency: dict[str, list[CompetencyEvidenceMapping]] = {}
    for mapping in mappings:
        by_competency.setdefault(mapping.competency_id, []).append(mapping)

    summaries: list[dict] = []
    for competency in competencies:
        competency_id = competency_identifier(competency)
        rows = by_competency.get(competency_id, [])
        countable = [_countable_score(row) for row in rows]
        scores = [score for score in countable if score is not None]
        if scores:
            normalized = round(sum(scores) / len(scores), 2)
            status = COMPETENCY_ASSESSED
            evidence_count = len(scores)
        else:
            normalized = None
            status = COMPETENCY_NOT_ASSESSED
            evidence_count = 0
        countable_rows = [row for row, s in zip(rows, countable) if s is not None]
        summaries.append({
            "competency_id": competency_id,
            "competency_name": str(competency.get("name", "")).strip(),
            "weight_pct": _coerce_weight(competency.get("weight_pct")),
            "normalized_score": normalized,
            "status": status,
            "evidence_count": evidence_count,
            "evidence_types": sorted({row.evidence_type for row in countable_rows}),
            "sources": sorted({row.source for row in countable_rows}),
        })

    required = len(summaries)
    assessed = [s for s in summaries if s["status"] == COMPETENCY_ASSESSED]
    missing = [
        s["competency_name"] for s in summaries
        if s["status"] != COMPETENCY_ASSESSED
    ]

    if required:
        coverage = round(len(assessed) / required, 4)
    else:
        coverage = None

    weight_errors = validate_competency_weights(competencies)

    overall_score: float | None = None
    overall_status = STATUS_UNAVAILABLE
    scoring_error: str | None = None

    if not competencies:
        scoring_error = "no_configured_competencies"
    elif weight_errors:
        scoring_error = "invalid_competency_weights: " + "; ".join(weight_errors)
    elif not assessed:
        overall_status = STATUS_UNAVAILABLE
    else:
        use = summaries if not missing else assessed
        weighted = sum(
            (s["weight_pct"] or 0.0) * (s["normalized_score"] or 0.0)
            for s in use
        )
        overall_score = round(weighted / 100.0, 2)
        overall_status = STATUS_FINAL if not missing else STATUS_PROVISIONAL

    return {
        "overall_score": overall_score,
        "overall_score_status": overall_status,
        "required_competency_count": required,
        "assessed_competency_count": len(assessed),
        "evidence_coverage": coverage,
        "missing_competencies": missing,
        "competencies": summaries,
        "blueprint_id": snapshot.get("blueprint_id") if snapshot else None,
        "blueprint_version": snapshot.get("blueprint_version") if snapshot else None,
        "scoring_policy_version": SCORING_POLICY_VERSION,
        "scoring_error": scoring_error,
    }
