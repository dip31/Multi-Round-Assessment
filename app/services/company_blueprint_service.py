"""
Phase 4B: Company Assessment Blueprint Generation Service.

Responsibilities:
- Transform an APPROVED Phase 4A CompanyPattern into a TPO-reviewable Assessment Blueprint.
- Calculate round-level configurations (time limits, question counts, topic weights, difficulty).
- Derive topic distributions deterministically from historical evidence.
- Apply fallback default markings with low-confidence labels when historical evidence is missing or sparse.
- Support TPO actions: generate, recalculate, view, edit, and approve.
- Maintain separate storage (CompanyBlueprint) without overwriting historical patterns or raw data.
- Ensure strict compatibility with Phase 1-3 assessment engines without modifying those engines.
"""

from __future__ import annotations

import copy
import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.company_data import CompanyBlueprint, CompanyHistoricalData, CompanyPattern
from app.schemas.company_data import (
    BlueprintCompetency,
    BlueprintRoundConfig,
    TopicWeight,
    UpdateBlueprintRequest,
    validate_competency_configuration,
)
from app.services.topic_taxonomy import (
    TOPIC_TAXONOMY,
    get_topic_category,
    normalize_topic,
)
from app.services.edi5_benchmark_seeds import EDI5_BENCHMARKS, benchmark_role_compatible

logger = logging.getLogger(__name__)


# ── Canonical Defaults for Fallback Rounds ────────────────────────────

DEFAULT_ROUND_SPECS: Dict[str, Dict[str, Any]] = {
    "aptitude": {
        "name": "Aptitude Assessment",
        "duration_minutes": 45,
        "question_count": 25,
        "question_types": ["MCQ"],
        "default_difficulty": {"easy": 0.30, "medium": 0.50, "hard": 0.20},
        "default_topics": [
            {"topic": "Quantitative Aptitude", "weight_pct": 40.0, "category": "Aptitude", "is_default": True},
            {"topic": "Logical Reasoning", "weight_pct": 35.0, "category": "Aptitude", "is_default": True},
            {"topic": "Verbal Ability", "weight_pct": 25.0, "category": "Aptitude", "is_default": True},
        ],
    },
    "coding": {
        "name": "Coding Assessment",
        "duration_minutes": 60,
        "question_count": 2,
        "question_types": ["Coding"],
        "default_difficulty": {"easy": 0.0, "medium": 0.50, "hard": 0.50},
        "default_topics": [
            {"topic": "Data Structures & Algorithms", "weight_pct": 50.0, "category": "Data Structures & Algorithms", "is_default": True},
            {"topic": "Dynamic Programming", "weight_pct": 30.0, "category": "Data Structures & Algorithms", "is_default": True},
            {"topic": "Arrays", "weight_pct": 20.0, "category": "Data Structures & Algorithms", "is_default": True},
        ],
    },
    "technical_interview": {
        "name": "Technical Interview",
        "duration_minutes": 45,
        "question_count": 3,
        "question_types": ["Live Coding", "System Design", "Technical Q&A"],
        "default_difficulty": {"easy": 0.20, "medium": 0.50, "hard": 0.30},
        "default_topics": [
            {"topic": "Object-Oriented Programming", "weight_pct": 35.0, "category": "Core CS", "is_default": True},
            {"topic": "Database Management Systems", "weight_pct": 35.0, "category": "Core CS", "is_default": True},
            {"topic": "System Design", "weight_pct": 30.0, "category": "Core CS", "is_default": True},
        ],
    },
    "hr_interview": {
        "name": "HR / Behavioral Round",
        "duration_minutes": 30,
        "question_count": 3,
        "question_types": ["Behavioral", "Situational"],
        "default_difficulty": {"easy": 0.30, "medium": 0.60, "hard": 0.10},
        "default_topics": [
            {"topic": "Behavioral & Leadership Principles", "weight_pct": 60.0, "category": "Behavioral", "is_default": True},
            {"topic": "HR & Personal Interview", "weight_pct": 40.0, "category": "Behavioral", "is_default": True},
        ],
    },
}

ROUND_DISPLAY_NAMES = {
    "aptitude": "Aptitude Assessment",
    "coding": "Coding Assessment",
    "technical_interview": "Technical Interview",
    "hr_interview": "HR / Behavioral Round",
}


def _normalize_key(company_name: str, target_role: str) -> Tuple[str, str]:
    return company_name.strip(), target_role.strip()


