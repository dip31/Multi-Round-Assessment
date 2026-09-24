"""
Personalization Service.

Top-level orchestrator for interview question personalization and contextual
follow-up generation. Coordinates the validation, generation, classification,
and metadata-tracking sub-components introduced by this feature.
"""

from typing import Any, Callable, Dict, List, Literal, Optional

from app.modules.interview.generators.contextual_followup_generator import (
    ContextualFollowupGenerator,
)
from app.modules.interview.utils.metadata_tracker import InterviewMetadataTracker
from app.modules.interview.validators.answer_classifier import (
    DomainAwareAnswerClassifier,
)
from app.modules.interview.validators.question_validator import QuestionValidator
from app.modules.interview.validators.resume_extraction_validator import (
    ResumeExtractionValidator,
    build_extraction_metadata,
)
from app.modules.interview.schemas.personalization_schemas import ResumeExtractionResult


class PersonalizationService:
    """
    Orchestrates the full personalization pipeline for a single interview session.

    Responsibilities:
      1. Validate question pools – ensure all questions reference resume content.
      2. Classify candidate answers – with domain-aware quality assessment.
      3. Generate contextual follow-ups – referencing answers and identified gaps.
      4. Track and persist metadata – across all turns of the interview.

    All sub-components are injected via the constructor to facilitate testing.
    """

    def __init__(
        self,
        question_validator: Optional[QuestionValidator] = None,
        answer_classifier: Optional[DomainAwareAnswerClassifier] = None,
        followup_generator: Optional[ContextualFollowupGenerator] = None,
        extraction_validator: Optional[ResumeExtractionValidator] = None,
    ) -> None:
        """
        Initialise the service with optional injected sub-components.

        Default (no-argument) construction creates instances using default settings.

        Args:
            question_validator: Validates question pool grounding. Uses default if None.
            answer_classifier: Classifies candidate answers. Uses default if None.
            followup_generator: Generates contextual follow-ups. Uses default if None.
            extraction_validator: Validates resume extraction quality. Uses default if None.
        """
        self.question_validator = question_validator or QuestionValidator()
        self.answer_classifier = answer_classifier or DomainAwareAnswerClassifier()
        self.followup_generator = followup_generator or ContextualFollowupGenerator()
        self.extraction_validator = extraction_validator or ResumeExtractionValidator()
        self._metadata_trackers: Dict[int, InterviewMetadataTracker] = {}

    def validate_resume_extraction(
        self,
        interview_id: int,
        extracted_skills: List[str],
        extracted_projects: List[Dict],
        detected_role: Literal["JUNIOR", "MID", "SENIOR"],
        experience_years: Optional[int] = None,
        extraction_method: str = "pymudf+groq",
        re_extractor: Optional[Callable] = None,
        db_session: Optional[Any] = None,
    ) -> ResumeExtractionResult:
        """
        Validate resume extraction quality and optionally persist results to the
        InterviewSession row.

        If *db_session* is provided the method will update the corresponding
        InterviewSession with ``extraction_confidence`` and
        ``personalization_metadata`` (extraction sub-section).

        Args:
            interview_id: Database ID of the interview session.
            extracted_skills: Skills extracted by the primary parser.
            extracted_projects: Projects extracted by the primary parser.
            detected_role: Candidate seniority level (JUNIOR / MID / SENIOR).
            experience_years: Optional total experience years for role alignment check.
            extraction_method: Label for the extraction method used (for logging).
            re_extractor: Optional callable for alternative extraction when skills < 3.
            db_session: Optional SQLAlchemy session. When supplied the
                        InterviewSession row is updated in-place (requires commit
                        by the caller).

        Returns:
            ResumeExtractionResult with confidence level and recommendation.
        """
        result = self.extraction_validator.validate(
            interview_id=interview_id,
            extracted_skills=extracted_skills,
            extracted_projects=extracted_projects,
            detected_role=detected_role,
            experience_years=experience_years,
            extraction_method=extraction_method,
            re_extractor=re_extractor,
        )

        # ── Requirement 1.8: persist extraction result to InterviewSession ────
        if db_session is not None:
            self._persist_extraction_result(db_session, interview_id, result)

        return result

    @staticmethod
    def _persist_extraction_result(
        db_session: Any,
        interview_id: int,
        result: ResumeExtractionResult,
    ) -> None:
        """
        Persist extraction result fields onto the InterviewSession row.

        The caller is responsible for committing the session.

        Args:
            db_session: Active SQLAlchemy session.
            interview_id: Primary key of the InterviewSession to update.
            result: Validated extraction result.
        """
        import logging as _logging
        _log = _logging.getLogger(__name__)

        try:
            from app.models.interview import InterviewSession

            session_row = db_session.get(InterviewSession, interview_id)
            if session_row is None:
                _log.warning(
                    "[PersonalizationService] interview_id=%d not found – "
                    "skipping extraction result persistence", interview_id
                )
                return

            session_row.extraction_confidence = result.extraction_confidence

            # Merge into existing personalization_metadata if present
            existing_meta: Dict = session_row.personalization_metadata or {}
            existing_meta["extraction_metadata"] = build_extraction_metadata(
                result, interview_id
            )
            session_row.personalization_metadata = existing_meta

            # Propagate warnings list
            warnings: List[str] = list(session_row.personalization_warnings or [])
            if result.extraction_confidence == "LOW" and "limited_personalization" not in warnings:
                warnings.append("limited_personalization")
            session_row.personalization_warnings = warnings or None

        except Exception as exc:
            _log.error(
                "[PersonalizationService] Failed to persist extraction result for "
                "interview_id=%d: %s", interview_id, exc
            )
            # Non-blocking: interview continues regardless of metadata save failure

    def validate_question_pool(
        self,
        interview_id: int,
        questions: List[Dict],
        candidate_skills: List[str],
        candidate_projects: List[Dict],
        detected_role: str,
    ) -> Dict:
        """
        Validate an entire question pool and return per-question results.

        A pool is acceptable when ≥8 of 10 questions have grounding_confidence_score
        ≥ 0.75 or are explicitly marked as fallback.

        Args:
            interview_id: Database ID of the interview session.
            questions: Questions to validate (list of dicts with at minimum question_text).
            candidate_skills: Skills extracted from the candidate's resume.
            candidate_projects: Projects extracted from the candidate's resume.
            detected_role: Candidate's seniority level (JUNIOR / MID / SENIOR).

        Returns:
            Dict with per_question_results and pool_summary.
        """
        raise NotImplementedError

    def classify_answer(
        self,
        interview_id: int,
        answer_id: int,
        answer_text: str,
        original_question: str,
        question_domain: str,
        candidate_skills: List[str],
        prior_classification: Optional[Dict] = None,
    ) -> Dict:
        """
        Classify a candidate's answer and store the result in session metadata.

        Args:
            interview_id: Database ID of the interview session.
            answer_id: Unique identifier for this answer.
            answer_text: Transcribed text of the candidate's answer.
            original_question: The question the candidate was answering.
            question_domain: Domain category of the question (DATABASE / FRONTEND / …).
            candidate_skills: Skills from the candidate's resume.
            prior_classification: Optional prior classification (for multi-turn context).

        Returns:
            Full classification dict from DomainAwareAnswerClassifier.
        """
        raise NotImplementedError

    def generate_followup(
        self,
        interview_id: int,
        followup_id: int,
        followup_count: int,
        original_question: str,
        candidate_answer: str,
        answer_classification: Dict,
        candidate_skills: List[str],
        candidate_projects: List[Dict],
        prior_followups: List[str],
        prior_missing_aspects_addressed: List[str],
    ) -> Optional[Dict]:
        """
        Generate a contextual follow-up question for an interview turn.

        Returns None when no follow-up is appropriate (all aspects addressed,
        or hard limit of 2 follow-ups reached).

        Args:
            interview_id: Database ID of the interview session.
            followup_id: Unique identifier for this follow-up.
            followup_count: 0-based count of follow-ups already asked for this question.
            original_question: The original interview question.
            candidate_answer: Transcribed candidate answer.
            answer_classification: Classification dict (quality, missing_aspects, …).
            candidate_skills: Skills from the candidate's resume.
            candidate_projects: Projects from the candidate's resume.
            prior_followups: Previously asked follow-up texts for this question.
            prior_missing_aspects_addressed: Gaps already explored for this question.

        Returns:
            Follow-up dict or None.
        """
        raise NotImplementedError

    def get_or_create_metadata_tracker(
        self, interview_id: int
    ) -> InterviewMetadataTracker:
        """
        Return the metadata tracker for the given interview, creating one if needed.

        Args:
            interview_id: Database ID of the interview session.

        Returns:
            InterviewMetadataTracker instance for the session.
        """
        raise NotImplementedError

    def finalise_interview_metadata(self, interview_id: int) -> Dict:
        """
        Compute and return the final summary metadata for a completed interview.

        Args:
            interview_id: Database ID of the completed interview session.

        Returns:
            Summary dict from InterviewMetadataTracker.compute_summary().
        """
        raise NotImplementedError
