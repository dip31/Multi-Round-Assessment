"""
Domain-Aware Answer Classifier.

Classifies candidate answers with an understanding of domain expertise and
answer completeness. Ensures brief-but-expert answers are not penalised for
brevity when domain markers indicate genuine knowledge.
"""

from typing import Dict, List, Literal, Optional


class DomainAwareAnswerClassifier:
    """
    Classifies candidate answers into quality categories while accounting for
    domain-specific knowledge markers and candidate seniority.

    Quality categories (design.md §3):
      EXCELLENT  – content_score ≥ 0.85: technical depth, project examples, architecture
      COMPLETE   – content_score 0.65–0.84: directly addresses question with specifics
      PARTIAL    – content_score 0.35–0.64: addresses question but lacks depth
      SHORT      – content_score < 0.35: too brief, off-topic, or ambiguous

    Domain-aware rule: an expert candidate providing a brief answer with relevant
    domain markers should be classified COMPLETE, not SHORT.
    """

    # Domain marker lists keyed by question domain
    DOMAIN_MARKERS: Dict[str, List[str]] = {
        "DATABASE": [
            "query optimization", "indexing", "schema design", "replication",
            "transactions", "ACID", "normalization", "partitioning", "sharding",
        ],
        "FRONTEND": [
            "state management", "code splitting", "lazy loading", "virtual DOM",
            "accessibility", "bundle size", "SSR", "hydration", "performance",
        ],
        "BACKEND": [
            "REST", "microservices", "caching", "rate limiting", "middleware",
            "authentication", "authorization", "logging", "monitoring",
        ],
        "DEVOPS": [
            "CI/CD", "containerisation", "orchestration", "IaC", "blue-green",
            "canary", "observability", "rollback", "pipeline",
        ],
        "GENERAL": [],
    }

    # Missing-aspect candidates per domain (design.md §3)
    DOMAIN_MISSING_ASPECTS: Dict[str, List[str]] = {
        "DATABASE": ["testing", "scaling", "optimization", "replication", "transactions", "security"],
        "FRONTEND": ["performance", "testing", "accessibility", "state_management", "error_handling"],
        "BACKEND": ["error_handling", "testing", "monitoring", "deployment", "security"],
        "DEVOPS": ["monitoring", "rollback", "scaling", "security", "cost"],
        "GENERAL": ["examples", "specifics", "context", "results"],
    }

    def classify_answer(
        self,
        answer_id: int,
        answer_text: str,
        original_question: str,
        question_domain: Literal["DATABASE", "FRONTEND", "BACKEND", "DEVOPS", "GENERAL"],
        candidate_skills: List[str],
        prior_classification: Optional[Dict] = None,
    ) -> Dict:
        """
        Classify a candidate's answer and return a rich classification object.

        Args:
            answer_id: Unique identifier for this answer.
            answer_text: Transcribed text of the candidate's answer.
            original_question: The question the candidate was answering.
            question_domain: Domain category of the question.
            candidate_skills: Skills from the candidate's resume (used for seniority context).
            prior_classification: Optional classification from a previous turn (for follow-ups).

        Returns:
            Dict with: quality, intent, content_score, confidence, missing_aspects,
            domain_markers, depth_indicators, fallback_followup_type, reasoning.
        """
        raise NotImplementedError

    def _detect_domain_markers(
        self,
        answer_text: str,
        question_domain: str,
    ) -> List[str]:
        """
        Identify domain-specific keywords present in the answer text.

        Args:
            answer_text: The candidate's answer.
            question_domain: Domain to look up marker list for.

        Returns:
            List of domain markers found in the answer.
        """
        raise NotImplementedError

    def _extract_missing_aspects(
        self,
        answer_text: str,
        question_domain: str,
        domain_markers_found: List[str],
    ) -> List[str]:
        """
        Identify specific aspects that are absent from the candidate's answer.

        Uses the DOMAIN_MISSING_ASPECTS list for the given domain and checks which
        items are not evidenced in the answer.

        Args:
            answer_text: The candidate's answer.
            question_domain: Domain of the question.
            domain_markers_found: Markers already detected in the answer.

        Returns:
            List of specific missing aspects (e.g., ["testing", "deployment"]).
        """
        raise NotImplementedError

    def _apply_domain_awareness(
        self,
        base_score: float,
        domain_markers: List[str],
        candidate_skills: List[str],
        answer_text: str,
    ) -> float:
        """
        Adjust the raw content score upward when domain expertise is evident.

        Expert candidates with brief but domain-marker-rich answers should not
        be penalised for brevity (design.md §3, domain-aware assessment section).

        Args:
            base_score: Initial score based on length/coverage heuristics.
            domain_markers: Domain markers detected in the answer.
            candidate_skills: Resume skills used to infer seniority.
            answer_text: The candidate's answer.

        Returns:
            Adjusted content_score (0.0–1.0).
        """
        raise NotImplementedError

    def _calculate_confidence(
        self,
        content_score: float,
        domain_markers: List[str],
        answer_text: str,
    ) -> float:
        """
        Calculate the classifier's own confidence in its assessment.

        Low confidence (< 0.35) triggers error-recovery follow-up type.
        Medium confidence (0.35–0.75) triggers low-confidence flag.

        Args:
            content_score: Computed content quality score.
            domain_markers: Detected domain markers.
            answer_text: The candidate's answer.

        Returns:
            Confidence score in range 0.0–1.0.
        """
        raise NotImplementedError
