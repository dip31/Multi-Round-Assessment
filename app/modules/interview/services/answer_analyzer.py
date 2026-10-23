"""
Semantic Answer Analysis Service for EDI5.

Evaluates candidate answers against expected concepts using LLM-based
semantic reasoning. Returns structured, validated output for persistence
and competency mapping.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Any

from app.services.groq_service import GroqService, _safe_json
from app.config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class ConceptEvaluation:
    """Evaluation of a single concept."""
    concept: str
    status: str  # demonstrated, missing, incorrect, partial
    evidence: Optional[str] = None


@dataclass
class AnswerAnalysis:
    """Complete answer analysis result."""
    covered_concepts: List[str]
    missing_concepts: List[str]
    incorrect_concepts: List[str]
    partial_concepts: List[str]
    concept_evaluations: List[ConceptEvaluation]
    strengths: List[str]
    gaps: List[str]
    score: float  # 0-10
    depth_level: str  # Surface, Basic, Good, Strong, Expert
    confidence: float  # 0-1
    reasoning: str


class AnswerAnalyzer:
    """Semantic answer evaluation using LLM with structured output."""
    
    # Valid statuses for concept evaluation
    VALID_STATUSES = {"demonstrated", "missing", "incorrect", "partial"}
    
    # Valid depth levels
    VALID_DEPTH_LEVELS = {"Surface", "Basic", "Good", "Strong", "Expert"}
    
    def __init__(self, groq_service: Optional[GroqService] = None):
        self.groq = groq_service or GroqService(settings.GROQ_API_KEY)
    
    def analyze_answer(
        self,
        question: str,
        answer: str,
        expected_concepts: List[str],
        interview_type: str = "technical",
        follow_up_context: Optional[str] = None,
    ) -> AnswerAnalysis:
        """
        Analyze a candidate's answer against expected concepts.
        
        Uses semantic reasoning (not keyword matching) to evaluate:
        - Which expected concepts were demonstrated
        - Which were missing
        - Any incorrect statements
        - Partial coverage
        
        Args:
            question: The interview question asked
            answer: Candidate's answer text
            expected_concepts: List of concepts a strong answer should cover
            interview_type: "technical", "hr", or "communication"
            follow_up_context: Optional context from previous Q&A in this thread
            
        Returns:
            AnswerAnalysis with structured evaluation
        """
        if not answer or not answer.strip():
            return self._empty_analysis(expected_concepts)
        
        if not expected_concepts:
            logger.warning("No expected concepts provided for analysis")
            return self._fallback_analysis(answer, interview_type)
        
        prompt = self._build_analysis_prompt(
            question=question,
            answer=answer,
            expected_concepts=expected_concepts,
            interview_type=interview_type,
            follow_up_context=follow_up_context,
        )
        
        from app.services.groq_service import GROQ_MODEL

        try:
            response = self.groq.client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt(interview_type),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=1200,
            )
            
            raw_response = response.choices[0].message.content
            parsed = _safe_json(raw_response)
            
            if parsed and self._validate_analysis(parsed, expected_concepts):
                return self._parse_analysis(parsed, expected_concepts)
            else:
                logger.warning("LLM returned invalid analysis format, using fallback")
                return self._fallback_analysis(answer, interview_type, expected_concepts)
                
        except Exception as e:
            logger.error(f"Answer analysis failed: {e}")
            return self._fallback_analysis(answer, interview_type, expected_concepts)
    
    def _get_system_prompt(self, interview_type: str) -> str:
        """Get system prompt based on interview type."""
        base = """You are an expert interviewer evaluating a candidate's answer.
        
Your task is to perform SEMANTIC evaluation - understand the MEANING of the candidate's response,
not just keyword matching. A candidate may express a concept using different words, analogies,
or explanations. Judge based on conceptual understanding.

Return ONLY valid JSON matching the specified schema exactly."""
        
        if interview_type == "hr":
            return base + """
Focus on: behavioral reasoning, STAR method usage, self-awareness, professional attitude,
conflict resolution, leadership, adaptability, cultural fit."""
        elif interview_type == "communication":
            return base + """
Focus on: clarity, structure, conciseness, articulation, audience awareness,
ability to simplify complex topics, persuasion, active listening."""
        else:
            return base + """
Focus on: technical correctness, depth of understanding, problem-solving approach,
best practices, trade-off awareness, implementation details, edge cases."""
    
    def _build_analysis_prompt(
        self,
        question: str,
        answer: str,
        expected_concepts: List[str],
        interview_type: str,
        follow_up_context: Optional[str],
    ) -> str:
        """Build the analysis prompt."""
        concepts_json = json.dumps(expected_concepts, indent=2)
        
        followup_section = ""
        if follow_up_context:
            followup_section = f"""
Previous context in this question thread:
{follow_up_context}

"""
        
        return f"""{followup_section}Question: "{question}"
Interview Type: {interview_type}
Expected concepts to evaluate: {concepts_json}

Candidate's answer: "{answer}"

Evaluate the answer against each expected concept using SEMANTIC REASONING.
A concept is "demonstrated" if the candidate shows clear understanding, even with different wording.
A concept is "partial" if mentioned but inadequately explained or with gaps.
A concept is "incorrect" if the candidate makes a factually wrong statement about it.
A concept is "missing" if not addressed at all.

Also identify any factually incorrect statements NOT in expected concepts.

