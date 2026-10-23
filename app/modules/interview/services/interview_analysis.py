"""
Post-Interview Analysis Service for EDI5.

Analyzes completed interview conversations and generates question-wise
evaluation with expected concepts, covered points, missing points, and scores.
Integrates with AnswerAnalyzer for semantic evaluation and CompetencyUpdater
for profile updates.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.interview import (
    InterviewSession,
    InterviewTurn,
    InterviewConversation,
    InterviewMessage,
    InterviewMessageSpeaker,
    InterviewMessageType,
    InterviewQuestionAnalysis,
    ApprovedQuestionPool,
)
from app.modules.interview.services.answer_analyzer import (
    AnswerAnalyzer, AnswerAnalysis, ConceptEvaluation, get_answer_analyzer
)
from app.modules.interview.services.competency_updater import (
    CompetencyUpdater, get_competency_updater
)
from app.services.groq_service import GroqService, _safe_json as groq_safe_json, GROQ_MODEL
from app.config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class QuestionAnalysis:
    """Analysis result for a single question."""
    question_id: str
    question_number: int
    question_text: str
    question_type: str  # QUESTION, FOLLOW_UP
    candidate_answer: str
    expected_concepts: List[str]
    covered_concepts: List[str]
    missing_concepts: List[str]
    incorrect_concepts: List[str]
    partial_concepts: List[str]
    concept_evaluations: List[ConceptEvaluation]
    strengths: List[str]
    gaps: List[str]
    score: float  # 0-10
    max_score: float = 10.0
    confidence: float = 0.8
    depth_level: str = "Basic"  # Surface, Basic, Good, Strong, Expert
    interview_turn_id: Optional[int] = None
    pool_question_id: Optional[str] = None


@dataclass
class InterviewAnalysis:
    """Complete interview analysis result."""
    interview_id: int
    overall_score: float
    question_analyses: List[QuestionAnalysis]
    strong_areas: List[str]
    improvement_areas: List[str]
    recurring_gaps: List[str]
    pattern_summary: str
    confidence: float
    competency_changes: List[Dict[str, Any]] = field(default_factory=list)


class InterviewAnalysisService:
    """Service for post-interview question-wise analysis."""
    
    def __init__(
        self,
        groq_service: Optional[GroqService] = None,
        answer_analyzer: Optional[AnswerAnalyzer] = None,
        competency_updater: Optional[CompetencyUpdater] = None,
    ):
        self.groq = groq_service or GroqService(settings.GROQ_API_KEY)
        self.answer_analyzer = answer_analyzer or get_answer_analyzer()
        self.competency_updater = competency_updater
    
    def analyze_interview(
        self,
        db: Session,
        interview_id: int,
        persist: bool = True,
        update_competency: bool = True,
    ) -> InterviewAnalysis:
        """
        Analyze a completed interview and generate question-wise evaluation.
        
        Args:
            db: Database session
            interview_id: InterviewSession ID
            persist: Whether to persist results to database
            update_competency: Whether to update competency profiles
            
        Returns:
            InterviewAnalysis with structured results
        """
        interview = db.query(InterviewSession).filter(
            InterviewSession.id == interview_id
        ).first()
        
        if not interview:
            raise ValueError(f"Interview {interview_id} not found")
        
        # Get structured conversation
        conversation = db.query(InterviewConversation).filter(
            InterviewConversation.interview_id == interview_id
        ).first()
        
        if not conversation or not conversation.messages:
            logger.warning(f"No structured conversation for interview {interview_id}, falling back to turns")
            return self._analyze_from_turns(db, interview, persist, update_competency)
        
        # Get question pool for expected concepts
        pool = db.query(ApprovedQuestionPool).filter(
            ApprovedQuestionPool.session_id == interview.session_id,
            ApprovedQuestionPool.admin_approved == True,
        ).first()
        
        # Build concept -> skill mapping from pool
        skill_mapping = self._build_skill_mapping(pool)
        
        # Group messages into question-answer pairs using turn_id for accuracy
        qa_pairs = self._group_into_qa_pairs(conversation.messages)
        
        # Analyze each question
        question_analyses = []
        for idx, (question_msg, answer_msgs, turn_id, pool_qid) in enumerate(qa_pairs):
            analysis = self._analyze_question(
                db=db,
                question_number=idx + 1,
                question_msg=question_msg,
                answer_msgs=answer_msgs,
                interview_type=interview.phase.lower() if interview.phase else "technical",
                turn_id=turn_id,
                pool_question_id=pool_qid,
            )
            question_analyses.append(analysis)
            
            # Persist individual question analysis
            if persist and analysis.interview_turn_id:
                self._persist_question_analysis(db, interview_id, analysis)
        
        # Generate overall summary
        overall_score = self._calculate_overall_score(question_analyses)
        strong_areas, improvement_areas = self._identify_strengths_weaknesses(question_analyses)
        recurring_gaps = self._identify_recurring_gaps(question_analyses)
        pattern_summary = self._generate_pattern_summary(question_analyses, strong_areas, improvement_areas)
        confidence = self._calculate_confidence(question_analyses)
        
        # Update competency profiles
        competency_changes = []
        if update_competency and self.competency_updater:
            try:
                competency_updates = self.competency_updater.update_from_interview(
                    interview_id=interview_id,
                    question_analyses=[
                        self._qa_to_dict(qa) for qa in question_analyses
                    ],
                    skill_mapping=skill_mapping,
                )
                competency_changes = [
                    {
                        "skill": u.skill,
                        "previous_score": u.previous_score,
                        "new_score": u.new_score,
                        "previous_confidence": u.previous_confidence,
                        "new_confidence": u.new_confidence,
                    }
                    for u in competency_updates
                ]
            except Exception as e:
                logger.error(f"Failed to update competency for interview {interview_id}: {e}")
        
        result = InterviewAnalysis(
            interview_id=interview_id,
            overall_score=overall_score,
            question_analyses=question_analyses,
            strong_areas=strong_areas,
            improvement_areas=improvement_areas,
            recurring_gaps=recurring_gaps,
            pattern_summary=pattern_summary,
            confidence=confidence,
            competency_changes=competency_changes,
        )
        
        return result
    
    def _qa_to_dict(self, qa: QuestionAnalysis) -> Dict[str, Any]:
        """Convert QuestionAnalysis to dict for competency updater."""
        return {
            "covered_concepts": qa.covered_concepts,
            "missing_concepts": qa.missing_concepts,
            "incorrect_concepts": qa.incorrect_concepts,
            "partial_concepts": qa.partial_concepts,
            "score": qa.score,
            "confidence": qa.confidence,
            "depth_level": qa.depth_level,
        }
    
    def _build_skill_mapping(self, pool: Optional[ApprovedQuestionPool]) -> Dict[str, List[str]]:
        """Build skill -> concepts mapping from question pool."""
        skill_mapping = {}
        
        if pool and pool.question_pool:
            for q in pool.question_pool:
                grounded = q.get("grounded_in", "")
                if grounded:
                    # Use grounded_in as skill indicator
                    skill = grounded.replace("_", " ").title()
                    if skill not in skill_mapping:
                        skill_mapping[skill] = []
                    # Add expected concepts if available
                    if q.get("expected_concepts"):
                        for c in q["expected_concepts"]:
                            if c not in skill_mapping[skill]:
                                skill_mapping[skill].append(c)
                    # Add topic
                    if q.get("topic"):
                        if q["topic"] not in skill_mapping[skill]:
                            skill_mapping[skill].append(q["topic"])
        
        # Default fallback skills if none found
        if not skill_mapping:
            skill_mapping = {
                "Technical Knowledge": ["Core concepts", "Implementation", "Best practices"],
                "Problem Solving": ["Approach", "Trade-offs", "Edge cases"],
                "Communication": ["Clarity", "Structure", "Articulation"],
            }
        
        return skill_mapping
    
    def _group_into_qa_pairs(self, messages: List[InterviewMessage]) -> List[tuple]:
        """
        Group messages into question-answer pairs using turn_id for accuracy.
        
        Returns list of (question_message, [answer_messages], turn_id, pool_question_id) tuples.
        """
        qa_pairs = []
        current_question = None
        current_answers = []
        current_turn_id = None
        current_pool_qid = None
        
        for msg in messages:
            if msg.speaker == InterviewMessageSpeaker.AI.value:
                # Save previous pair
                if current_question:
                    qa_pairs.append((
                        current_question, current_answers, current_turn_id, current_pool_qid
                    ))
                
                # Start new pair
                current_question = msg
                current_answers = []
                current_turn_id = msg.turn_id
                # Try to get pool question ID from message metadata or turn
                current_pool_qid = None
            elif msg.speaker == InterviewMessageSpeaker.CANDIDATE.value:
                if current_question:
                    current_answers.append(msg)
                else:
                    # Answer without preceding question - create synthetic question
                    current_question = None
                    current_answers.append(msg)
        
        # Don't forget the last pair
        if current_question:
            qa_pairs.append((current_question, current_answers, current_turn_id, current_pool_qid))
        
        return qa_pairs
    
    def _analyze_question(
        self,
        db: Session,
        question_number: int,
        question_msg: Optional[InterviewMessage],
        answer_msgs: List[InterviewMessage],
        interview_type: str,
        turn_id: Optional[int] = None,
        pool_question_id: Optional[str] = None,
    ) -> QuestionAnalysis:
        """Analyze a single question-answer exchange using AnswerAnalyzer."""
        
        question_text = question_msg.text if question_msg else "Unknown question"
        question_type = question_msg.message_type if question_msg else "QUESTION"
        candidate_answer = " ".join([m.text for m in answer_msgs]) if answer_msgs else "No answer provided"
        
        # F-2 fix: Get expected concepts from pool question if available
        expected_concepts = []
        if pool_question_id:
            expected_concepts = self._get_pool_expected_concepts(db, pool_question_id, question_text)
        
        # If no pool concepts, generate on-the-fly (fallback)
        if not expected_concepts:
            expected_concepts = self._generate_expected_concepts(question_text, interview_type)
        
        # Use AnswerAnalyzer for semantic evaluation
        analysis_result = self.answer_analyzer.analyze_answer(
            question=question_text,
            answer=candidate_answer,
            expected_concepts=expected_concepts,
            interview_type=interview_type,
        )
        
        return QuestionAnalysis(
            question_id=question_msg.id if question_msg else f"q{question_number}",
            question_number=question_number,
            question_text=question_text,
            question_type=question_type,
            candidate_answer=candidate_answer,
            expected_concepts=expected_concepts,
            covered_concepts=analysis_result.covered_concepts,
            missing_concepts=analysis_result.missing_concepts,
            incorrect_concepts=analysis_result.incorrect_concepts,
            partial_concepts=analysis_result.partial_concepts,
            concept_evaluations=analysis_result.concept_evaluations,
            strengths=analysis_result.strengths,
            gaps=analysis_result.gaps,
            score=analysis_result.score,
            confidence=analysis_result.confidence,
            depth_level=analysis_result.depth_level,
            interview_turn_id=turn_id,
            pool_question_id=pool_question_id,
        )
    
    def _get_pool_expected_concepts(
        self, db: Session, pool_question_id: str, question_text: str
    ) -> List[str]:
        """F-2 fix: Retrieve expected concepts from the approved question pool.
        
        Pool questions may have an 'expected_concepts' field in their JSONB data.
        Falls back to topic-based heuristics if not available.
        """
        try:
            # Find pool records that contain this question_id
            pools = db.query(ApprovedQuestionPool).all()
            for pool in pools:
                for q in (pool.question_pool or []):
                    if q.get("id") == pool_question_id:
                        # Check for explicit expected_concepts
                        concepts = q.get("expected_concepts", [])
                        if concepts and isinstance(concepts, list):
                            logger.debug(
                                f"Found {len(concepts)} pool concepts for question {pool_question_id}"
                            )
                            return [str(c) for c in concepts]
                        # No explicit concepts — return empty to trigger fallback
                        return []
        except Exception as e:
            logger.warning(f"Failed to look up pool concepts for {pool_question_id}: {e}")
        return []
    
    def _generate_expected_concepts(self, question: str, interview_type: str) -> List[str]:
        """Generate expected concepts for a question using LLM (fallback).
        
        F-1 fix: Uses self.groq.client.chat.completions.create() — the correct
        Groq SDK interface — instead of the non-existent self.groq.chat_completion().
        """
        prompt = f"""You are an expert interviewer evaluating candidate responses for a {interview_type} interview.