def _taxonomy_round_for_topic(canonical_topic: str) -> Optional[str]:
    """Taxonomy-defined round for a topic without the blanket ``coding`` funnel.

    ``get_default_round_for_topic`` falls back to ``coding`` for topics missing
    from the taxonomy, silently mis-attributing unknown topics. Historical
    blueprint derivation must only attribute topics the taxonomy actually knows.
    """
    info = TOPIC_TAXONOMY.get(canonical_topic)
    if not info:
        return None
    return info.get("default_round", "coding")


# ── Blueprint Generation & Calculation ────────────────────────────────

def generate_blueprint_from_pattern(
    db: Session,
    company_name: str,
    target_role: str,
    created_by_id: int,
    force: bool = False,
) -> CompanyBlueprint:
    """Transform an approved 4A pattern into a structured CompanyBlueprint."""
    company, role = _normalize_key(company_name, target_role)

    # 1. Fetch CompanyPattern
    pattern = (
        db.query(CompanyPattern)
        .filter(
            func.lower(CompanyPattern.company_name) == company.lower(),
            func.lower(CompanyPattern.target_role) == role.lower(),
        )
        .first()
    )

    if not pattern:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No structured pattern found for company='{company}', "
                f"role='{role}'. Generate and approve a Phase 4A pattern first."
            ),
        )

    pattern_data = pattern.pattern_data or {}
    provenance = pattern_data.get("source_provenance")
    if not provenance:
        # Older patterns predate provenance. Resolve their source records at read
        # time without rewriting the saved pattern or any existing blueprint.
        source_ids = [item.get("id") for item in pattern_data.get("sources_summary", []) if item.get("id")]
        old_sources = db.query(CompanyHistoricalData).filter(CompanyHistoricalData.id.in_(source_ids)).all() if source_ids else []
        incompatible = []
        classifications = set()
        for source in old_sources:
            if source.source_type != "pre_seeded":
                classifications.add("company_specific_historical_evidence")
                continue
            raw = source.raw_data or {}
            old_prov = raw.get("source_provenance") or {}
            ref = raw.get("benchmark_reference", "")
            bm_name = ref.rsplit(" - ", 1)[0].strip() if ref else ""
            bm = next((item for item in EDI5_BENCHMARKS if item["company_name"].lower() == bm_name.lower()), None)
            if old_prov.get("explicit_fallback_requested"):
                classifications.add(old_prov.get("classification", "pre_seeded_benchmark"))
            elif bm and benchmark_role_compatible(role, bm):
                classifications.add("pre_seeded_benchmark")
            else:
                incompatible.append(source.id)
        if incompatible:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "INSUFFICIENT_ROLE_SPECIFIC_EVIDENCE",
                    "message": "No role-specific historical evidence is available for this company/role.",
                    "selection_status": "no_compatible_evidence_found",
                    "company_name": company,
                    "target_role": role,
                    "incompatible_source_ids": incompatible,
                },
            )
        provenance = {
            "classification": next(iter(classifications), "source_unverified"),
            "selection_status": "role_compatible_evidence_found" if classifications else "no_compatible_evidence_found",
            "explicit_fallback_requested": False,
            "empirical_source_count": sum(1 for source in old_sources if source.source_type != "pre_seeded"),
        }
    if (
        provenance.get("selection_status") == "no_compatible_evidence_found"
        and provenance.get("generation_method") != "llm_role_assessment"
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "INSUFFICIENT_ROLE_SPECIFIC_EVIDENCE",
                "message": "No role-specific historical evidence is available for this company/role.",
                "selection_status": "no_compatible_evidence_found",
                "company_name": company,
                "target_role": role,
            },
        )
    review_status = pattern_data.get("review_status", "pending_review")

    # 2. Strict Approval Requirement: Pattern must be approved by TPO
    if review_status != "approved" and not force:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Company pattern for '{company}' - '{role}' must be approved by TPO "
                f"before generating a blueprint. Current pattern review status: '{review_status}'."
            ),
        )

    is_llm_role_assessment = provenance.get("generation_method") == "llm_role_assessment"
    if is_llm_role_assessment:
        existing_llm_blueprint = db.query(CompanyBlueprint).filter(
            func.lower(CompanyBlueprint.company_name) == company.lower(),
            func.lower(CompanyBlueprint.target_role) == role.lower(),
        ).first()
        if existing_llm_blueprint:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An LLM role assessment blueprint already exists; it was not overwritten.",
            )
        _validate_llm_role_pattern(pattern_data)

    # 3. Compute Blueprint Rounds from Pattern
    computed_rounds = _compute_blueprint_rounds(pattern_data)
    if is_llm_role_assessment:
        for round_config in computed_rounds:
            topics = round_config.get("topics") or []
            if not topics or any(item.get("is_default") for item in topics):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"LLM role assessment round '{round_config.get('round_type')}' has no valid role-specific topics.",
                )
            if abs(sum(float(item.get("weight_pct", 0)) for item in topics) - 100.0) > 0.1:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"LLM role assessment round '{round_config.get('round_type')}' has invalid topic weights.",
                )

    # 4. Check existing blueprint
    existing_bp = (
        db.query(CompanyBlueprint)
        .filter(
            func.lower(CompanyBlueprint.company_name) == company.lower(),
            func.lower(CompanyBlueprint.target_role) == role.lower(),
        )
        .first()
    )

    new_version = (existing_bp.version + 1) if existing_bp else 1
    confidence_level = pattern_data.get("confidence_level", "medium")
    blueprint_data = {
        "company_name": company,
        "target_role": role,
        "status": "draft",
        "version": new_version,
        "confidence_level": confidence_level,
        "confidence_score": pattern_data.get("confidence_score", 0.75),
        "evidence_sources_count": provenance.get("empirical_source_count", pattern.source_count),
        "overall_difficulty": pattern_data.get("avg_difficulty", "medium"),
        "historical_pattern_id": pattern.id,
        "rounds": computed_rounds,
        "source_references": pattern_data.get("sources_summary", []),
        "source_provenance": provenance,
        "empirical_evidence_sources_count": provenance.get("empirical_source_count", pattern.source_count),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Preserve an existing blueprint's explicitly configured competencies across
    # recalculation. Competencies are a TPO-authored, additive layer that the
    # pattern cannot reproduce, so they are carried over verbatim (ids, names,
    # weights, topic associations) rather than regenerated, replaced, or dropped.
    # New blueprints and blueprints without a configured set are unaffected.
    if existing_bp:
        preserved_competencies = (existing_bp.blueprint_data or {}).get("competencies")
        if preserved_competencies is not None:
            blueprint_data["competencies"] = copy.deepcopy(preserved_competencies)

    if existing_bp:
        existing_bp.blueprint_data = blueprint_data
        existing_bp.status = "draft"  # Reset to draft on recalculation
        existing_bp.version = new_version
        existing_bp.confidence_level = confidence_level
        existing_bp.evidence_sources_count = provenance.get("empirical_source_count", pattern.source_count)
        existing_bp.created_by_id = created_by_id
        db.commit()
        db.refresh(existing_bp)
        return existing_bp

    new_bp = CompanyBlueprint(
        company_name=company,
        target_role=role,
        status="draft",
        version=new_version,
        blueprint_data=blueprint_data,
        confidence_level=confidence_level,
        evidence_sources_count=provenance.get("empirical_source_count", pattern.source_count),
        created_by_id=created_by_id,
    )
    db.add(new_bp)
    db.commit()
    db.refresh(new_bp)
    return new_bp


def _validate_llm_role_pattern(pattern_data: Dict[str, Any]) -> None:
    """Reject incomplete LLM patterns before legacy blueprint defaults can mask them."""
    allowed_rounds = {"aptitude", "coding", "technical_interview", "hr_interview"}
    rounds = pattern_data.get("assessment_rounds")
    round_patterns = pattern_data.get("round_patterns")
    frequency = pattern_data.get("topic_frequency")
    difficulty = pattern_data.get("difficulty_distribution")
    if (
        not isinstance(rounds, list)
        or not rounds
        or any(not isinstance(round_type, str) for round_type in rounds)
        or len(set(rounds)) != len(rounds)
    ):
        raise HTTPException(status_code=422, detail="LLM role assessment must contain unique configured rounds.")
    if any(round_type not in allowed_rounds for round_type in rounds):
        raise HTTPException(status_code=422, detail="LLM role assessment contains an unsupported round.")
    if not isinstance(round_patterns, dict) or not isinstance(frequency, list):
        raise HTTPException(status_code=422, detail="LLM role assessment has malformed round topics.")
    if any(
        not isinstance(item, dict)
        or not isinstance(item.get("topic"), str)
        or not item["topic"].strip()
        or not isinstance(item.get("typical_round"), str)
        or not isinstance(item.get("count"), (int, float))
        or not math.isfinite(item["count"])
        or item["count"] <= 0
        for item in frequency
    ):
        raise HTTPException(status_code=422, detail="LLM role assessment contains malformed topic entries.")
    if not isinstance(difficulty, dict) or set(difficulty) != {"easy", "medium", "hard"}:
        raise HTTPException(status_code=422, detail="LLM role assessment has invalid difficulty weights.")
    difficulty_values = list(difficulty.values())
    if any(not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0 or value > 1 for value in difficulty_values) or abs(sum(difficulty_values) - 1.0) > 0.01:
        raise HTTPException(status_code=422, detail="LLM role assessment has invalid difficulty weights.")

    for round_type in rounds:
        config = round_patterns.get(round_type)
        if not isinstance(config, dict):
            raise HTTPException(status_code=422, detail=f"LLM role assessment is missing round '{round_type}'.")
        focus = config.get("focus_areas")
        weights = config.get("topic_weights")
        if (
            not isinstance(focus, list)
            or not focus
            or any(not isinstance(topic, str) or not topic.strip() for topic in focus)
            or len({topic.casefold() for topic in focus}) != len(focus)
        ):
            raise HTTPException(status_code=422, detail=f"LLM role assessment round '{round_type}' has empty or duplicate topics.")
        if not isinstance(weights, dict) or {str(topic).casefold() for topic in weights} != {str(topic).casefold() for topic in focus}:
            raise HTTPException(status_code=422, detail=f"LLM role assessment round '{round_type}' has incompatible topic weights.")
        values = list(weights.values())
        if any(not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0 for value in values) or abs(sum(values) - 100.0) > 0.1:
            raise HTTPException(status_code=422, detail=f"LLM role assessment round '{round_type}' has invalid topic weights.")
        available = {
            str(item.get("topic", "")).casefold()
            for item in frequency
            if isinstance(item, dict) and item.get("typical_round") == round_type
        }
        if any(str(topic).casefold() not in available for topic in focus):
            raise HTTPException(status_code=422, detail=f"LLM role assessment round '{round_type}' contains incompatible topics.")
        round_difficulty = config.get("difficulty_distribution")
        if not isinstance(round_difficulty, dict) or set(round_difficulty) != {"easy", "medium", "hard"}:
            raise HTTPException(status_code=422, detail=f"LLM role assessment round '{round_type}' has invalid difficulty weights.")
        round_difficulty_values = list(round_difficulty.values())
        if any(not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0 or value > 1 for value in round_difficulty_values) or abs(sum(round_difficulty_values) - 1.0) > 0.01:
            raise HTTPException(status_code=422, detail=f"LLM role assessment round '{round_type}' has invalid difficulty weights.")


def _compute_blueprint_rounds(pattern_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Deterministically calculate blueprint round specifications and topic distributions."""
    rounds_order = (
        pattern_data.get("assessment_rounds")
        or pattern_data.get("rounds")
        or []
    )
    # A pattern with no rounds must NOT be silently padded with default rounds
    # (aptitude/coding/technical). Historical evidence decides the rounds; a TPO
    # can add rounds explicitly. Empty here simply yields an empty blueprint.
    if not isinstance(rounds_order, list):
        rounds_order = []

    round_patterns = pattern_data.get("round_patterns", {})
    topic_frequency = pattern_data.get("topic_frequency", [])
    overall_diff_dist = pattern_data.get(
        "difficulty_distribution", {"easy": 0.25, "medium": 0.50, "hard": 0.25}
    )
    overall_confidence = pattern_data.get("confidence_level", "medium")

    computed_rounds: List[Dict[str, Any]] = []

    for idx, round_key in enumerate(rounds_order, start=1):
        round_type = str(round_key).lower().strip().replace(" ", "_")
        defaults = DEFAULT_ROUND_SPECS.get(
            round_type,
            {
                "name": round_type.replace("_", " ").title(),
                "duration_minutes": 45,
                "question_count": 3,
                "question_types": ["General"],
                "default_difficulty": overall_diff_dist,
                "default_topics": [],
            },
        )

        rp_data = round_patterns.get(round_type, {}) if isinstance(round_patterns, dict) else {}
        # Historical patterns that were generated as incomplete flag the round so
        # blueprint generation rejects missing fields instead of silently using
        # canonical defaults. Legacy/LLM patterns without the flag keep the
        # existing fallback behavior for full backward compatibility.
        requires_config = bool(rp_data.get("requires_tpo_configuration"))

        # ── 1. Duration ───────────────────────────────────────────────
        # Explicit TPO-configured/evidence-exact values win over evidence averages.
        observed_dur = rp_data.get("duration_minutes") or rp_data.get("avg_duration_minutes")
        if isinstance(observed_dur, (int, float)) and observed_dur > 0:
            time_limit = int(observed_dur)
            dur_is_fallback = False
        else:
            time_limit = defaults["duration_minutes"]
            dur_is_fallback = True
        if requires_config and dur_is_fallback:
            label = ROUND_DISPLAY_NAMES.get(round_type, round_type.replace("_", " ").title())
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Historical {label} round requires TPO configuration for round duration before blueprint generation.",
            )

        # ── 2. Question Count ─────────────────────────────────────────
        observed_q_cnt = rp_data.get("question_count") or rp_data.get("avg_question_count")
        if isinstance(observed_q_cnt, (int, float)) and observed_q_cnt > 0:
            q_count = int(observed_q_cnt)
            q_cnt_is_fallback = False
        else:
            q_count = defaults["question_count"]
            q_cnt_is_fallback = True
        if requires_config and q_cnt_is_fallback:
            label = ROUND_DISPLAY_NAMES.get(round_type, round_type.replace("_", " ").title())
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Historical {label} round requires TPO configuration for question count before blueprint generation.",
            )

        # ── 3. Question Types ─────────────────────────────────────────
        if round_type == "aptitude":
            q_types = ["MCQ"]
        elif round_type == "coding":
            q_types = ["Coding"]
        elif round_type == "technical_interview":
            q_types = ["Live Coding", "System Design", "Technical Q&A"]
        elif round_type == "hr_interview":
            q_types = ["Behavioral", "Situational"]
        else:
            q_types = defaults.get("question_types", ["General"])

        # ── 4. Topic Distribution & Weights ───────────────────────────
        topics_for_round, topics_is_fallback = _derive_round_topic_weights(
            round_type=round_type,
            rp_data=rp_data,
            topic_frequency=topic_frequency,
            defaults=defaults,
        )
        if requires_config and topics_is_fallback:
            label = ROUND_DISPLAY_NAMES.get(round_type, round_type.replace("_", " ").title())
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Historical {label} round requires TPO configuration for topic selection before blueprint generation.",
            )

        # ── 5. Difficulty Distribution ────────────────────────────────
        round_diff_dist = rp_data.get("difficulty_distribution") if isinstance(rp_data, dict) else None
        if requires_config and not isinstance(round_diff_dist, dict):
            label = ROUND_DISPLAY_NAMES.get(round_type, round_type.replace("_", " ").title())
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Historical {label} round requires TPO configuration for difficulty distribution before blueprint generation.",
            )
        diff_dist = dict(round_diff_dist or overall_diff_dist) if (round_diff_dist or overall_diff_dist) else defaults["default_difficulty"]

        # Round confidence rating
        is_fallback_round = dur_is_fallback or q_cnt_is_fallback or topics_is_fallback
        if is_fallback_round:
            round_conf = "low (default)" if overall_confidence == "low" else "medium (fallback defaults)"
        else:
            round_conf = overall_confidence

        computed_rounds.append({
            "round_type": round_type,
            "round_order": idx,
            "round_name": ROUND_DISPLAY_NAMES.get(round_type, defaults["name"]),
            "time_limit_minutes": time_limit,
            "question_count": q_count,
            "difficulty_distribution": diff_dist,
            "question_types": q_types,
            "topics": topics_for_round,
            "confidence_level": round_conf,
            "is_default_fallback": is_fallback_round,
        })

    return computed_rounds


def _derive_round_topic_weights(
    round_type: str,
    rp_data: Dict[str, Any],
    topic_frequency: List[Dict[str, Any]],
    defaults: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], bool]:
    """Calculate relative topic weights for a given round based on historical mentions."""
    # Check if explicit focus areas are recorded for this round
    focus_areas = rp_data.get("focus_areas", [])
    matched_topics: List[Dict[str, Any]] = []
    matched_topic_names = set()

    # Map topics from topic_frequency matching this round
    for item in topic_frequency:
        t_name = item.get("topic")
        if not t_name:
            continue
        typical_rnd = item.get("typical_round") or _taxonomy_round_for_topic(t_name)
        category = item.get("category") or get_topic_category(t_name)

        # Match criteria
        matches_round = False
        if typical_rnd == round_type or t_name in focus_areas:
            matches_round = True
        elif not rp_data.get("topic_weights") and round_type == "coding" and category == "Data Structures & Algorithms":
            matches_round = True
        elif not rp_data.get("topic_weights") and round_type == "aptitude" and category == "Aptitude":
            matches_round = True
        elif not rp_data.get("topic_weights") and round_type == "technical_interview" and category in ("Core CS", "Programming Languages", "Data Engineering & Cloud", "AI & Data Science"):
            matches_round = True
        elif not rp_data.get("topic_weights") and round_type == "hr_interview" and category == "Behavioral":
            matches_round = True

        if matches_round and t_name.casefold() not in matched_topic_names:
            matched_topic_names.add(t_name.casefold())
            matched_topics.append({
                "topic": t_name,
                "count": max(item.get("count", 1), 1),
                "category": category,
            })

    if not matched_topics:
        # Fall back to canonical defaults
        default_topics = defaults.get("default_topics", [])
        return [dict(t) for t in default_topics], True

    # Take top 6 topics to maintain focused assessment blueprint
    top_matched = matched_topics[:6]
    explicit_weights = rp_data.get("topic_weights") or {}
    has_explicit_weights = all(t["topic"] in explicit_weights for t in top_matched)
    total_counts = sum(float(explicit_weights[t["topic"]]) if has_explicit_weights else t["count"] for t in top_matched)

    # Compute percentage weights
    weighted_topics: List[Dict[str, Any]] = []
    accumulated_weight = 0.0

    for idx, t in enumerate(top_matched):
        if idx == len(top_matched) - 1:
            # Last topic takes remainder to ensure exact 100% total
            weight = round(100.0 - accumulated_weight, 1)
        else:
            topic_weight = float(explicit_weights[t["topic"]]) if has_explicit_weights else t["count"]
            weight = round((topic_weight / total_counts) * 100.0, 1)
            accumulated_weight += weight

        weighted_topics.append({
            "topic": t["topic"],
            "weight_pct": weight if has_explicit_weights else max(weight, 5.0),
            "category": t["category"],
            "is_default": False,
        })

    return weighted_topics, False


# ── TPO Blueprint CRUD & Review ───────────────────────────────────────

def get_blueprint(db: Session, company_name: str, target_role: str) -> CompanyBlueprint:
    """Retrieve blueprint for a specific company + role."""
    company, role = _normalize_key(company_name, target_role)
    # Trim the STORED identity too: a persisted row carrying edge whitespace
    # must stay reachable through the same case-insensitive, trimmed comparison
    # used by list_blueprints. Identity stays exact otherwise (no substring
    # matching), so a different company/role still 404s.
    bp = (
        db.query(CompanyBlueprint)
        .filter(
            func.lower(func.trim(CompanyBlueprint.company_name)) == company.lower(),
            func.lower(func.trim(CompanyBlueprint.target_role)) == role.lower(),
        )
        .first()
    )
    if not bp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No assessment blueprint found for company='{company}', role='{role}'.",
        )
    return bp


def list_blueprints(
    db: Session,
    company_name: Optional[str] = None,
    target_role: Optional[str] = None,
    status_filter: Optional[str] = None,
) -> List[CompanyBlueprint]:
    """List all blueprints with optional company, role, or status filters."""
    q = db.query(CompanyBlueprint)
    # Mock Drive supplies both identity fields and asks only for approved
    # blueprints. In that case, use the same trimmed, case-insensitive identity
    # comparison as the single-blueprint lookup instead of substring matching.
    exact_identity = bool(company_name and target_role and status_filter)
    if company_name:
        company = company_name.strip()
        if exact_identity:
            q = q.filter(func.lower(func.trim(CompanyBlueprint.company_name)) == company.lower())
        else:
            q = q.filter(CompanyBlueprint.company_name.ilike(f"%{company}%"))
    if target_role:
        role = target_role.strip()
        if exact_identity:
            q = q.filter(func.lower(func.trim(CompanyBlueprint.target_role)) == role.lower())
        else:
            q = q.filter(CompanyBlueprint.target_role.ilike(f"%{role}%"))
    if status_filter:
        q = q.filter(func.lower(CompanyBlueprint.status) == status_filter.strip().lower())
    q = q.order_by(CompanyBlueprint.version.desc(), CompanyBlueprint.updated_at.desc())
    if exact_identity and status_filter.strip().lower() == "approved":
        q = q.limit(1)
    return q.all()


def update_blueprint(
    db: Session,
    company_name: str,
    target_role: str,
    payload: UpdateBlueprintRequest,
    user_id: int,
) -> CompanyBlueprint:
    """TPO edit action: update rounds, topics, difficulty, or notes of a blueprint."""
    bp = get_blueprint(db, company_name, target_role)

    bdata = dict(bp.blueprint_data or {})
    original_content = dict(bdata)
    original_content.pop("updated_at", None)

    if payload.rounds is not None:
        rounds_list = []
        for r in payload.rounds:
            rounds_list.append(r.model_dump())
        bdata["rounds"] = rounds_list

    if payload.overall_difficulty is not None:
        bdata["overall_difficulty"] = payload.overall_difficulty

    existing_competencies = (bp.blueprint_data or {}).get("competencies")

    if payload.competencies is not None:
        bdata["competencies"] = [c.model_dump() for c in payload.competencies]

    if payload.blueprint_data is not None:
        bdata.update(payload.blueprint_data)

    # Competency configuration policy, kept consistent between request-schema
    # validation (``UpdateBlueprintRequest``) and this service:
    #   * omitted            -> preserve the existing configuration.
    #   * explicit JSON null -> preserve the existing configuration (never clear).
    #   * empty list         -> rejected (422); a configured set must be non-empty.
    #   * valid list         -> normalized and persisted.
    #   * invalid/malformed  -> structured 422, never a raw 500 or silent clear.
    # Legacy blueprints without a configuration are never touched unless the
    # caller explicitly supplies one.
    if "competencies" in bdata:
        configured = bdata["competencies"]
        if configured is None:
            if existing_competencies is None:
                bdata.pop("competencies", None)
            else:
                bdata["competencies"] = existing_competencies
        else:
            try:
                parsed = [BlueprintCompetency.model_validate(item) for item in configured]
                validate_competency_configuration(parsed)
            except (ValidationError, ValueError, TypeError) as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid competency configuration: {exc}",
                ) from exc
            bdata["competencies"] = [c.model_dump() for c in parsed]

    if payload.review_notes is not None:
        bp.review_notes = payload.review_notes

    updated_content = dict(bdata)
    updated_content.pop("updated_at", None)
    if updated_content != original_content:
        # Drives and assessment contexts pin snapshots by (blueprint_id,
        # version). Reusing a version for changed content makes a historical
        # snapshot impossible to distinguish from the current blueprint.
        bp.version = (bp.version or 0) + 1
        bdata["version"] = bp.version
    else:
        # Keep the JSON and relational version fields aligned, including for
        # legacy records where the JSON value was absent or stale.
        bdata["version"] = bp.version

    bdata["updated_at"] = datetime.now(timezone.utc).isoformat()
    bp.blueprint_data = bdata
    db.commit()
    db.refresh(bp)
    return bp


def approve_blueprint(
    db: Session,
    company_name: str,
    target_role: str,
    status_val: str,
    notes: Optional[str],
    user_id: int,
) -> CompanyBlueprint:
    """TPO approval action: transition blueprint status to 'approved'."""
    bp = get_blueprint(db, company_name, target_role)

    bp.status = status_val
    bp.reviewed_by_id = user_id
    bp.reviewed_at = datetime.now(timezone.utc)
    if notes:
        bp.review_notes = notes

    bdata = dict(bp.blueprint_data or {})
    bdata["status"] = status_val
    bdata["reviewed_at"] = bp.reviewed_at.isoformat()
    bdata["review_notes"] = notes
    bp.blueprint_data = bdata

    db.commit()
    db.refresh(bp)
    return bp


def delete_blueprint(db: Session, blueprint_id: int) -> None:
    """Delete a company blueprint record."""
    bp = db.query(CompanyBlueprint).filter(CompanyBlueprint.id == blueprint_id).first()
    if not bp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Blueprint id={blueprint_id} not found.",
        )
    db.delete(bp)
    db.commit()
