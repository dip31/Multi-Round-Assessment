"""
Pydantic schemas for Phase 4A: Company Historical Data & Pattern Foundation.
"""

from datetime import datetime
import math
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ── Historical Data schemas ───────────────────────────────────────────

class CompanyHistoricalDataCreate(BaseModel):
    """Request body for manually adding a historical drive record."""
    company_name: str = Field(..., min_length=1, max_length=200)
    target_role: str = Field(..., min_length=1, max_length=150)
    label: str = Field("Historical Drive", max_length=200)
    raw_data: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Structured historical drive data. "
            "Supported keys: year (int), rounds (list[str]), topics (list[str]), "
            "question_types (list[str]), difficulty (str: easy|medium|hard), "
            "duration_minutes (int), notes (str)"
        ),
    )


class CompanyHistoricalDataResponse(BaseModel):
    id: int
    company_name: str
    target_role: str
    source_type: str
    label: str
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    raw_data: Dict[str, Any] = {}
    created_by_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Pattern schemas ───────────────────────────────────────────────────

class TpoRoundConfiguration(BaseModel):
    """TPO-provided configuration for a single evidence-supported round.

    Mirrors the per-round validation enforced for the no-history LLM
    ``RoleAssessmentGenerationRequest`` rounds. ``focus_areas`` is optional so
    existing configurations (and rounds with no evidence-backed topics) remain
    compatible; supplied topics are validated against the pattern's
    ``topic_frequency`` during configuration application.
    """
    round_type: str
    question_count: Any = None
    duration_minutes: Any = None
    difficulty_distribution: Any = None
    focus_areas: Optional[List[str]] = None

    @field_validator("round_type")
    @classmethod
    def validate_round_type(cls, value):
        round_type = str(value).strip().lower()
        if round_type not in {"aptitude", "coding", "technical_interview", "hr_interview"}:
            raise ValueError("round_type must be a supported assessment round")
        return round_type

    @field_validator("question_count")
    @classmethod
    def validate_question_count(cls, value):
        if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 100:
            raise ValueError("question_count must be between 1 and 100")
        return value

    @field_validator("duration_minutes")
    @classmethod
    def validate_duration_minutes(cls, value):
        if not isinstance(value, int) or isinstance(value, bool) or not 5 <= value <= 300:
            raise ValueError("duration_minutes must be between 5 and 300")
        return value

    @field_validator("difficulty_distribution")
    @classmethod
    def validate_difficulty_distribution(cls, value):
        if not isinstance(value, dict) or set(value) != {"easy", "medium", "hard"}:
            raise ValueError("difficulty_distribution must contain easy, medium, and hard")
        if any(not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 or v > 1 for v in value.values()) or abs(sum(value.values()) - 1) > 0.01:
            raise ValueError("difficulty_distribution must contain supported weights summing to 1")
        return value

    @field_validator("focus_areas")
    @classmethod
    def validate_focus_areas(cls, value):
        if value is None:
            return None
        if not isinstance(value, list):
            raise ValueError("focus_areas must be a list of topic names when provided")
        topics = [str(topic).strip() for topic in value]
        if any(not topic for topic in topics) or len(set(topic.casefold() for topic in topics)) != len(topics):
            raise ValueError("focus_areas must contain non-empty, unique topic names")
        return topics


class GeneratePatternRequest(BaseModel):
    company_name: Optional[str] = None
    target_role: Optional[str] = None
    use_fallback: Optional[bool] = False
    added_rounds: Optional[List[str]] = Field(
        None,
        description=(
            "Assessment rounds the TPO explicitly wants in the historical "
            "pattern even though they were not present in the evidence. Rounds "
            "are appended in the given order and tagged as TPO-added. Only "
            "supported assessment rounds are accepted; evidence rounds are never "
            "downgraded."
        ),
    )
    round_configuration: Optional[List[TpoRoundConfiguration]] = Field(
        None,
        description=(
            "Optional explicit TPO round configuration applied to the historical "
            "pattern. Only rounds present in the evidence (or explicitly added via "
            "added_rounds) are accepted. Fields left unset in the pattern remain "
            "flagged as requiring TPO configuration."
        ),
    )
    deselected_rounds: Optional[List[str]] = Field(
        None,
        description=(
            "Assessment rounds the TPO explicitly deselected from the historical "
            "pattern. A deselected round is distinguishable from an unspecified "
            "round: unspecified rounds keep their evidence default, deselected "
            "rounds are removed from the effective pattern while their historical "
            "evidence is preserved. Evidence rounds are never deleted."
        ),
    )

    @field_validator("added_rounds")
    @classmethod
    def validate_added_rounds(cls, values):
        if not values:
            return values
        supported = {"aptitude", "coding", "technical_interview", "hr_interview"}
        normalized = [str(value).strip().lower().replace(" ", "_") for value in values]
        if any(not value or value not in supported for value in normalized):
            raise ValueError("added_rounds contains an unsupported assessment round")
        if len(set(normalized)) != len(normalized):
            raise ValueError("added_rounds must be unique")
        return normalized

    @field_validator("deselected_rounds")
    @classmethod
    def validate_deselected_rounds(cls, values):
        if not values:
            return values
        supported = {"aptitude", "coding", "technical_interview", "hr_interview"}
        normalized = [str(value).strip().lower().replace(" ", "_") for value in values]
        if any(not value or value not in supported for value in normalized):
            raise ValueError("deselected_rounds contains an unsupported assessment round")
        if len(set(normalized)) != len(normalized):
            raise ValueError("deselected_rounds must be unique")
        return normalized

    @field_validator("round_configuration")
    @classmethod
    def validate_unique_rounds(cls, values):
        if not values:
            return values
        seen = set()
        for cfg in values:
            if cfg.round_type in seen:
                raise ValueError("round_configuration rounds must be unique")
            seen.add(cfg.round_type)
        return values


