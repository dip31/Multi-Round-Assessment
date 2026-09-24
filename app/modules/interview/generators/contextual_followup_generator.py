"""
Contextual Follow-up Question Generator.

Generates follow-up questions that explicitly reference what a candidate said
and address specific gaps identified in the answer classification. Prevents
repetition by tracking previously addressed missing aspects.
"""

from typing import Dict, List, Literal, Optional


class ContextualFollowupGenerator:
    """
    Generates contextually grounded follow-up questions for interview turns.

    Each follow-up must:
      1. Reference word(s) from the candidate's answer OR a specific missing_aspect.
      2. Address a different missing_aspect than any prior follow-up for the same question.
      3. Never produce generic phrasing ("Could you elaborate?", "Tell me more").

    Limits: maximum 2 follow-ups per original question (design.md §4).
    """

    MAX_FOLLOWUPS_PER_QUESTION: int = 2
    GROUNDING_ACCEPT_THRESHOLD: float = 0.75
    MAX_REGENERATION_ATTEMPTS: int = 1

    # Forbidden generic phrases that must never appear in a follow-up
    FORBIDDEN_PHRASES: List[str] = [
        "could you elaborate",
        "tell me more",
        "can you explain further",
        "please elaborate",
        "expand on that",
    ]

    def generate_followup(
        self,
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
        Generate a contextual follow-up question for a given interview turn.

        Returns None when no further follow-up is appropriate (e.g., all aspects
        addressed or maximum follow-up limit reached).

        Args:
            followup_id: Unique identifier for this follow-up.
            followup_count: 0-based index of this follow-up for the current question.
            original_question: The original interview question being followed up.
            candidate_answer: Transcribed text of the candidate's answer.
            answer_classification: Dict from DomainAwareAnswerClassifier containing
                quality, missing_aspects, domain_markers, content_score.
            candidate_skills: Skills from the candidate's resume.
            candidate_projects: Projects from the candidate's resume.
            prior_followups: Text of follow-up questions already asked for this question.
            prior_missing_aspects_addressed: Gaps already explored for this question.

        Returns:
            Dict with followup_question, followup_type, grounding_score,
            grounding_evidence, targeted_missing_aspect, validation_status,
            includes_answer_reference, includes_gap_reference — or None.
        """
        raise NotImplementedError

    def _determine_followup_type(
        self,
        quality: str,
        confidence: float,
        missing_aspects: List[str],
    ) -> Literal["clarification", "depth_probe", "error_recovery"]:
        """
        Select the follow-up type based on answer quality and classifier confidence.

        Rules (design.md §4 Generation Algorithm Step 1):
          - quality == SHORT AND confidence < 0.35 → error_recovery
          - quality == SHORT                        → clarification
          - missing_aspects not empty               → depth_probe

        Args:
            quality: Answer quality category (SHORT / PARTIAL / COMPLETE / EXCELLENT).
            confidence: Classifier confidence in the quality assessment.
            missing_aspects: Specific gaps identified in the answer.

        Returns:
            Follow-up type literal.
        """
        raise NotImplementedError

    def _select_target_aspect(
        self,
        missing_aspects: List[str],
        followup_count: int,
        prior_missing_aspects_addressed: List[str],
    ) -> Optional[str]:
        """
        Choose which missing aspect this follow-up should address.

        First follow-up uses missing_aspects[0]; second follow-up uses a different
        aspect not yet addressed. Returns None when all aspects are covered.

        Args:
            missing_aspects: Gaps from the answer classification.
            followup_count: 0-based index of the current follow-up.
            prior_missing_aspects_addressed: Aspects explored in previous follow-ups.

        Returns:
            The aspect to target, or None if no new aspects remain.
        """
        raise NotImplementedError

    def _calculate_grounding_score(
        self,
        followup_text: str,
        candidate_answer: str,
        targeted_aspect: Optional[str],
    ) -> float:
        """
        Score how contextually grounded a follow-up question is.

        Scoring components (design.md §4 Step 4):
          +0.5  – follow-up contains word(s) from candidate_answer
          +0.3  – follow-up references targeted_missing_aspect
          +0.2  – follow-up uses domain-appropriate language

        Args:
            followup_text: The proposed follow-up question.
            candidate_answer: Original candidate answer for reference matching.
            targeted_aspect: The gap this follow-up is meant to address.

        Returns:
            Grounding score in range 0.0–1.0.
        """
        raise NotImplementedError

    def _is_generic(self, followup_text: str) -> bool:
        """
        Detect whether a follow-up question contains forbidden generic phrasing.

        Args:
            followup_text: Text of the proposed follow-up.

        Returns:
            True if the follow-up is considered generic, False otherwise.
        """
        raise NotImplementedError

    def _build_template_fallback(
        self,
        followup_type: str,
        candidate_answer: str,
        targeted_aspect: Optional[str],
        original_question: str,
    ) -> str:
        """
        Construct a minimal-but-contextual fallback follow-up from templates.

        Used when LLM generation fails or produces a generic question.

        Templates:
          clarification  : "[excerpt]. Which [aspect] specifically?"
          depth_probe    : "You mentioned [excerpt]. How did you approach [aspect]?"
          error_recovery : "Let me rephrase: [original_question]. Can you give more detail?"

        Args:
            followup_type: Type of follow-up to generate.
            candidate_answer: Candidate's answer (for excerpt extraction).
            targeted_aspect: Gap to reference in depth_probe/clarification templates.
            original_question: Used in error_recovery template.

        Returns:
            Contextual (non-generic) follow-up question string.
        """
        raise NotImplementedError
