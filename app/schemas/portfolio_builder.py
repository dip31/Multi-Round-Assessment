"""
Pydantic schemas for Portfolio Builder Assessment API.

Defines request/response models for the 6-stage orchestration layer.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class PortfolioBuilderStageKey(str, Enum):
    """Canonical stage keys in mandatory order."""
    APTITUDE = "APTITUDE"
    TECHNICAL_MCQ = "TECHNICAL_MCQ"
    COMBINED_MCQ = "COMBINED_MCQ"
    DSA_CODING = "DSA_CODING"
    RESUME_INTERVIEW = "RESUME_INTERVIEW"
    COMPETENCY_RESULTS = "COMPETENCY_RESULTS"


class PortfolioBuilderStageStatus(str, Enum):
    """Stage lifecycle status."""
    LOCKED = "LOCKED"
    AVAILABLE = "AVAILABLE"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class PortfolioBuilderAttemptStatus(str, Enum):
    """Overall attempt lifecycle status."""
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"
    ABANDONED = "ABANDONED"


# Stage order mapping for validation
STAGE_ORDER = [
    PortfolioBuilderStageKey.APTITUDE,
    PortfolioBuilderStageKey.TECHNICAL_MCQ,
    PortfolioBuilderStageKey.COMBINED_MCQ,
    PortfolioBuilderStageKey.DSA_CODING,
    PortfolioBuilderStageKey.RESUME_INTERVIEW,
    PortfolioBuilderStageKey.COMPETENCY_RESULTS,
]

STAGE_DISPLAY = {
    PortfolioBuilderStageKey.APTITUDE: {
        "number": 1,
        "title": "Aptitude & Logical Reasoning",
        "description": "Quantitative aptitude, logical reasoning, and verbal ability assessment",
        "duration_minutes": 30,
    },
    PortfolioBuilderStageKey.TECHNICAL_MCQ: {
        "number": 2,
        "title": "Technical Knowledge Assessment",
        "description": "Core CS subjects: OS, DBMS, Networks, OOP, DSA fundamentals",
        "duration_minutes": 30,
    },
    PortfolioBuilderStageKey.COMBINED_MCQ: {
        "number": 3,
        "title": "Combined Aptitude & Technical Assessment",
        "description": "Integrated assessment combining aptitude and technical questions",
        "duration_minutes": 45,
    },
    PortfolioBuilderStageKey.DSA_CODING: {
        "number": 4,
        "title": "DSA Coding Assessment",
        "description": "Data Structures & Algorithms coding challenges with automated evaluation",
        "duration_minutes": 60,
    },
    PortfolioBuilderStageKey.RESUME_INTERVIEW: {
        "number": 5,
        "title": "Resume-Based Interview",
        "description": "AI-powered technical interview grounded in your resume and projects",
        "duration_minutes": 30,
    },
    PortfolioBuilderStageKey.COMPETENCY_RESULTS: {
        "number": 6,
        "title": "Consolidated Competency Results",
        "description": "Evidence-backed competency profile with strengths, gaps, and recommendations",
        "duration_minutes": 0,  # Instant generation
    },
}


class PortfolioBuilderStageResponse(BaseModel):
    """Single stage status response."""
    stage_key: PortfolioBuilderStageKey
    sequence: int
    title: str
    description: str
    duration_minutes: int
    status: PortfolioBuilderStageStatus
    score: Optional[float] = None
    max_score: Optional[float] = None
    passed: Optional[bool] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failure_reason: Optional[str] = None
    retry_count: int = 0
    # Links to underlying assessment records
    assessment_round_id: Optional[int] = None
    interview_session_id: Optional[int] = None
    # Action for frontend
    action: Optional[str] = None  # "START", "RESUME", "VIEW_RESULTS", "LOCKED"
    action_url: Optional[str] = None


class PortfolioBuilderAttemptResponse(BaseModel):
    """Parent attempt overview response."""
    id: int
    user_id: int
    current_stage: PortfolioBuilderStageKey
    overall_status: PortfolioBuilderAttemptStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    last_activity_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    stages: List[PortfolioBuilderStageResponse]
    # Next action guidance
    next_action: Optional[str] = None
    next_stage_key: Optional[PortfolioBuilderStageKey] = None
    next_action_url: Optional[str] = None


class PortfolioBuilderInitializeResponse(BaseModel):
    """Response for initialize/get-or-create endpoint."""
    attempt: PortfolioBuilderAttemptResponse
    is_new: bool


class StageStartRequest(BaseModel):
    """Request to start/resume a stage."""
    stage_key: PortfolioBuilderStageKey


class StageStartResponse(BaseModel):
    """Response when starting a stage - provides underlying assessment details."""
    stage_key: PortfolioBuilderStageKey
    stage_status: PortfolioBuilderStageStatus
    # Underlying assessment identifiers
    assessment_session_id: Optional[int] = None
    assessment_round_id: Optional[int] = None
    interview_session_id: Optional[int] = None
    # Frontend routing
    redirect_url: str
    # Resume info
    is_resume: bool = False
    existing_progress: Optional[Dict[str, Any]] = None


class StageCompleteRequest(BaseModel):
    """Request to mark stage complete (validated server-side)."""
    stage_key: PortfolioBuilderStageKey
    # Client may send completion confirmation, but server validates actual evidence


class StageCompleteResponse(BaseModel):
    """Response after stage completion validation."""
    stage_key: PortfolioBuilderStageKey
    status: PortfolioBuilderStageStatus
    score: Optional[float] = None
    passed: Optional[bool] = None
    next_stage_key: Optional[PortfolioBuilderStageKey] = None
    next_stage_available: bool = False
    message: str


class StageResultResponse(BaseModel):
    """Detailed stage results."""
    stage_key: PortfolioBuilderStageKey
    stage_title: str
    status: PortfolioBuilderStageStatus
    score: Optional[float] = None
    max_score: Optional[float] = None
    passed: Optional[bool] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    # Stage-specific detail (varies by stage)
    detail: Dict[str, Any] = {}
    # Evidence references
    assessment_round_id: Optional[int] = None
    interview_session_id: Optional[int] = None


class ConsolidatedCompetencyEvidence(BaseModel):
    """Single competency evidence item in consolidated report."""
    competency_name: str
    canonical_skill_id: Optional[str] = None
    category: str  # Programming, Core CS, Development, AI/ML, Tools, General
    # Evidence sources
    evidence_sources: List[str] = []  # e.g., ["aptitude", "coding", "interview"]
    # Scores per source
    source_scores: Dict[str, float] = {}  # e.g., {"aptitude": 75.0, "coding": 80.0}
    # Aggregated
    aggregated_score: Optional[float] = None
    confidence: Optional[float] = None
    freshness: Optional[str] = None
    # Provenance
    evidence_count: int = 0
    assessment_round_ids: List[int] = []
    interview_session_ids: List[int] = []
    # Interpretation
    strength_areas: List[str] = []
    improvement_areas: List[str] = []
    evidence_sufficient: bool = False


class ConsolidatedReportResponse(BaseModel):
    """Final consolidated competency report (Stage 6)."""
    attempt_id: int
    user_id: int
    generated_at: datetime
    overall_completion_status: PortfolioBuilderAttemptStatus
    stages_completed: List[PortfolioBuilderStageKey]
    stages_missing: List[PortfolioBuilderStageKey]
    
    # Section A: Portfolio Builder Overview
    completion_date: Optional[datetime] = None
    total_duration_minutes: Optional[int] = None
    
    # Section B: Aptitude & Logical Reasoning
    aptitude_score: Optional[float] = None
    aptitude_max_score: Optional[float] = None
    aptitude_topic_breakdown: Dict[str, float] = {}
    aptitude_correct_count: Optional[int] = None
    aptitude_incorrect_count: Optional[int] = None
    
    # Section C: Technical Knowledge
    technical_score: Optional[float] = None
    technical_max_score: Optional[float] = None
    technical_subject_breakdown: Dict[str, float] = {}
    
    # Section D: Combined Assessment
    combined_score: Optional[float] = None
    combined_max_score: Optional[float] = None
    combined_category_breakdown: Dict[str, float] = {}
    
    # Section E: Coding Performance
    coding_problems_attempted: int = 0
    coding_problems_passed: int = 0
    coding_test_cases_passed: Optional[int] = None
    coding_test_cases_total: Optional[int] = None
    coding_languages_used: List[str] = []
    coding_competencies: List[str] = []
    
    # Section F: Interview Performance
    interview_type: Optional[str] = None
    interview_overall_score: Optional[float] = None
    interview_dimension_scores: Dict[str, float] = {}
    interview_competencies: List[str] = []
    
    # Section G: Competency Summary
    competency_evidence: List[ConsolidatedCompetencyEvidence] = []
    
    # Section H: Improvement Recommendations
    recommendations: List[Dict[str, Any]] = []
    
    # Metadata
    evidence_sources_summary: Dict[str, int] = {}
    has_insufficient_evidence: bool = False
    missing_evidence_details: List[str] = []


class PortfolioBuilderProgressResponse(BaseModel):
    """Lightweight progress response for polling/resume."""
    attempt_id: int
    current_stage: PortfolioBuilderStageKey
    overall_status: PortfolioBuilderAttemptStatus
    stages: List[PortfolioBuilderStageResponse]
    last_activity_at: Optional[datetime] = None