Question: "{question}"

Generate a list of 5-8 key concepts/points that a strong candidate should cover in their answer.
These should be specific, measurable concepts - not vague topics.

Return ONLY a JSON array of strings, e.g.:
["dependency injection concept", "FastAPI Depends usage", "database session management", "separation of concerns", "testing benefits"]

Focus on:
- Technical accuracy requirements
- Framework-specific implementation details (if applicable)
- Best practices and patterns
- Common pitfalls to avoid"""

        try:
            # F-1 fix: Use the actual Groq SDK interface
            response = self.groq.client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": "You are an expert interviewer. Return only valid JSON arrays."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=500,
            )
            raw = response.choices[0].message.content
            parsed = groq_safe_json(raw)
            if isinstance(parsed, list):
                return [str(c) for c in parsed if isinstance(c, str)]
            elif isinstance(parsed, dict) and "concepts" in parsed:
                return [str(c) for c in parsed["concepts"] if isinstance(c, str)]
        except Exception as e:
            logger.warning(f"Failed to generate expected concepts via LLM: {e}")
        
        # Fallback — clearly marked as generic
        return ["Core concept understanding", "Practical implementation", "Best practices", "Edge cases"]
    
    def _persist_question_analysis(
        self,
        db: Session,
        interview_id: int,
        analysis: QuestionAnalysis,
    ) -> None:
        """Persist question analysis to database."""
        try:
            # Check if already exists (idempotency)
            existing = db.query(InterviewQuestionAnalysis).filter(
                InterviewQuestionAnalysis.interview_id == interview_id,
                InterviewQuestionAnalysis.turn_id == analysis.interview_turn_id,
            ).first()
            
            # F-3 fix: Build evidence dict from concept_evaluations
            evidence_dict = {}
            for ce in (analysis.concept_evaluations or []):
                if ce.evidence:
                    evidence_dict[ce.concept] = ce.evidence
            
            if existing:
                # Update existing
                existing.question_id = analysis.question_id
                existing.question_number = analysis.question_number
                existing.question_text = analysis.question_text
                existing.question_type = analysis.question_type
                existing.candidate_answer = analysis.candidate_answer
                existing.expected_concepts = analysis.expected_concepts
                existing.covered_concepts = analysis.covered_concepts
                existing.missing_concepts = analysis.missing_concepts
                existing.incorrect_concepts = analysis.incorrect_concepts
                existing.partial_concepts = analysis.partial_concepts  # F-3 fix
                existing.evidence = evidence_dict  # F-3 fix
                existing.strengths = analysis.strengths
                existing.gaps = analysis.gaps
                existing.score = analysis.score
                existing.max_score = analysis.max_score
                existing.depth_level = analysis.depth_level
                existing.confidence = analysis.confidence
                existing.interview_type = analysis.question_type.lower() if analysis.question_type else "technical"  # F-13 fix
            else:
                # Create new
                qa_record = InterviewQuestionAnalysis(
                    interview_id=interview_id,
                    turn_id=analysis.interview_turn_id,
                    question_id=analysis.pool_question_id,
                    question_number=analysis.question_number,
                    question_text=analysis.question_text,
                    question_type=analysis.question_type,
                    candidate_answer=analysis.candidate_answer,
                    expected_concepts=analysis.expected_concepts,
                    covered_concepts=analysis.covered_concepts,
                    missing_concepts=analysis.missing_concepts,
                    incorrect_concepts=analysis.incorrect_concepts,
                    partial_concepts=analysis.partial_concepts,  # F-3 fix
                    evidence=evidence_dict,  # F-3 fix
                    strengths=analysis.strengths,
                    gaps=analysis.gaps,
                    score=analysis.score,
                    max_score=analysis.max_score,
                    depth_level=analysis.depth_level,
                    confidence=analysis.confidence,
                    interview_type=analysis.question_type.lower() if analysis.question_type else "technical",  # F-13 fix
                )
                db.add(qa_record)
            
            db.commit()
            logger.debug(f"Persisted question analysis for interview {interview_id}, turn {analysis.interview_turn_id}")
            
        except Exception as e:
            logger.error(f"Failed to persist question analysis: {e}")
            db.rollback()
    
    def _analyze_from_turns(
        self,
        db: Session,
        interview: InterviewSession,
        persist: bool = True,
        update_competency: bool = True,
    ) -> InterviewAnalysis:
        """Fallback analysis using InterviewTurn records when structured conversation unavailable."""
        turns = db.query(InterviewTurn).filter(
            InterviewTurn.interview_id == interview.id,
            InterviewTurn.is_followup == False
        ).order_by(InterviewTurn.turn_number).all()
        
        question_analyses = []
        for turn in turns:
            expected_concepts = self._generate_expected_concepts(turn.question_text, interview.phase.lower())
            
            # Use AnswerAnalyzer
            analysis_result = self.answer_analyzer.analyze_answer(
                question=turn.question_text,
                answer=turn.candidate_response or "",
                expected_concepts=expected_concepts,
                interview_type=interview.phase.lower(),
            )
            
            qa = QuestionAnalysis(
                question_id=str(turn.id),
                question_number=turn.turn_number,
                question_text=turn.question_text,
                question_type="QUESTION",
                candidate_answer=turn.candidate_response or "",
                expected_concepts=expected_concepts,
                covered_concepts=analysis_result.covered_concepts,
                missing_concepts=analysis_result.missing_concepts,
                incorrect_concepts=analysis_result.incorrect_concepts,
                partial_concepts=analysis_result.partial_concepts,
                concept_evaluations=analysis_result.concept_evaluations,
                strengths=analysis_result.strengths,
                gaps=analysis_result.gaps,
                score=analysis_result.score,
                confidence=analysis_result.confidence,
                depth_level=analysis_result.depth_level,
                interview_turn_id=turn.id,
                pool_question_id=getattr(turn, 'question_id', None),
            )
            question_analyses.append(qa)
            
            if persist:
                self._persist_question_analysis(db, interview.id, qa)
        
        overall_score = self._calculate_overall_score(question_analyses)
        strong_areas, improvement_areas = self._identify_strengths_weaknesses(question_analyses)
        recurring_gaps = self._identify_recurring_gaps(question_analyses)
        pattern_summary = self._generate_pattern_summary(question_analyses, strong_areas, improvement_areas)
        confidence = self._calculate_confidence(question_analyses)
        
        competency_changes = []
        if update_competency and self.competency_updater:
            pool = db.query(ApprovedQuestionPool).filter(
                ApprovedQuestionPool.session_id == interview.session_id,
                ApprovedQuestionPool.admin_approved == True,
            ).first()
            skill_mapping = self._build_skill_mapping(pool)
            try:
                competency_updates = self.competency_updater.update_from_interview(
                    interview_id=interview.id,
                    question_analyses=[self._qa_to_dict(qa) for qa in question_analyses],
                    skill_mapping=skill_mapping,
                )
                competency_changes = [
                    {
                        "skill": u.skill,
                        "previous_score": u.previous_score,
                        "new_score": u.new_score,
                        "previous_confidence": u.previous_confidence,
                        "new_confidence": u.new_confidence,
                    }
                    for u in competency_updates
                ]
            except Exception as e:
                logger.error(f"Failed to update competency: {e}")
        
        return InterviewAnalysis(
            interview_id=interview.id,
            overall_score=overall_score,
            question_analyses=question_analyses,
            strong_areas=strong_areas,
            improvement_areas=improvement_areas,
            recurring_gaps=recurring_gaps,
            pattern_summary=pattern_summary,
            confidence=confidence,
            competency_changes=competency_changes,
        )
    
    # Keep existing helper methods (unchanged)
    def _calculate_overall_score(self, analyses: List[QuestionAnalysis]) -> float:
        if not analyses:
            return 0.0
        scores = [a.score for a in analyses]
        return round(sum(scores) / len(scores), 1)
    
    def _identify_strengths_weaknesses(self, analyses: List[QuestionAnalysis]) -> tuple:
        all_covered = []
        all_missing = []
        for a in analyses:
            all_covered.extend(a.covered_concepts)
            all_missing.extend(a.missing_concepts)
        
        from collections import Counter
        covered_counts = Counter(all_covered)
        missing_counts = Counter(all_missing)
        
        strong = [concept for concept, count in covered_counts.items() 
                  if count >= max(1, len(analyses) // 2)]
        weak = [concept for concept, count in missing_counts.items() 
                if count >= max(1, len(analyses) // 2)]
        
        return strong[:5], weak[:5]
    
    def _identify_recurring_gaps(self, analyses: List[QuestionAnalysis]) -> List[str]:
        all_gaps = []
        for a in analyses:
            all_gaps.extend(a.gaps)
        
        from collections import Counter
        gap_counts = Counter(all_gaps)
        recurring = [gap for gap, count in gap_counts.items() if count > 1]
        return recurring[:5]
    
    def _generate_pattern_summary(
        self,
        analyses: List[QuestionAnalysis],
        strong_areas: List[str],
        weak_areas: List[str],
    ) -> str:
        if not analyses:
            return "No questions analyzed."
        
        avg_score = sum(a.score for a in analyses) / len(analyses)
        
        patterns = []
        if avg_score >= 7.5:
            patterns.append("The candidate demonstrates strong technical understanding across most topics.")
        elif avg_score >= 5.5:
            patterns.append("The candidate shows moderate understanding with room for improvement.")
        else:
            patterns.append("The candidate struggles with fundamental concepts and needs significant improvement.")
        
        if strong_areas:
            patterns.append(f"Strengths include: {', '.join(strong_areas[:3])}.")
        if weak_areas:
            patterns.append(f"Areas for improvement: {', '.join(weak_areas[:3])}.")
        
        depth_counts = {}
        for a in analyses:
            depth_counts[a.depth_level] = depth_counts.get(a.depth_level, 0) + 1
        
        dominant_depth = max(depth_counts, key=depth_counts.get)
        if dominant_depth in ["Surface", "Basic"]:
            patterns.append("Answers tend to lack implementation-level depth.")
        elif dominant_depth in ["Strong", "Expert"]:
            patterns.append("Answers demonstrate deep, expert-level understanding.")
        
        return " ".join(patterns)
    
    def _calculate_confidence(self, analyses: List[QuestionAnalysis]) -> float:
        if not analyses:
            return 0.5
        
        avg_concepts = sum(len(a.expected_concepts) for a in analyses) / len(analyses)
        concept_confidence = min(avg_concepts / 8.0, 1.0)
        
        avg_answer_length = sum(len(a.candidate_answer) for a in analyses) / len(analyses)
        length_confidence = min(avg_answer_length / 500.0, 1.0)
        
        return round((concept_confidence + length_confidence) / 2, 2)


def get_interview_analysis_service() -> InterviewAnalysisService:
    """Factory function for dependency injection."""
    return InterviewAnalysisService()