Return ONLY valid JSON with this exact structure:
{{
    "concept_evaluations": [
        {{"concept": "concept_name", "status": "demonstrated|missing|incorrect|partial", "evidence": "quote or paraphrase from answer"}},
        ...
    ],
    "incorrect_statements": ["statement1", "statement2"],
    "strengths": ["strength1", "strength2"],
    "gaps": ["gap1", "gap2"],
    "score": 7.5,
    "depth_level": "Surface|Basic|Good|Strong|Expert",
    "confidence": 0.85,
    "reasoning": "Brief explanation of overall assessment"
}}

Guidelines:
- score: 0-10 (0=empty/wrong, 3=surface, 5=basic, 7=good, 8.5=strong, 10=expert)
- depth_level: MUST be one of: Surface, Basic, Good, Strong, Expert
- confidence: 0-1 (how certain you are; lower for vague/short answers)
- concept_evaluations: MUST include ALL expected_concepts
- evidence: specific text from candidate's answer supporting the status"""
    
    def _validate_analysis(self, parsed: Dict, expected_concepts: List[str]) -> bool:
        """Validate parsed analysis has required fields and valid values."""
        required_fields = ["concept_evaluations", "score", "depth_level", "confidence"]
        for field in required_fields:
            if field not in parsed:
                return False
        
        # Check all expected concepts are evaluated
        evaluated_concepts = {e.get("concept") for e in parsed.get("concept_evaluations", [])}
        if not set(expected_concepts).issubset(evaluated_concepts):
            logger.warning(f"Missing concept evaluations. Expected: {expected_concepts}, Got: {evaluated_concepts}")
            return False
        
        # Validate statuses
        for eval_item in parsed.get("concept_evaluations", []):
            if eval_item.get("status") not in self.VALID_STATUSES:
                return False
        
        # Validate depth_level
        if parsed.get("depth_level") not in self.VALID_DEPTH_LEVELS:
            return False
        
        # Validate score range
        score = parsed.get("score", 0)
        if not isinstance(score, (int, float)) or score < 0 or score > 10:
            return False
        
        # Validate confidence range
        conf = parsed.get("confidence", 0)
        if not isinstance(conf, (int, float)) or conf < 0 or conf > 1:
            return False
        
        return True
    
    def _parse_analysis(self, parsed: Dict, expected_concepts: List[str]) -> AnswerAnalysis:
        """Parse validated analysis into AnswerAnalysis dataclass."""
        concept_evals = parsed.get("concept_evaluations", [])
        
        covered = [e["concept"] for e in concept_evals if e["status"] == "demonstrated"]
        missing = [e["concept"] for e in concept_evals if e["status"] == "missing"]
        incorrect = [e["concept"] for e in concept_evals if e["status"] == "incorrect"]
        partial = [e["concept"] for e in concept_evals if e["status"] == "partial"]
        
        # Add any additional incorrect statements
        extra_incorrect = parsed.get("incorrect_statements", [])
        
        return AnswerAnalysis(
            covered_concepts=covered,
            missing_concepts=missing,
            incorrect_concepts=incorrect + extra_incorrect,
            partial_concepts=partial,
            concept_evaluations=[ConceptEvaluation(**e) for e in concept_evals],
            strengths=parsed.get("strengths", []),
            gaps=parsed.get("gaps", []),
            score=max(0.0, min(10.0, float(parsed.get("score", 5.0)))),
            depth_level=parsed.get("depth_level", "Basic"),
            confidence=max(0.0, min(1.0, float(parsed.get("confidence", 0.8)))),
            reasoning=parsed.get("reasoning", ""),
        )
    
    def _empty_analysis(self, expected_concepts: List[str]) -> AnswerAnalysis:
        """Return analysis for empty answer."""
        return AnswerAnalysis(
            covered_concepts=[],
            missing_concepts=expected_concepts,
            incorrect_concepts=[],
            partial_concepts=[],
            concept_evaluations=[
                ConceptEvaluation(concept=c, status="missing", evidence=None)
                for c in expected_concepts
            ],
            strengths=[],
            gaps=expected_concepts,
            score=0.0,
            depth_level="Surface",
            confidence=0.9,
            reasoning="No answer provided",
        )
    
    def _fallback_analysis(
        self,
        answer: str,
        interview_type: str,
        expected_concepts: Optional[List[str]] = None,
    ) -> AnswerAnalysis:
        """Fallback analysis when LLM fails."""
        if not expected_concepts:
            expected_concepts = ["Core concept understanding", "Practical implementation"]
        
        # Simple heuristic based on answer length
        length = len(answer.strip())
        if length < 20:
            score, depth, conf = 2.0, "Surface", 0.5
        elif length < 100:
            score, depth, conf = 4.0, "Basic", 0.6
        elif length < 300:
            score, depth, conf = 6.0, "Good", 0.7
        else:
            score, depth, conf = 7.0, "Strong", 0.75
        
        return AnswerAnalysis(
            covered_concepts=expected_concepts[:max(1, len(expected_concepts)//2)],
            missing_concepts=expected_concepts[max(1, len(expected_concepts)//2):],
            incorrect_concepts=[],
            partial_concepts=[],
            concept_evaluations=[
                ConceptEvaluation(
                    concept=c,
                    status="demonstrated" if i < len(expected_concepts)//2 else "missing",
                    evidence="Fallback heuristic"
                )
                for i, c in enumerate(expected_concepts)
            ],
            strengths=["Provided a response"] if answer else [],
            gaps=expected_concepts[max(1, len(expected_concepts)//2):],
            score=score,
            depth_level=depth,
            confidence=conf,
            reasoning="Fallback heuristic analysis (LLM unavailable)",
        )


def get_answer_analyzer() -> AnswerAnalyzer:
    """Factory for dependency injection."""
    return AnswerAnalyzer()