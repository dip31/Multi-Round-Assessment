"""Read-only adapters for approved Mock Drive blueprint configuration."""

from copy import deepcopy
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.assessment import AssessmentRound, AssessmentSession
from app.models.assessment_context import AssessmentContext
from app.models.company_data import CompanyBlueprint
from app.models.mock_drive import MockDrive


def snapshot_company_blueprint(blueprint: CompanyBlueprint) -> dict[str, Any]:
    return {
        "blueprint_id": blueprint.id,
        "blueprint_version": blueprint.version,
        "status": blueprint.status,
        "company_name": blueprint.company_name,
        "target_role": blueprint.target_role,
        "blueprint_data": deepcopy(blueprint.blueprint_data or {}),
    }


def get_drive_blueprint_snapshot(db: Session, drive: MockDrive) -> Optional[dict[str, Any]]:
    """Return the exact approved blueprint attached to a drive.

    Older drives can be upgraded lazily only while their attached row still has
    the version recorded on the drive. A newer mutable blueprint is never used
    as a substitute for a missing historical snapshot.
    """
    if drive.blueprint_id is None:
        return None

    snapshot = drive.blueprint_snapshot
    if snapshot:
        if (
            snapshot.get("status") != "approved"
            or snapshot.get("blueprint_id") != drive.blueprint_id
            or snapshot.get("blueprint_version") != drive.blueprint_version
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The attached blueprint snapshot does not match this Mock Drive.",
            )
        return deepcopy(snapshot)

    blueprint = (
        db.query(CompanyBlueprint)
        .filter(CompanyBlueprint.id == drive.blueprint_id)
        .first()
    )
    if blueprint is None or blueprint.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Only an approved attached blueprint can configure this assessment.",
        )

    if blueprint.version != drive.blueprint_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The attached blueprint version is unavailable for this Mock Drive.",
        )

    snapshot = snapshot_company_blueprint(blueprint)
    drive.blueprint_snapshot = deepcopy(snapshot)
    return snapshot


def snapshot_for_assessment_context(
    drive_snapshot: Optional[dict[str, Any]],
    selected_rounds: Any,
    enabled_rounds: list[str],
) -> Optional[dict[str, Any]]:
    if drive_snapshot is None:
        return None
    snapshot = deepcopy(drive_snapshot)
    snapshot["selected_rounds"] = deepcopy(selected_rounds or {})
    snapshot["enabled_rounds"] = list(enabled_rounds)
    return snapshot


def get_session_blueprint_snapshot(
    db: Session, session: AssessmentSession
) -> Optional[dict[str, Any]]:
    context = session.context
    if context is None and session.context_id is not None:
        context = (
            db.query(AssessmentContext)
            .filter(AssessmentContext.id == session.context_id)
            .first()
        )
    if context is None or context.mock_drive_id is None:
        return None

    if context.blueprint_snapshot:
        if context.blueprint_snapshot.get("status") != "approved":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Only an approved blueprint can configure this assessment.",
            )
        return deepcopy(context.blueprint_snapshot)

    drive = (
        db.query(MockDrive)
        .filter(MockDrive.id == context.mock_drive_id)
        .first()
    )
    if drive is None:
        return None
    snapshot = get_drive_blueprint_snapshot(db, drive)
    if snapshot is not None:
        context.blueprint_snapshot = snapshot_for_assessment_context(
            snapshot, drive.selected_rounds, []
        )
        db.commit()
        return deepcopy(context.blueprint_snapshot)
    return None


def get_session_blueprint_round_config(
    db: Session, session_id: int, round_type: str
) -> tuple[Optional[dict[str, Any]], Optional[dict[str, Any]]]:
    session = (
        db.query(AssessmentSession)
        .filter(AssessmentSession.id == session_id)
        .first()
    )
    if session is None:
        return None, None
    snapshot = get_session_blueprint_snapshot(db, session)
    return snapshot, get_blueprint_round_config(snapshot, round_type)


