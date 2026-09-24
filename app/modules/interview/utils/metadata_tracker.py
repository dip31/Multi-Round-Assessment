"""
Interview Metadata Tracker.

Tracks personalization and contextual grounding quality metrics throughout an
interview session, persists them to the database, and computes summary scores
that can trigger quality warnings.
"""

from datetime import datetime
from typing import Dict, List, Optional


class InterviewMetadataTracker:
    """
    Aggregates and persists interview quality metadata for a single session.

    Tracked dimensions (design.md §6):
      - extraction_metadata      : extraction confidence, skill/project counts, issues
      - question_pool_metadata   : retrieval success rate, personalization rate, fallback count
      - per_question_metrics     : per-turn grounding, classification, and follow-up data
      - interview_summary        : aggregate quality scores and warnings

    Score thresholds:
      - personalization_quality_score ≥ 0.60 is acceptable
      - follow_up_quality_score       ≥ 0.65 is acceptable
    """

    PERSONALIZATION_WARNING_THRESHOLD: float = 0.60
    FOLLOWUP_WARNING_THRESHOLD: float = 0.65

    def __init__(self, interview_id: int) -> None:
        """
        Initialise the tracker for a specific interview session.

        Args:
            interview_id: Database ID of the interview session.
        """
        self.interview_id = interview_id
        self.extraction_metadata: Dict = {}
        self.question_pool_metadata: Dict = {}
        self.per_question_metrics: List[Dict] = []
        self._warnings: List[str] = []

    def record_extraction_result(
        self,
        extraction_confidence: str,
        skills_count: int,
        projects_count: int,
        issues: List[str],
        alternative_extraction_attempted: bool = False,
    ) -> None:
        """
        Store the outcome of resume extraction validation.

        Args:
            extraction_confidence: HIGH / MEDIUM / LOW confidence level.
            skills_count: Number of distinct skills extracted.
            projects_count: Number of projects with non-empty descriptions.
            issues: List of issues found during extraction (e.g., "too_few_skills").
            alternative_extraction_attempted: Whether a re-extraction was attempted.
        """
        raise NotImplementedError

    def record_question_pool_metadata(
        self,
        retrieval_success_rate: float,
        question_personalization_rate: float,
        questions_with_fallback: int,
        average_grounding_confidence: float,
    ) -> None:
        """
        Store statistics about the generated question pool.

        Args:
            retrieval_success_rate: Fraction of skills that had relevant RAG docs.
            question_personalization_rate: Fraction of questions meeting the 0.75 threshold.
            questions_with_fallback: Count of questions replaced by fallback.
            average_grounding_confidence: Mean confidence score across the pool.
        """
        raise NotImplementedError

    def record_question_turn(
        self,
        question_number: int,
        question_text: str,
        personalization_source: Optional[str],
        grounding_confidence: Optional[float],
        answer_quality: Optional[str] = None,
        answer_classification_confidence: Optional[float] = None,
        missing_aspects: Optional[List[str]] = None,
    ) -> None:
        """
        Initialise a per-question metrics entry for a new interview turn.

        Should be called when a question is presented to the candidate.

        Args:
            question_number: 1-based index of the question in the interview.
            question_text: Full text of the question.
            personalization_source: Skill or project the question references.
            grounding_confidence: Confidence score for this question's grounding.
            answer_quality: Classification quality category (populated after answer).
            answer_classification_confidence: Classifier confidence (populated after answer).
            missing_aspects: Gaps identified in the answer (populated after answer).
        """
        raise NotImplementedError

    def record_followup_turn(
        self,
        question_number: int,
        followup_number: int,
        followup_text: str,
        followup_type: str,
        grounding_score: float,
        targeted_aspect: Optional[str],
    ) -> None:
        """
        Append a follow-up record to an existing per-question metrics entry.

        Args:
            question_number: 1-based index of the parent question.
            followup_number: 1-based index of this follow-up for the parent question.
            followup_text: Full text of the follow-up question.
            followup_type: Type of follow-up (clarification / depth_probe / error_recovery).
            grounding_score: Grounding score for this follow-up (0.0–1.0).
            targeted_aspect: The gap this follow-up addressed.
        """
        raise NotImplementedError

    def compute_summary(self) -> Dict:
        """
        Compute the final interview summary including quality scores and warnings.

        Formulas (design.md §6):
          personalization_quality_score = (
              extraction_confidence_weight * extraction_confidence_numeric
              + question_personalization_rate * 0.8
              + average_question_grounding_confidence * 0.6
          ) / 3

          follow_up_quality_score = mean(all followup grounding scores)

        Warnings are triggered when:
          - personalization_quality_score < 0.60 → "limited_personalization"
          - follow_up_quality_score < 0.60        → "low_follow_up_quality"

        Returns:
            Dict with total_questions, total_followups, average_followup_grounding,
            personalization_quality_score, follow_up_quality_score, warnings.
        """
        raise NotImplementedError

    def to_dict(self) -> Dict:
        """
        Serialise the full metadata structure to a JSON-serialisable dict.

        Returns:
            Dict suitable for storage in the InterviewSession.personalization_metadata
            JSON field.
        """
        raise NotImplementedError

    def _get_extraction_confidence_numeric(self, confidence_level: str) -> float:
        """
        Convert extraction confidence label to a numeric weight for score computation.

        HIGH   → 1.0
        MEDIUM → 0.65
        LOW    → 0.35

        Args:
            confidence_level: "HIGH", "MEDIUM", or "LOW".

        Returns:
            Numeric weight in range 0.0–1.0.
        """
        raise NotImplementedError
