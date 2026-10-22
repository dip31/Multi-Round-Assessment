"""Explicit no-history role assessment generation using the existing Groq client."""

import re
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import HTTPException, status
from groq import APIStatusError, RateLimitError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.models.company_data import CompanyHistoricalData, CompanyPattern, CompanyBlueprint
from app.schemas.company_data import RoleAssessmentDefinition, RoleAssessmentGenerationRequest
from app.services.edi5_benchmark_seeds import EDI5_BENCHMARKS, benchmark_role_compatible
from app.services.groq_service import GroqService
from app.services.topic_taxonomy import get_topic_category, normalize_topic


def _has_compatible_historical_evidence(db: Session, company: str, role: str) -> bool:
    rows = db.query(CompanyHistoricalData).filter(
        func.lower(func.trim(CompanyHistoricalData.company_name)) == company.lower(),
        func.lower(func.trim(CompanyHistoricalData.target_role)) == role.lower(),
    ).all()
    for row in rows:
        data = row.raw_data or {}
        provenance = data.get("source_provenance") or {}
        # Existing generic fallback rows are explicitly not evidence for this new path.
        if provenance.get("classification") == "generic_fallback":
            continue
        if row.source_type != "pre_seeded":
            return True
        reference = data.get("benchmark_reference", "")
        benchmark_name = reference.rsplit(" - ", 1)[0].strip() if reference else ""
        benchmark = next((item for item in EDI5_BENCHMARKS if item["company_name"].lower() == benchmark_name.lower()), None)
        if benchmark:
            if benchmark["company_name"] == "Generic Benchmark":
                continue
            if benchmark_role_compatible(role, benchmark):
                return True
    return False


def _cap_round_topics(raw_definition: Any) -> Any:
    """Keep LLM round topics within the schema limit (models sometimes overshoot).

    Keeps the highest-weighted topics, then renormalizes their weights to 100 so
    the strict topic_weights validator still holds. TPO configuration is untouched.
    """
    rounds = raw_definition.get("rounds") if isinstance(raw_definition, dict) else None
    if not isinstance(rounds, dict):
        return raw_definition
    for config in rounds.values():
        if not isinstance(config, dict):
            continue
        topics = config.get("topics")
        weights = config.get("topic_weights")
        if not isinstance(topics, list) or not isinstance(weights, dict) or len(topics) <= 6:
            continue
        weight_by_key = {str(key).strip().casefold(): float(value) for key, value in weights.items()}
        ranked = [
            topic for topic in topics
            if isinstance(topic, str) and str(topic).strip().casefold() in weight_by_key
        ]
        ranked.sort(key=lambda topic: weight_by_key[str(topic).strip().casefold()], reverse=True)
        kept = ranked[:6]
        kept_weights = {topic: weight_by_key[str(topic).strip().casefold()] for topic in kept}
        total = sum(kept_weights.values())
        if total > 0:
            kept_weights = {topic: round(weight * 100.0 / total, 2) for topic, weight in kept_weights.items()}
            drift = round(100.0 - sum(kept_weights.values()), 2)
            largest = max(kept_weights, key=kept_weights.get)
            kept_weights[largest] = round(kept_weights[largest] + drift, 2)
        else:
            kept_weights = {topic: round(100.0 / len(kept), 2) for topic in kept}
        config["topics"] = kept
        config["topic_weights"] = kept_weights
    return raw_definition


def _to_pattern_data(
    definition: RoleAssessmentDefinition,
    requested_rounds: list[dict],
    company_name: str,
    target_role: str,
) -> Dict[str, Any]:
    all_topics = []
    topic_frequency = []
    round_patterns = {}
    round_difficulties = []
    for round_request in requested_rounds:
        round_type = round_request["round_type"]
        config = definition.rounds[round_type]
        normalized_topics = []
        weights_by_normalized_topic = {}
        for topic in config.topics:
            canonical = normalize_topic(topic) or " ".join(topic.split())
            if not canonical.strip() or canonical.casefold() in weights_by_normalized_topic:
                raise ValueError("LLM topics must remain non-empty and unique after normalization")
            normalized_topics.append(canonical)
            original_weight = next(value for key, value in config.topic_weights.items() if key.casefold() == topic.casefold())
            weights_by_normalized_topic[canonical.casefold()] = (canonical, float(original_weight))
            all_topics.append(canonical)
            topic_frequency.append({
                "topic": canonical,
                "count": 1,
                "sources_count": 0,
                # LLM topics have no historical source-frequency, so report the
                # role-assessment's own canonical weight (already a 0-100 per-round
                # percentage) rather than a fabricated 0%.
                "frequency_pct": round(float(original_weight), 2),
                "category": get_topic_category(canonical),
                "typical_round": round_type,
            })
        explicit_weights = {name: weight for name, weight in weights_by_normalized_topic.values()}
        round_patterns[round_type] = {
            "focus_areas": normalized_topics,
            "topic_weights": explicit_weights,
            "difficulty_distribution": round_request["difficulty_distribution"],
            "question_count": round_request["question_count"],
            "duration_minutes": round_request["duration_minutes"],
            "sources_count": 0,
        }
        round_difficulties.append(round_request["difficulty_distribution"])

    # Preserve drive-selected difficulty values; these are configuration, not evidence.
    difficulty_distribution = {
        key: round(sum(item[key] for item in round_difficulties) / len(round_difficulties), 4)
        for key in ("easy", "medium", "hard")
    }
    return {
        "assessment_rounds": [item["round_type"] for item in requested_rounds],
        "topics": {topic: 1 for topic in dict.fromkeys(all_topics)},
        "topic_frequency": topic_frequency,
        "question_types": {},
        "difficulty_distribution": difficulty_distribution,
        "avg_difficulty": max(difficulty_distribution, key=difficulty_distribution.get),
        "round_patterns": round_patterns,
        "year_range": [],
        "source_count": 0,
        "evidence_count": 0,
        "confidence_level": "low (LLM-generated; no historical evidence)",
        "confidence_score": 0.4,
        "confidence_reasons": "Role assessment generated by LLM; no company historical evidence was used.",
        "sources_summary": [],
        "role_understanding": definition.role_understanding.model_dump(),
        "review_status": "pending_review",
        "is_fallback": False,
        "source_provenance": {
            "classification": "llm_role_assessment",
            "generation_method": "llm_role_assessment",
            "generation_source": "groq",
            "selection_status": "no_compatible_evidence_found",
            "requested_company": company_name,
            "requested_role": target_role,
            "historical_source_count": 0,
            "historical_evidence_used": False,
            "empirical_source_count": 0,
            "pre_seeded_source_count": 0,
            "explicit_fallback_requested": False,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _rate_limit_http_error(exc: Exception) -> HTTPException:
    """Map an upstream Groq 429 to a client-facing 429 with a retry hint."""
    match = re.search(r"Please try again in ([0-9]+(?:\.[0-9]+)?(?:m[0-9.]+)?s)", str(exc))
    retry_hint = f"Retry in about {match.group(1)}." if match else "Please retry in a few minutes."
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={
            "code": "GROQ_RATE_LIMITED",
            "message": f"Groq rate limit reached while generating the role assessment. {retry_hint}",
        },
    )


def _generation_failed_http_error(exc: Exception) -> HTTPException:
    """Keep genuine provider/output/validation failures on the existing 502 contract."""
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail={"code": "ROLE_ASSESSMENT_GENERATION_FAILED", "message": str(exc) or "The role assessment response was invalid."},
    )


