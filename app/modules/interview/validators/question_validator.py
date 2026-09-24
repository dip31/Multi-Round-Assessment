"""
Question Personalization Validator.

Verifies that each generated interview question is grounded in the candidate's
resume content, assigns a confidence score, and requests regeneration when
grounding falls below the acceptance threshold.
"""

from typing import Dict, List, Literal, Optional


class QuestionValidator:
    """
    Validates that interview questions explicitly reference candidate resume content.

    Each question is assessed for grounding confidence (0.0–1.0). Questions that
    score below the acceptance threshold (0.75) are flagged for regeneration. After
    two failed regeneration attempts the question is replaced with a fallback and
    marked with a lower confidence score.
    """

    # Confidence thresholds (as defined in design.md)
    ACCEPT_THRESHOLD: float = 0.75
    FALLBACK_THRESHOLD: float = 0.40
    MAX_REGENERATION_ATTEMPTS: int = 2

    def validate_question(
        self,
        question_id: int,
        question_text: str,
        candidate_skills: List[str],
        candidate_projects: List[Dict],
        detected_role: str,
        question_source: str = "rag_generated",
        regeneration_attempt: int = 0,
    ) -> Dict:
        """
        Validate a single question against the candidate's resume content.

        Args:
            question_id: Unique identifier for the question.
            question_text: The full text of the interview question.
            candidate_skills: List of skills extracted from the candidate's resume.
            candidate_projects: List of project dicts (name, description) from resume.
            detected_role: Candidate's detected seniority level (JUNIOR/MID/SENIOR).
            question_source: Origin of the question ('rag_generated' or 'fallback').
            regeneration_attempt: How many times this question has already been regenerated.

        Returns:
            Dict containing is_valid, grounding_confidence_score, personalization_source,
            recommendation, and regeneration_attempt.
        """
        raise NotImplementedError

    def validate_question_pool(
        self,
        questions: List[Dict],
        candidate_skills: List[str],
        candidate_projects: List[Dict],
        detected_role: str,
    ) -> Dict:
        """
        Validate an entire pool of questions, returning per-question results and
        an overall pool-level summary.

        A pool is considered acceptable when at least 8 of 10 final questions have
        grounding_confidence_score ≥ 0.75 or are explicitly marked as fallback.

        Args:
            questions: List of question dicts to validate.
            candidate_skills: Extracted resume skills.
            candidate_projects: Extracted resume projects.
            detected_role: Candidate's seniority level.

        Returns:
            Dict with per_question_results and pool_summary (is_acceptable,
            questions_passing_threshold, average_confidence).
        """
        raise NotImplementedError

    def _calculate_grounding_score(
        self,
        question_text: str,
        candidate_skills: List[str],
        candidate_projects: List[Dict],
        detected_role: str,
    ) -> tuple:
        """
        Calculate the grounding confidence score for a question.

        Scoring tiers (design.md §2):
          - Exact skill/project name present → 0.85–1.0
          - Semantic similarity to a skill    → 0.65–0.85
          - Role-based reference only         → 0.40–0.65
          - No resume grounding               → 0.0–0.40

        Args:
            question_text: Text of the question.
            candidate_skills: Extracted skills list.
            candidate_projects: Extracted projects list.
            detected_role: Candidate's seniority level.

        Returns:
            Tuple of (score: float, personalization_source: dict).
        """
        raise NotImplementedError

    def _is_generic_question(self, question_text: str) -> bool:
        """
        Detect whether a question is a generic template with no resume grounding.

        Generic patterns that must always be rejected:
          - "What is X?"
          - "Explain X"
          - "Describe the difference between X and Y"

        Args:
            question_text: Text of the question to inspect.

        Returns:
            True if the question appears generic, False otherwise.
        """
        raise NotImplementedError
