"""
Pydantic v2 schemas for interview question personalization and contextual follow-up data structures.
"""

from pydantic import BaseModel, Field
from typing import List, Literal, Optional


class ResumeExtractionResult(BaseModel):
    """Result of resume extraction validation."""

    is_valid: bool
    extraction_confidence: Literal["HIGH", "MEDIUM", "LOW"]
    skills_count: int
    projects_count: int
    issues: List[str] = Field(default_factory=list)
    recommendation: Literal["PROCEED", "RETRY", "FALLBACK_MODE"]
    retry_count: int = 0
    alternative_extraction_attempted: bool = False


class PersonalizationSource(BaseModel):
    """Which resume content a question is grounded in."""

    skill: Optional[str] = None
    project: Optional[str] = None
    reference_type: Literal["skill", "project", "role"]
    matching_evidence: str
    confidence: float = Field(ge=0.0, le=1.0)


class QuestionValidationResult(BaseModel):
    """Result of validating a single question's resume grounding."""

    is_valid: bool
    grounding_confidence_score: float = Field(ge=0.0, le=1.0)
    personalization_source: Optional[PersonalizationSource] = None
    recommendation: Literal["ACCEPT", "REGENERATE", "FALLBACK"]
    regeneration_attempt: int = 0
    is_fallback: bool = False
    fallback_reason: Optional[str] = None


class AnswerClassificationResult(BaseModel):
    """Domain-aware classification of a candidate answer."""

    quality: Literal["SHORT", "PARTIAL", "COMPLETE", "EXCELLENT"]
    intent: Literal["POSITIVE", "NEUTRAL", "NEGATIVE"]
    content_score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    missing_aspects: List[str] = Field(default_factory=list)
    domain_markers: List[str] = Field(default_factory=list)
    depth_indicators: dict = Field(default_factory=dict)
    fallback_followup_type: Literal[
        "elaboration", "clarification", "depth_probe", "error_recovery"
    ] = "elaboration"
    reasoning: str = ""


class ContextualFollowupResult(BaseModel):
    """Result of contextual follow-up generation."""

    followup_question: str
    followup_type: Literal["clarification", "depth_probe", "error_recovery"]
    grounding_score: float = Field(ge=0.0, le=1.0)
    grounding_evidence: str = ""
    targeted_missing_aspect: Optional[str] = None
    validation_status: Literal["high_confidence", "low_confidence", "fallback"]
    includes_answer_reference: bool = False
    includes_gap_reference: bool = False


class PerQuestionMetric(BaseModel):
    """Metrics for a single question in an interview."""

    question_number: int
    question_text: str
    personalization_source: Optional[str] = None
    grounding_confidence: Optional[float] = None
    answer_quality: Optional[str] = None
    answer_classification_confidence: Optional[float] = None
    missing_aspects: List[str] = Field(default_factory=list)
    followups: List[dict] = Field(default_factory=list)
    average_followup_grounding: float = 0.0


class InterviewMetadataSummary(BaseModel):
    """Final summary of interview quality metadata."""

    total_questions: int
    total_followups: int
    average_followup_grounding: float
    personalization_quality_score: float
    follow_up_quality_score: float
    warnings: List[str] = Field(default_factory=list)
