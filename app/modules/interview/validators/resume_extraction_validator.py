"""
Resume Extraction Validator.

Validates that resume parsing extracted sufficient skill and project data before
proceeding with personalized question generation. Confidence levels drive downstream
behaviour: HIGH → full personalization, MEDIUM → partial personalization, LOW → fallback mode.

Design references: Requirements 1.1–1.8, design.md §1 (Resume Extraction Validator).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from app.modules.interview.schemas.personalization_schemas import ResumeExtractionResult

logger = logging.getLogger(__name__)

# ── Thresholds (design.md §1) ─────────────────────────────────────────────────
_SKILLS_HIGH = 5       # ≥5 distinct skills → HIGH
_SKILLS_MEDIUM = 3     # ≥3 skills → MEDIUM  (<3 → LOW, triggers retry)
_PROJECTS_HIGH = 2     # ≥2 projects with description → HIGH
_PROJECTS_MEDIUM = 1   # ≥1 project → MEDIUM

# Seniority level → expected minimum years of experience
_ROLE_SENIORITY_YEARS: Dict[str, int] = {
    "JUNIOR": 0,
    "MID": 2,
    "SENIOR": 5,
}


class ResumeExtractionValidator:
    """
    Validates resume extraction completeness and quality.

    Responsibilities:
      1. Count distinct extracted skills and determine confidence tier.
      2. Count projects with non-empty descriptions.
      3. Validate detected role alignment with experience years (if available).
      4. Trigger retry when skills < 3 and a re-extractor callable is provided.
      5. Return a structured ResumeExtractionResult with recommendation.

    Usage::

        validator = ResumeExtractionValidator()
        result = validator.validate(
            interview_id=42,
            extracted_skills=["Python", "Django", "PostgreSQL"],
            extracted_projects=[{"name": "Shop", "description": "E-commerce app"}],
            detected_role="MID",
        )
        # result.extraction_confidence → "MEDIUM"
        # result.recommendation       → "PROCEED"
    """

    def validate(
        self,
        interview_id: int,
        extracted_skills: List[str],
        extracted_projects: List[Dict[str, Any]],
        detected_role: Literal["JUNIOR", "MID", "SENIOR"],
        experience_years: Optional[int] = None,
        extraction_method: str = "pymudf+groq",
        re_extractor: Optional[Any] = None,
    ) -> ResumeExtractionResult:
        """
        Validate extracted resume data and return a confidence assessment.

        If skills count is below the LOW threshold (< 3) and a *re_extractor*
        callable is provided, it will be invoked once.  The callable must accept
        no arguments and return a dict with keys ``skills`` (List[str]) and
        ``projects`` (List[Dict]).

        Args:
            interview_id: Database ID of the interview session (used for logging).
            extracted_skills: Skills extracted by the primary parser.
            extracted_projects: Projects extracted by the primary parser.
            detected_role: Candidate seniority level detected from resume.
            experience_years: Optional total years of experience (used for role alignment).
            extraction_method: Human-readable label for the extraction method used.
            re_extractor: Optional callable that performs alternative extraction.
                          Signature: ``() -> {"skills": [...], "projects": [...]}``

        Returns:
            ResumeExtractionResult with confidence level and recommendation.
        """
        skills = list(dict.fromkeys(s.strip() for s in extracted_skills if s.strip()))
        projects = [p for p in extracted_projects if p.get("description", "").strip()]

        retry_count = 0
        alternative_attempted = False
        issues: List[str] = []

        # ── Requirement 1.6: retry if skills < 3 ─────────────────────────────
        if len(skills) < _SKILLS_MEDIUM and re_extractor is not None:
            logger.info(
                "[ResumeExtractionValidator] interview_id=%d – skills=%d < %d, "
                "attempting re-extraction via %s",
                interview_id, len(skills), _SKILLS_MEDIUM, extraction_method,
            )
            try:
                alt_result = re_extractor()
                alternative_attempted = True
                retry_count = 1

                alt_skills = list(dict.fromkeys(
                    s.strip() for s in alt_result.get("skills", []) if s.strip()
                ))
                alt_projects = [
                    p for p in alt_result.get("projects", [])
                    if p.get("description", "").strip()
                ]

                # Use re-extraction results only if they improve coverage
                if len(alt_skills) > len(skills):
                    logger.info(
                        "[ResumeExtractionValidator] interview_id=%d – re-extraction "
                        "improved skills: %d → %d",
                        interview_id, len(skills), len(alt_skills),
                    )
                    skills = alt_skills
                if len(alt_projects) > len(projects):
                    projects = alt_projects

            except Exception as exc:
                logger.warning(
                    "[ResumeExtractionValidator] interview_id=%d – re-extraction failed: %s",
                    interview_id, exc,
                )
                issues.append("alternative_extraction_failed")

        # ── Requirement 1.2: assess skill count ──────────────────────────────
        skills_confidence = self._skills_confidence(len(skills))
        if skills_confidence == "LOW":
            issues.append("too_few_skills")
            logger.warning(
                "[ResumeExtractionValidator] interview_id=%d – LOW skills confidence "
                "(count=%d)", interview_id, len(skills),
            )
        elif skills_confidence == "MEDIUM":
            issues.append("below_recommended_skills")

        # ── Requirement 1.3: assess project count ────────────────────────────
        projects_confidence = self._projects_confidence(len(projects))
        if projects_confidence == "LOW":
            issues.append("too_few_projects")
        elif projects_confidence == "MEDIUM":
            issues.append("below_recommended_projects")

        # ── Requirement 1.4: role alignment check ────────────────────────────
        role_aligned = self._validate_role_alignment(detected_role, experience_years)
        if not role_aligned:
            issues.append("role_experience_mismatch")
            logger.info(
                "[ResumeExtractionValidator] interview_id=%d – role/experience mismatch "
                "(role=%s, years=%s)", interview_id, detected_role, experience_years,
            )

        # ── Overall confidence (most conservative of skills / projects) ───────
        overall_confidence = self._combine_confidence(skills_confidence, projects_confidence)

        # ── Recommendation ────────────────────────────────────────────────────
        recommendation = self._determine_recommendation(
            overall_confidence, alternative_attempted, skills
        )

        result = ResumeExtractionResult(
            is_valid=overall_confidence != "LOW",
            extraction_confidence=overall_confidence,
            skills_count=len(skills),
            projects_count=len(projects),
            issues=issues,
            recommendation=recommendation,
            retry_count=retry_count,
            alternative_extraction_attempted=alternative_attempted,
        )

        # ── Requirement 1.5 / 1.8: log result ────────────────────────────────
        logger.info(
            "[ResumeExtractionValidator] interview_id=%d – result: "
            "confidence=%s recommendation=%s skills=%d projects=%d issues=%s",
            interview_id,
            result.extraction_confidence,
            result.recommendation,
            result.skills_count,
            result.projects_count,
            result.issues,
        )

        return result

    # ── Internal helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _skills_confidence(
        count: int,
    ) -> Literal["HIGH", "MEDIUM", "LOW"]:
        """Map skill count to confidence tier (Requirement 1.2)."""
        if count >= _SKILLS_HIGH:
            return "HIGH"
        if count >= _SKILLS_MEDIUM:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _projects_confidence(
        count: int,
    ) -> Literal["HIGH", "MEDIUM", "LOW"]:
        """Map project-with-description count to confidence tier (Requirement 1.3)."""
        if count >= _PROJECTS_HIGH:
            return "HIGH"
        if count >= _PROJECTS_MEDIUM:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _combine_confidence(
        skills_conf: Literal["HIGH", "MEDIUM", "LOW"],
        projects_conf: Literal["HIGH", "MEDIUM", "LOW"],
    ) -> Literal["HIGH", "MEDIUM", "LOW"]:
        """
        Return the most conservative confidence level.

        HIGH  only when both are HIGH.
        LOW   when either is LOW.
        MEDIUM otherwise.
        """
        order = {"HIGH": 2, "MEDIUM": 1, "LOW": 0}
        worst = min(order[skills_conf], order[projects_conf])
        return ["LOW", "MEDIUM", "HIGH"][worst]

    @staticmethod
    def _validate_role_alignment(
        detected_role: str,
        experience_years: Optional[int],
    ) -> bool:
        """
        Check that declared experience years are consistent with detected role (Requirement 1.4).

        Returns True when experience_years is None (not provided) or when the
        years are at or above the minimum expected for the role tier.
        """
        if experience_years is None:
            return True  # Cannot validate without data → assume aligned
        role_upper = detected_role.upper()
        min_years = _ROLE_SENIORITY_YEARS.get(role_upper, 0)
        return experience_years >= min_years

    @staticmethod
    def _determine_recommendation(
        confidence: Literal["HIGH", "MEDIUM", "LOW"],
        alternative_attempted: bool,
        skills: List[str],
    ) -> Literal["PROCEED", "RETRY", "FALLBACK_MODE"]:
        """
        Determine the downstream recommendation.

        - HIGH  → PROCEED unconditionally.
        - MEDIUM → PROCEED (enough data for partial personalization).
        - LOW + alternative not yet tried → RETRY.
        - LOW + alternative already tried (or no re_extractor) → FALLBACK_MODE.
        """
        if confidence == "HIGH":
            return "PROCEED"
        if confidence == "MEDIUM":
            return "PROCEED"
        # LOW confidence
        if not alternative_attempted:
            return "RETRY"
        return "FALLBACK_MODE"


def build_extraction_metadata(
    result: ResumeExtractionResult,
    interview_id: int,
) -> Dict[str, Any]:
    """
    Build the ``extraction_metadata`` dict stored in InterviewSession.personalization_metadata.

    Args:
        result: Validated extraction result.
        interview_id: Interview session ID.

    Returns:
        Dict suitable for JSON serialization.
    """
    return {
        "interview_id": interview_id,
        "extraction_confidence": result.extraction_confidence,
        "skills_count": result.skills_count,
        "projects_count": result.projects_count,
        "issues": result.issues,
        "recommendation": result.recommendation,
        "alternative_extraction_attempted": result.alternative_extraction_attempted,
        "retry_count": result.retry_count,
        "is_valid": result.is_valid,
        "validated_at": datetime.utcnow().isoformat(),
    }
