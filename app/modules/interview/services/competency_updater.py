"""
Competency Profile Update Service for EDI5.

Updates student competency profiles based on interview question analysis evidence.
Maintains history, confidence, and freshness tracking.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from sqlalchemy.orm import Session

from app.models.interview import (
    InterviewSession,
    InterviewQuestionAnalysis,
    StudentCompetency,
    CompetencyEvidence,
)
from app.models.assessment import AssessmentSession
from app.models.user import User

logger = logging.getLogger(__name__)


@dataclass
class CompetencyUpdate:
    """Result of a competency update."""
    skill: str
    previous_score: float
    new_score: float
    previous_confidence: float
    new_confidence: float
    evidence_recorded: bool


@dataclass
class SkillEvidence:
    """Aggregated evidence for a skill from interview analysis."""
    skill: str
    demonstrated_concepts: List[str]
    missing_concepts: List[str]
    question_scores: List[float]  # 0-10 scores
    question_confidences: List[float]
    question_count: int
    avg_depth_score: float  # 0-1 based on depth levels


class CompetencyUpdater:
    """Updates student competency profiles from interview evidence."""
    
    # Depth level to numeric mapping
    DEPTH_SCORES = {
        "Surface": 0.1,
        "Basic": 0.3,
        "Good": 0.55,
        "Strong": 0.8,
        "Expert": 1.0,
    }
    
    # Freshness thresholds (days)
    FRESHNESS_HIGH_DAYS = 30
    FRESHNESS_MEDIUM_DAYS = 90
    
    def __init__(self, db: Session):
        self.db = db
    
    def update_from_interview(
        self,
        interview_id: int,
        question_analyses: List[InterviewQuestionAnalysis],
        skill_mapping: Dict[str, List[str]],  # skill -> list of concepts
    ) -> List[CompetencyUpdate]:
        """
        Update competency profiles based on interview question analyses.
        
        Args:
            interview_id: InterviewSession ID
            question_analyses: List of InterviewQuestionAnalysis records
            skill_mapping: Mapping from skill name to list of related concepts
            
        Returns:
            List of CompetencyUpdate results
        """
        # Aggregate evidence per skill
        skill_evidence = self._aggregate_skill_evidence(
            question_analyses, skill_mapping
        )
        
        if not skill_evidence:
            logger.info(f"No skill evidence found for interview {interview_id}")
            return []
        
        # Get interview for metadata
        interview = self.db.query(InterviewSession).filter(
            InterviewSession.id == interview_id
        ).first()
        
        if not interview:
            logger.error(f"Interview {interview_id} not found")
            return []
        
        # F-0 fix: Resolve the REAL user_id via AssessmentSession.
        # interview.session_id is the AssessmentSession PK, NOT the user PK.
        assessment = self.db.query(AssessmentSession).filter(
            AssessmentSession.id == interview.session_id
        ).first()
        
        if not assessment:
            logger.error(
                f"AssessmentSession {interview.session_id} not found for interview {interview_id}; "
                f"cannot resolve user_id — aborting competency update"
            )
            return []
        
        real_user_id = assessment.user_id
        logger.info(
            f"Competency update: interview={interview_id}, "
            f"assessment_session={interview.session_id}, user_id={real_user_id}"
        )
        
        updates = []
        for skill, evidence in skill_evidence.items():
            update = self._update_skill_competency(
                user_id=real_user_id,
                skill=skill,
                evidence=evidence,
                interview_id=interview_id,
            )
            if update:
                updates.append(update)
        
        self.db.commit()
        return updates
    
    def _aggregate_skill_evidence(
        self,
        analyses: List[InterviewQuestionAnalysis],
        skill_mapping: Dict[str, List[str]],
    ) -> Dict[str, SkillEvidence]:
        """Aggregate question-level evidence into skill-level evidence."""
        
        # Build concept -> skill reverse mapping
        concept_to_skills = {}
        for skill, concepts in skill_mapping.items():
            for concept in concepts:
                concept_lower = concept.lower().strip()
                if concept_lower not in concept_to_skills:
                    concept_to_skills[concept_lower] = []
                concept_to_skills[concept_lower].append(skill)
        
        # Initialize skill evidence containers
        skill_evidence: Dict[str, SkillEvidence] = {}
        
        for analysis in analyses:
            # Get depth score for this question
            depth_score = self.DEPTH_SCORES.get(analysis.depth_level, 0.3)
            
            # Evaluate each concept safely handling None or legacy records
            covered = analysis.covered_concepts or []
            missing = analysis.missing_concepts or []
            incorrect = getattr(analysis, "incorrect_concepts", None) or []
            partial = getattr(analysis, "partial_concepts", None) or []
            all_concepts = set(list(covered) + list(missing) + list(incorrect) + list(partial))
            
            for concept in all_concepts:
                concept_lower = concept.lower().strip()
                related_skills = concept_to_skills.get(concept_lower, [])
                
                # Also try fuzzy matching
                if not related_skills:
                    for skill, skill_concepts in skill_mapping.items():
                        for sc in skill_concepts:
                            if self._concepts_match(concept_lower, sc.lower().strip()):
                                related_skills.append(skill)
                                break
                
                if not related_skills:
                    continue
                
                # Determine status for this concept in this question
                if concept in analysis.covered_concepts:
                    status = "demonstrated"
                elif concept in analysis.missing_concepts:
                    status = "missing"
                elif concept in analysis.incorrect_concepts:
                    status = "incorrect"
                elif concept in analysis.partial_concepts:
                    status = "partial"
                else:
                    status = "missing"
                
                for skill in related_skills:
                    if skill not in skill_evidence:
                        skill_evidence[skill] = SkillEvidence(
                            skill=skill,
                            demonstrated_concepts=[],
                            missing_concepts=[],
                            question_scores=[],
                            question_confidences=[],
                            question_count=0,
                            avg_depth_score=0.0,
                        )
                    
                    se = skill_evidence[skill]
                    
                    if status == "demonstrated" and concept not in se.demonstrated_concepts:
                        se.demonstrated_concepts.append(concept)
                    elif status in ("missing", "incorrect") and concept not in se.missing_concepts:
                        se.missing_concepts.append(concept)
                    
                    se.question_scores.append(analysis.score)
                    se.question_confidences.append(analysis.confidence)
                    se.question_count += 1
                    # Track depth score for averaging
                    se.avg_depth_score = (
                        (se.avg_depth_score * (se.question_count - 1) + depth_score) 
                        / se.question_count
                    )
        
        return skill_evidence
    
    def _concepts_match(self, concept1: str, concept2: str) -> bool:
        """Check if two concepts are semantically similar (simple substring match)."""
        # Simple heuristic: one contains the other, or significant word overlap
        words1 = set(concept1.split())
        words2 = set(concept2.split())
        
        if concept1 in concept2 or concept2 in concept1:
            return True
        
        # Word overlap
        if words1 and words2:
            overlap = len(words1 & words2)
            if overlap / max(len(words1), len(words2)) > 0.6:
                return True
        
        return False
    
    def _update_skill_competency(
        self,
        user_id: int,
        skill: str,
        evidence: SkillEvidence,
        interview_id: int,
    ) -> Optional[CompetencyUpdate]:
        """Update or create competency for a skill based on aggregated evidence."""
        
        # Calculate new score and confidence
        new_score, new_confidence = self._calculate_competency_score(evidence)
        
        # Get or create competency record
        competency = self.db.query(StudentCompetency).filter(
            StudentCompetency.user_id == user_id,
            StudentCompetency.skill == skill,
        ).first()
        
        previous_score = 0.0
        previous_confidence = 0.5
        
        if competency:
            previous_score = competency.score
            previous_confidence = competency.confidence
        else:
            competency = StudentCompetency(
                user_id=user_id,
                skill=skill,
                score=0.0,
                confidence=0.5,
            )
            self.db.add(competency)
            self.db.flush()
        
        # Only update if there's meaningful change
        score_delta = new_score - previous_score
        if abs(score_delta) < 0.5 and abs(new_confidence - previous_confidence) < 0.05:
            logger.debug(f"No significant change for {skill}: {previous_score:.1f}->{new_score:.1f}")
            return None
        
        # Determine freshness (uses existing record's last_verified_at for decay)
        freshness = self._calculate_freshness(
            competency.last_verified_at if competency.id else None
        )
        
        # Update competency
        competency.score = round(new_score, 1)
        competency.confidence = round(new_confidence, 2)
        competency.last_verified_at = datetime.now()
        competency.freshness = freshness
        competency.evidence_source = "interview"
        competency.evidence_id = interview_id
        
        # Idempotency: check if evidence already recorded for this source+skill
        existing_evidence = self.db.query(CompetencyEvidence).filter(
            CompetencyEvidence.user_id == user_id,
            CompetencyEvidence.skill == skill,
            CompetencyEvidence.source == "interview",
            CompetencyEvidence.source_id == interview_id,
        ).first()
        
        evidence_recorded = False
        if not existing_evidence:
            evidence_record = CompetencyEvidence(
                user_id=user_id,
                skill=skill,
                previous_score=previous_score,
                new_score=new_score,
                score_delta=round(score_delta, 1),
                previous_confidence=previous_confidence,
                new_confidence=new_confidence,
                source="interview",
                source_id=interview_id,
                demonstrated_concepts=evidence.demonstrated_concepts,
                missing_concepts=evidence.missing_concepts,
                reasoning=self._generate_reasoning(evidence, score_delta),
            )
            self.db.add(evidence_record)
            evidence_recorded = True
        else:
            logger.debug(
                f"Competency evidence already exists for user={user_id} "
                f"skill={skill} source=interview source_id={interview_id}; skipping"
            )
        
        logger.info(
            f"Updated competency: user={user_id} skill={skill} "
            f"{previous_score:.1f}->{new_score:.1f} "
            f"(confidence: {previous_confidence:.2f}->{new_confidence:.2f})"
        )
        
        return CompetencyUpdate(
            skill=skill,
            previous_score=previous_score,
            new_score=new_score,
            previous_confidence=previous_confidence,
            new_confidence=new_confidence,
            evidence_recorded=evidence_recorded,
        )
    
    def _calculate_competency_score(
        self,
        evidence: SkillEvidence,
    ) -> tuple[float, float]:
        """
        Calculate competency score and confidence from aggregated evidence.
        
        Score methodology:
        - Base score from demonstrated concepts ratio
        - Weighted by question depth and confidence
        - Penalized for missing core concepts
        
        Confidence methodology:
        - Higher with more questions
        - Higher with higher question confidences
        - Higher with more demonstrated concepts
        """
        if evidence.question_count == 0:
            return 0.0, 0.5
        
        total_concepts = len(set(evidence.demonstrated_concepts + evidence.missing_concepts))
        demonstrated_count = len(evidence.demonstrated_concepts)
        
        if total_concepts == 0:
            return 0.0, 0.5
        
        # Base score from concept coverage (0-100)
        coverage_ratio = demonstrated_count / total_concepts
        base_score = coverage_ratio * 100
        
        # Weight by average depth
        depth_weight = evidence.avg_depth_score  # 0.1-1.0
        
        # Weight by average question confidence
        avg_confidence = sum(evidence.question_confidences) / evidence.question_count
        
        # Combined score
        final_score = base_score * depth_weight * avg_confidence
        
        # Clamp
        final_score = max(0.0, min(100.0, final_score))
        
        # Confidence calculation
        # More questions = higher confidence
        question_factor = min(evidence.question_count / 5.0, 1.0)  # saturates at 5 questions
        
        # Higher confidence when answers are clear (high depth)
        clarity_factor = evidence.avg_depth_score
        
        # Higher confidence when coverage is clear (not 50/50)
        coverage_clarity = abs(coverage_ratio - 0.5) * 2  # 0 at 50%, 1 at 0% or 100%
        
        confidence = (0.4 * question_factor + 0.3 * clarity_factor + 0.3 * coverage_clarity)
        confidence = max(0.3, min(0.95, confidence))  # Floor at 0.3, cap at 0.95
        
        return round(final_score, 1), round(confidence, 2)
    
    def _calculate_freshness(self, last_verified_at: Optional[datetime] = None) -> str:
        """Calculate freshness tier based on evidence age.
        
        Tiers:
          - "high":   verified within the last 30 days
          - "medium": verified 30–90 days ago
          - "low":    verified more than 90 days ago
        
        If last_verified_at is None (brand-new record), returns "high".
        """
        if last_verified_at is None:
            return "high"
        
        days_old = (datetime.now() - last_verified_at).days
        if days_old <= 30:
            return "high"
        elif days_old <= 90:
            return "medium"
        else:
            return "low"
    
    def _generate_reasoning(self, evidence: SkillEvidence, score_delta: float) -> str:
        """Generate human-readable reasoning for the update."""
        parts = []
        
        if score_delta > 0:
            parts.append(f"Score increased by {score_delta:.1f} points")
        elif score_delta < 0:
            parts.append(f"Score decreased by {abs(score_delta):.1f} points")
        else:
            parts.append("Score unchanged")
        
        if evidence.demonstrated_concepts:
            parts.append(f"Demonstrated: {', '.join(evidence.demonstrated_concepts[:3])}")
        
        if evidence.missing_concepts:
            parts.append(f"Missing: {', '.join(evidence.missing_concepts[:3])}")
        
        parts.append(f"Based on {evidence.question_count} question(s)")
        
        return "; ".join(parts)
    
    def get_competency_profile(self, user_id: int) -> List[Dict[str, Any]]:
        """Get full competency profile for a user."""
        competencies = self.db.query(StudentCompetency).filter(
            StudentCompetency.user_id == user_id
        ).all()
        
        profile = []
        for c in competencies:
            # Calculate days since last verified
            days_old = (datetime.now() - c.last_verified_at).days
            
            profile.append({
                "skill": c.skill,
                "score": c.score,
                "confidence": c.confidence,
                "freshness": c.freshness,
                "days_since_verified": days_old,
                "evidence_source": c.evidence_source,
                "evidence_id": c.evidence_id,
                "last_updated": c.updated_at.isoformat() if c.updated_at else None,
            })
        
        return profile
    
    def get_competency_history(self, user_id: int, skill: str) -> List[Dict[str, Any]]:
        """Get historical evidence for a skill."""
        evidence_records = self.db.query(CompetencyEvidence).filter(
            CompetencyEvidence.user_id == user_id,
            CompetencyEvidence.skill == skill,
        ).order_by(CompetencyEvidence.created_at.desc()).all()
        
        history = []
        for e in evidence_records:
            history.append({
                "timestamp": e.created_at.isoformat(),
                "previous_score": e.previous_score,
                "new_score": e.new_score,
                "score_delta": e.score_delta,
                "previous_confidence": e.previous_confidence,
                "new_confidence": e.new_confidence,
                "source": e.source,
                "source_id": e.source_id,
                "demonstrated_concepts": e.demonstrated_concepts,
                "missing_concepts": e.missing_concepts,
                "reasoning": e.reasoning,
            })
        
        return history


def get_competency_updater(db: Session) -> CompetencyUpdater:
    """Factory for dependency injection."""
    return CompetencyUpdater(db)