class SeedBenchmarkRequest(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=200)
    target_role: str = Field(..., min_length=1, max_length=150)


class RoleAssessmentGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    company_name: str = Field(..., min_length=1, max_length=200)
    target_role: str = Field(..., min_length=1, max_length=150)
    rounds: List[Dict[str, Any]] = Field(..., min_length=1, max_length=4)
    job_description: Optional[str] = Field(None, max_length=12000)

    @field_validator("rounds")
    @classmethod
    def validate_rounds(cls, values):
        allowed = {"aptitude", "coding", "technical_interview", "hr_interview"}
        normalized = []
        for value in values:
            if not isinstance(value, dict):
                raise ValueError("each round must include its configuration")
            if set(value) != {"round_type", "question_count", "duration_minutes", "difficulty_distribution"}:
                raise ValueError("round configuration contains unsupported fields")
            round_type = str(value.get("round_type", "")).strip().lower()
            if round_type not in allowed or round_type in normalized:
                raise ValueError("rounds must be unique supported assessment round types")
            count = value.get("question_count")
            duration = value.get("duration_minutes")
            difficulty = value.get("difficulty_distribution")
            if not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= 100:
                raise ValueError("question_count must be between 1 and 100")
            if not isinstance(duration, int) or isinstance(duration, bool) or not 5 <= duration <= 300:
                raise ValueError("duration_minutes must be between 5 and 300")
            if not isinstance(difficulty, dict) or set(difficulty) != {"easy", "medium", "hard"}:
                raise ValueError("difficulty_distribution must contain easy, medium, and hard")
            if any(not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 or v > 1 for v in difficulty.values()) or abs(sum(difficulty.values()) - 1) > 0.01:
                raise ValueError("difficulty_distribution must contain supported weights summing to 1")
            normalized.append(round_type)
            value["round_type"] = round_type
        return values

    @field_validator("company_name", "target_role")
    @classmethod
    def trim_required_text(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value


class RoleUnderstandingOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=1)
    responsibilities: List[str] = Field(min_length=1, max_length=20)
    core_skills: List[str] = Field(min_length=1, max_length=30)
    tools_and_technologies: List[str] = Field(default_factory=list, max_length=30)
    competencies: List[str] = Field(min_length=1, max_length=20)

    @field_validator("summary")
    @classmethod
    def trim_summary(cls, value):
        if not value.strip():
            raise ValueError("summary must not be blank")
        return value.strip()

    @field_validator("responsibilities", "core_skills", "tools_and_technologies", "competencies")
    @classmethod
    def validate_string_lists(cls, values):
        cleaned = [value.strip() for value in values]
        if any(not value for value in cleaned):
            raise ValueError("list items must not be blank")
        if len({value.casefold() for value in cleaned}) != len(cleaned):
            raise ValueError("list items must be unique")
        return cleaned


class RoleAssessmentRoundOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topics: List[str] = Field(min_length=1, max_length=6)
    topic_weights: Dict[str, float]

    @model_validator(mode="after")
    def validate_weights(self):
        topics = [topic.strip().casefold() for topic in self.topics]
        if any(not topic for topic in topics) or len(set(topics)) != len(topics):
            raise ValueError("round topics must be non-empty and unique")
        normalized_weight_items = [(key.strip().casefold(), value) for key, value in self.topic_weights.items()]
        normalized_weights = dict(normalized_weight_items)
        if len(normalized_weights) != len(normalized_weight_items):
            raise ValueError("topic weight keys must be unique")
        if set(normalized_weights) != set(topics) or any(not math.isfinite(value) or value <= 0 for value in normalized_weights.values()):
            raise ValueError("topic weights must be positive and match the topics exactly")
        if abs(sum(normalized_weights.values()) - 100.0) > 0.1:
            raise ValueError("topic weights must sum to 100")
        self.topics = [topic.strip() for topic in self.topics]
        self.topic_weights = {topic: normalized_weights[topic.casefold()] for topic in self.topics}
        return self


class RoleAssessmentDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str = Field(min_length=1)
    role_understanding: RoleUnderstandingOutput
    rounds: Dict[str, RoleAssessmentRoundOutput]

    @field_validator("role")
    @classmethod
    def trim_definition_text(cls, value):
        if not value.strip():
            raise ValueError("value must not be blank")
        return value.strip()

    @field_validator("rounds")
    @classmethod
    def validate_output_round_keys(cls, values):
        allowed = {"aptitude", "coding", "technical_interview", "hr_interview"}
        if not values or any(key not in allowed for key in values):
            raise ValueError("rounds contains an unsupported round or is empty")
        return values


class ReviewPatternRequest(BaseModel):
    status: str = Field("approved", description="Review status: approved | needs_revision")
    notes: Optional[str] = Field(None, max_length=1000)


class CompanyPatternResponse(BaseModel):
    id: int
    company_name: str
    target_role: str
    pattern_data: Dict[str, Any] = {}
    source_count: int
    created_by_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Blueprint schemas (Phase 4B) ──────────────────────────────────────

class TopicWeight(BaseModel):
    topic: str
    weight_pct: float
    category: Optional[str] = "General"
    is_default: bool = False


class BlueprintRoundConfig(BaseModel):
    round_type: str = Field(..., description="aptitude | coding | technical_interview | hr_interview")
    round_order: int = Field(..., ge=1)
    round_name: str
    time_limit_minutes: int = Field(..., ge=5, le=300)
    question_count: int = Field(..., ge=1, le=100)
    difficulty_distribution: Dict[str, float] = Field(
        default_factory=lambda: {"easy": 0.25, "medium": 0.50, "hard": 0.25}
    )
    question_types: List[str] = Field(default_factory=list)
    topics: List[TopicWeight] = Field(default_factory=list)
    confidence_level: str = "medium"
    is_default_fallback: bool = False


class BlueprintCompetency(BaseModel):
    """Optional blueprint-level competency configuration (Phase 4C Part 4).

    Competencies are an additive, optional layer over the existing round/topic
    blueprint. They are configured by the TPO and persisted inside
    ``blueprint_data["competencies"]`` so they flow into the pinned snapshot.
    Legacy blueprints without this block remain valid and unaffected.

    ``id`` is an optional stable identifier; when omitted, the (normalized)
    ``name`` is used as the stable identifier for evidence mapping.
    """

    model_config = ConfigDict(extra="forbid")

    id: Optional[str] = Field(None, max_length=80)
    name: str = Field(..., min_length=1, max_length=200)
    weight_pct: float
    topics: List[str] = Field(..., min_length=1)

    @field_validator("id")
    @classmethod
    def trim_optional_id(cls, value):
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("name")
    @classmethod
    def trim_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("competency name must not be blank")
        return value

    @field_validator("weight_pct")
    @classmethod
    def validate_weight(cls, value):
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(value)
            or value <= 0
            or value > 100
        ):
            raise ValueError("competency weight_pct must be a positive number up to 100")
        return float(value)

    @field_validator("topics")
    @classmethod
    def validate_topics(cls, value):
        topics = [str(topic).strip() for topic in value]
        if any(not topic for topic in topics):
            raise ValueError("competency topics must not be blank")
        if len({topic.casefold() for topic in topics}) != len(topics):
            raise ValueError("competency topics must be unique")
        return topics


def validate_competency_configuration(
    competencies: List[BlueprintCompetency],
) -> List[BlueprintCompetency]:
    """Validate a configured competency set across items.

    Only applied when a blueprint explicitly carries a competency
    configuration; legacy blueprints without one are never validated.
    """
    if not competencies:
        raise ValueError("competency configuration must contain at least one competency")
    names = [competency.name.casefold() for competency in competencies]
    if len(set(names)) != len(names):
        raise ValueError("competency names must be unique")
    ids = [competency.id.casefold() for competency in competencies if competency.id]
    if len(set(ids)) != len(ids):
        raise ValueError("competency ids must be unique")
    total = sum(competency.weight_pct for competency in competencies)
    if abs(total - 100.0) > 0.1:
        raise ValueError("competency weights must sum to 100")
    return competencies


class GenerateBlueprintRequest(BaseModel):
    company_name: Optional[str] = None
    target_role: Optional[str] = None
    force: Optional[bool] = False


class UpdateBlueprintRequest(BaseModel):
    rounds: Optional[List[BlueprintRoundConfig]] = None
    overall_difficulty: Optional[str] = None
    review_notes: Optional[str] = None
    blueprint_data: Optional[Dict[str, Any]] = None
    competencies: Optional[List[BlueprintCompetency]] = None

    @model_validator(mode="after")
    def validate_competencies(self):
        if self.competencies is not None:
            validate_competency_configuration(self.competencies)
        return self


class ReviewBlueprintRequest(BaseModel):
    status: str = Field("approved", description="Review status: approved | draft | needs_revision")
    notes: Optional[str] = Field(None, max_length=1000)


class CompanyBlueprintResponse(BaseModel):
    id: int
    company_name: str
    target_role: str
    status: str
    version: int
    confidence_level: str
    evidence_sources_count: int
    blueprint_data: Dict[str, Any] = {}
    review_notes: Optional[str] = None
    reviewed_by_id: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    created_by_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