def generate_role_assessment_pattern(
    db: Session,
    payload: RoleAssessmentGenerationRequest,
    created_by_id: int,
    *,
    llm_generator=None,
) -> CompanyPattern:
    """Generate and persist a pending-review pattern only for a genuine no-history case."""
    company = payload.company_name.strip()
    role = payload.target_role.strip()
    if _has_compatible_historical_evidence(db, company, role):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "HISTORICAL_EVIDENCE_AVAILABLE", "message": "Compatible historical evidence exists; use the existing historical pattern flow."},
        )

    existing_pattern = db.query(CompanyPattern).filter(
        func.lower(func.trim(CompanyPattern.company_name)) == company.lower(),
        func.lower(func.trim(CompanyPattern.target_role)) == role.lower(),
    ).first()
    existing_blueprint = db.query(CompanyBlueprint).filter(
        func.lower(func.trim(CompanyBlueprint.company_name)) == company.lower(),
        func.lower(func.trim(CompanyBlueprint.target_role)) == role.lower(),
    ).first()
    pattern_provenance = ((existing_pattern.pattern_data or {}).get("source_provenance") or {}) if existing_pattern else {}
    replace_existing_role_pattern = bool(
        existing_pattern
        and pattern_provenance.get("classification") in {"generic_fallback", "llm_role_assessment"}
    )
    if (existing_pattern and not replace_existing_role_pattern) or existing_blueprint:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "ROLE_ASSESSMENT_ALREADY_EXISTS", "message": "A pattern or blueprint already exists for this company and role. Existing assessment data was not changed."},
        )

    generator = llm_generator
    if generator is None:
        if not settings.GROQ_API_KEY:
            raise HTTPException(status_code=503, detail={"code": "ROLE_ASSESSMENT_GENERATION_FAILED", "message": "Role assessment generation is unavailable: GROQ_API_KEY is not configured."})

    context = {
        "company_name": company,
        "target_role": role,
        "job_description": payload.job_description,
        "company_evidence": None,
        "rounds": payload.rounds,
    }
    try:
        if generator is None:
            client = GroqService(settings.GROQ_API_KEY)
            generator = client.generate_role_assessment_definition
        raw_definition = generator(context)
        definition = RoleAssessmentDefinition.model_validate(_cap_round_topics(raw_definition))
        requested_round_types = [item["round_type"] for item in payload.rounds]
        if set(definition.rounds) != set(requested_round_types):
            raise ValueError("LLM output rounds do not match the requested rounds")
        if definition.role.strip().casefold() != role.casefold():
            raise ValueError("LLM output role does not match the requested role")
        pattern_data = _to_pattern_data(definition, payload.rounds, company, role)
    except RateLimitError as exc:
        raise _rate_limit_http_error(exc) from exc
    except APIStatusError as exc:
        if getattr(exc, "status_code", None) == status.HTTP_429_TOO_MANY_REQUESTS:
            raise _rate_limit_http_error(exc) from exc
        raise _generation_failed_http_error(exc) from exc
    except Exception as exc:
        raise _generation_failed_http_error(exc) from exc

    if replace_existing_role_pattern:
        pattern = existing_pattern
        pattern.pattern_data = pattern_data
        pattern.source_count = 0
        pattern.created_by_id = created_by_id
    else:
        pattern = CompanyPattern(
            company_name=company,
            target_role=role,
            pattern_data=pattern_data,
            source_count=0,
            created_by_id=created_by_id,
        )
        db.add(pattern)
    db.commit()
    db.refresh(pattern)
    return pattern