def get_session_active_blueprint_round_config(
    db: Session, session_id: int, fallback_round_type: str
) -> tuple[Optional[dict[str, Any]], Optional[dict[str, Any]], str]:
    snapshot, fallback_config = get_session_blueprint_round_config(
        db, session_id, fallback_round_type
    )
    if snapshot is None:
        return None, None, fallback_round_type

    active_round = (
        db.query(AssessmentRound)
        .filter(
            AssessmentRound.session_id == session_id,
            AssessmentRound.status == "active",
        )
        .order_by(AssessmentRound.id.desc())
        .first()
    )
    if active_round is None:
        return snapshot, fallback_config, fallback_round_type

    round_key_types = {
        "aptitude": "aptitude",
        "coding": "coding",
        "technical_interview": "interview",
        "hr_interview": "interview",
    }
    if round_key_types.get(fallback_round_type, fallback_round_type) != active_round.round_type:
        return snapshot, fallback_config, fallback_round_type
    enabled_rounds = snapshot.get("enabled_rounds") or [
        item.get("round_type")
        for item in (snapshot.get("blueprint_data") or {}).get("rounds", [])
        if isinstance(item, dict)
    ]
    matching_keys = [
        key for key in enabled_rounds
        if round_key_types.get(key) == active_round.round_type
    ]
    if not matching_keys:
        return snapshot, fallback_config, fallback_round_type

    prior_same_type_rounds = (
        db.query(AssessmentRound.id)
        .filter(
            AssessmentRound.session_id == session_id,
            AssessmentRound.round_type == active_round.round_type,
            AssessmentRound.id < active_round.id,
        )
        .count()
    )
    index = min(prior_same_type_rounds, len(matching_keys) - 1)
    round_key = matching_keys[index]
    return snapshot, get_blueprint_round_config(snapshot, round_key), round_key


def get_blueprint_round_config(
    snapshot: Optional[dict[str, Any]], round_type: str
) -> Optional[dict[str, Any]]:
    if not snapshot:
        return None
    rounds = (snapshot.get("blueprint_data") or {}).get("rounds") or []
    aliases = {
        "interview": {"interview", "technical_interview"},
        "technical_interview": {"technical_interview", "interview"},
    }
    accepted = aliases.get(round_type, {round_type})
    for round_config in rounds:
        if isinstance(round_config, dict) and round_config.get("round_type") in accepted:
            return deepcopy(round_config)
    return None


def configured_question_count(round_config: Optional[dict[str, Any]]) -> Optional[int]:
    if not round_config:
        return None
    count = round_config.get("question_count")
    if isinstance(count, bool) or not isinstance(count, (int, float)) or count <= 0:
        return None
    return int(count)


def weighted_schedule(weights: dict[str, float], count: int) -> list[str]:
    """Build a deterministic weighted-fair sequence from positive weights."""
    entries = [(key, float(weight)) for key, weight in weights.items() if weight > 0]
    if not entries or count <= 0:
        return []

    total_weight = sum(weight for _, weight in entries)
    assigned = {key: 0 for key, _ in entries}
    sequence = []
    for position in range(1, count + 1):
        key, _ = max(
            entries,
            key=lambda entry: position * entry[1] / total_weight - assigned[entry[0]],
        )
        assigned[key] += 1
        sequence.append(key)
    return sequence


def difficulty_weights(round_config: Optional[dict[str, Any]]) -> dict[str, float]:
    raw = (round_config or {}).get("difficulty_distribution")
    if not isinstance(raw, dict):
        return {}
    normalized = {}
    for key in ("easy", "medium", "hard"):
        try:
            value = float(raw.get(key, 0))
        except (TypeError, ValueError):
            continue
        if value > 0:
            normalized[key] = value
    return normalized


def topic_weights(round_config: Optional[dict[str, Any]]) -> dict[str, float]:
    raw = (round_config or {}).get("topics")
    if not isinstance(raw, list):
        return {}
    normalized = {}
    for item in raw:
        if isinstance(item, str):
            name, weight = item.strip(), 1.0
        elif isinstance(item, dict):
            name = str(item.get("topic") or item.get("name") or "").strip()
            try:
                weight = float(item.get("weight_pct", item.get("weight", 1)))
            except (TypeError, ValueError):
                weight = 0
        else:
            continue
        if name and weight > 0:
            normalized[name] = weight
    return normalized


def match_topic_weights(
    weights: dict[str, float], available_topics: list[str]
) -> dict[str, float]:
    available_by_key = {topic.casefold(): topic for topic in available_topics}
    return {
        available_by_key[name.casefold()]: weight
        for name, weight in weights.items()
        if name.casefold() in available_by_key
    }


def scheduled_round_value(
    weights: dict[str, float], index: int
) -> Optional[str]:
    if index < 0:
        return None
    sequence = weighted_schedule(weights, index + 1)
    return sequence[-1] if sequence else None
