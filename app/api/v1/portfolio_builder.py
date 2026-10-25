"""
FastAPI router for Portfolio Builder Assessment.

Provides orchestration endpoints for the 6-stage assessment journey:
1. Aptitude & Logical Reasoning
2. Technical Knowledge MCQ
3. Combined Aptitude & Technical MCQ
4. DSA Coding Assessment
5. Resume-Based Interview
6. Consolidated Competency Results
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.database.db import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.portfolio_builder import (
    PortfolioBuilderAttempt,
    PortfolioBuilderStage,
    PortfolioBuilderStageKey,
    PortfolioBuilderStageStatus,
)
from app.services.portfolio_builder_service import PortfolioBuilderService
from app.schemas.portfolio_builder import (
    PortfolioBuilderAttemptResponse,
    PortfolioBuilderInitializeResponse,
    PortfolioBuilderProgressResponse,
    StageStartRequest,
    StageStartResponse,
    StageCompleteRequest,
    StageCompleteResponse,
    StageResultResponse,
    ConsolidatedReportResponse,
)

router = APIRouter(prefix="/portfolio-builder", tags=["Portfolio Builder Assessment"])


@router.get("", response_model=PortfolioBuilderInitializeResponse)
def get_or_initialize_portfolio_builder(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PortfolioBuilderInitializeResponse:
    """
    Get or initialize the Portfolio Builder attempt for the authenticated student.
    
    Returns the complete attempt state with all 6 stages and their statuses.
    Safe against concurrent initialization - returns existing attempt if present.
    """
    service = PortfolioBuilderService(db)
    attempt, is_new = service.get_or_create_attempt(current_user.id)
    
    # Load stages if not already loaded
    if not attempt.stages:
        attempt = service.get_attempt_with_stages(current_user.id)
    
    response = service.build_attempt_response(attempt)
    return PortfolioBuilderInitializeResponse(attempt=response, is_new=is_new)


@router.get("/progress", response_model=PortfolioBuilderProgressResponse)
def get_portfolio_builder_progress(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PortfolioBuilderProgressResponse:
    """
    Get lightweight progress update for the Portfolio Builder.
    
    Useful for polling or resume-after-refresh scenarios.
    """
    service = PortfolioBuilderService(db)
    attempt = service.get_attempt_with_stages(current_user.id)
    
    if not attempt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio Builder attempt not found. Initialize first."
        )
    
    return service.build_progress_response(attempt)


@router.post("/stage/start", response_model=StageStartResponse)
def start_or_resume_stage(
    request: StageStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StageStartResponse:
    """
    Start or resume a specific stage.
    
    Validates:
    - Student owns the attempt
    - Stage is the current eligible stage
    - All prerequisites are completed
    - Stage not already completed
    
    Returns underlying assessment session/round/interview IDs and frontend redirect URL.
    """
    service = PortfolioBuilderService(db)
    attempt = service.get_attempt_with_stages(current_user.id)
    
    if not attempt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio Builder attempt not found. Initialize first."
        )
    
    try:
        return service.start_stage(attempt, request.stage_key)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/stage/complete", response_model=StageCompleteResponse)
def complete_stage(
    request: StageCompleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StageCompleteResponse:
    """
    Mark a stage as completed after validating actual assessment completion.
    
    Server-side validation ensures:
    - MCQ rounds: assessment_round.status == "completed"
    - Coding: assessment_round.status == "completed" with passing submissions
    - Interview: interview_session.status == "COMPLETED" with sufficient turns
    - Results: all previous stages completed
    
    Client cannot bypass by sending bare completion flag.
    """
    service = PortfolioBuilderService(db)
    attempt = service.get_attempt_with_stages(current_user.id)
    
    if not attempt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio Builder attempt not found"
        )
    
    try:
        return service.complete_stage(attempt, request.stage_key)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/stage/{stage_key}/results", response_model=StageResultResponse)
def get_stage_results(
    stage_key: PortfolioBuilderStageKey,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StageResultResponse:
    """
    Get detailed results for a specific stage.
    
    Only accessible for stages that are COMPLETED or IN_PROGRESS.
    """
    service = PortfolioBuilderService(db)
    attempt = service.get_attempt_with_stages(current_user.id)
    
    if not attempt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio Builder attempt not found"
        )
    
    stage = service.get_stage(attempt.id, stage_key)
    if not stage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stage {stage_key} not found"
        )
    
    if stage.status == PortfolioBuilderStageStatus.LOCKED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Stage {stage_key} is locked"
        )
    
    if stage.status == PortfolioBuilderStageStatus.AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stage {stage_key} not started yet"
        )
    
    return service.get_stage_results(attempt, stage_key)


@router.get("/results", response_model=ConsolidatedReportResponse)
def get_consolidated_results(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConsolidatedReportResponse:
    """
    Get the final consolidated competency report (Stage 6).
    
    Aggregates evidence from all completed stages:
    - Aptitude & Logical Reasoning scores and topic breakdown
    - Technical Knowledge subject breakdown
    - Combined Assessment category breakdown
    - Coding performance (problems passed, languages, test cases)
    - Interview performance (dimension scores, competencies)
    - Competency evidence with provenance tracking
    - Improvement recommendations based on gaps
    
    Only available after all 5 assessment stages are completed.
    """
    service = PortfolioBuilderService(db)
    attempt = service.get_attempt_with_stages(current_user.id)
    
    if not attempt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio Builder attempt not found"
        )
    
    # Check if results stage is available
    results_stage = service.get_stage(attempt.id, PortfolioBuilderStageKey.COMPETENCY_RESULTS)
    if not results_stage or results_stage.status == PortfolioBuilderStageStatus.LOCKED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Consolidated results not available. Complete all assessment stages first."
        )
    
    return service.generate_consolidated_report(attempt)