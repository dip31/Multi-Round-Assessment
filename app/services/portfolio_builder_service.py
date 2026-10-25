"""
Portfolio Builder Assessment Orchestration Service.

Coordinates the 6-stage assessment journey using existing EDI5 services:
1. Aptitude & Logical Reasoning (existing aptitude MCQ pipeline)
2. Technical Knowledge MCQ (existing technical MCQ pipeline)
3. Combined Aptitude & Technical MCQ (new combined round type)
4. DSA Coding Assessment (existing coding pipeline + Judge0)
5. Resume-Based Interview (existing interview pipeline + resume parsing)
6. Consolidated Competency Results (evidence aggregation from stages 1-5)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import and_, or_, func

from app.models import (
    User,
    PortfolioBuilderAttempt,
    PortfolioBuilderStage,
    AssessmentSession,
    AssessmentRound,
    InterviewSession,
    AptitudeQuestion,
    AptitudeAttempt,
    CodingProblem,
    CodingSubmission,
    StudentCompetency,
    CompetencyEvidence,
    UserResume,
    StudentProfile,
)
from app.models.portfolio_builder import (
    PortfolioBuilderStageKey,
    PortfolioBuilderStageStatus,
    PortfolioBuilderAttemptStatus,
)
from app.schemas.portfolio_builder import (
    PortfolioBuilderAttemptResponse,
    PortfolioBuilderStageResponse,
    PortfolioBuilderInitializeResponse,
    StageStartResponse,
    StageCompleteResponse,
    StageResultResponse,
    ConsolidatedReportResponse,
    ConsolidatedCompetencyEvidence,
    PortfolioBuilderProgressResponse,
    STAGE_ORDER,
    STAGE_DISPLAY,
)
from app.services.profile_service import ProfileService
from app.services.session_service import (
    create_session, start_round, complete_round, get_active_session
)


class PortfolioBuilderService:
    """Orchestration service for Portfolio Builder Assessment journey."""
    
    # Stage configuration
    STAGE_KEYS = STAGE_ORDER
    STAGE_DISPLAY = STAGE_DISPLAY
    
    def __init__(self, db: Session):
        self.db = db
    
    # ─────────────────────────────────────────────────────────────────
    # Attempt Management
    # ─────────────────────────────────────────────────────────────────
    
    def get_or_create_attempt(self, user_id: int) -> Tuple[PortfolioBuilderAttempt, bool]:
        """
        Get existing Portfolio Builder attempt or create new one.
        
        Returns (attempt, is_new). Safe against concurrent creation.
        """
        # Use SELECT FOR UPDATE to prevent race conditions
        attempt = self.db.query(PortfolioBuilderAttempt).filter(
            PortfolioBuilderAttempt.user_id == user_id
        ).with_for_update(nowait=False).first()
        
        is_new = False
        if not attempt:
            is_new = True
            attempt = PortfolioBuilderAttempt(
                user_id=user_id,
                current_stage=PortfolioBuilderStageKey.APTITUDE,
                overall_status=PortfolioBuilderAttemptStatus.ACTIVE,
                created_at=datetime.utcnow(),
                version=1,
            )
            self.db.add(attempt)
            self.db.flush()
            
            # Initialize all 6 stages
            for i, stage_key in enumerate(self.STAGE_KEYS):
                display = self.STAGE_DISPLAY[stage_key]
                stage = PortfolioBuilderStage(
                    attempt_id=attempt.id,
                    stage_key=stage_key,
                    sequence=display["number"],
                    status=PortfolioBuilderStageStatus.AVAILABLE if i == 0 else PortfolioBuilderStageStatus.LOCKED,
                )
                self.db.add(stage)
            
            self.db.flush()
            self.db.commit()
            self.db.refresh(attempt)
        
        return attempt, is_new
    
    def get_attempt(self, user_id: int) -> Optional[PortfolioBuilderAttempt]:
        """Get existing attempt without creating."""
        return self.db.query(PortfolioBuilderAttempt).filter(
            PortfolioBuilderAttempt.user_id == user_id
        ).first()
    
    def get_attempt_with_stages(self, user_id: int) -> Optional[PortfolioBuilderAttempt]:
        """Get attempt with stages eagerly loaded."""
        attempt = self.db.query(PortfolioBuilderAttempt).options(
            selectinload(PortfolioBuilderAttempt.stages)
        ).filter(PortfolioBuilderAttempt.user_id == user_id).first()
        if attempt:
            self._sync_in_progress_stages(attempt)
        return attempt
    
    # ─────────────────────────────────────────────────────────────────
    # Stage State Management
    # ─────────────────────────────────────────────────────────────────
    
    def get_stage(self, attempt_id: int, stage_key: PortfolioBuilderStageKey) -> Optional[PortfolioBuilderStage]:
        """Get a specific stage by attempt and key."""
        return self.db.query(PortfolioBuilderStage).filter(
            PortfolioBuilderStage.attempt_id == attempt_id,
            PortfolioBuilderStage.stage_key == stage_key
        ).first()
    
    def get_current_stage(self, attempt: PortfolioBuilderAttempt) -> Optional[PortfolioBuilderStage]:
        """Get the current eligible stage for an attempt."""
        return self.get_stage(attempt.id, attempt.current_stage)
    
    def validate_stage_eligibility(
        self, 
        attempt: PortfolioBuilderAttempt, 
        stage_key: PortfolioBuilderStageKey
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate if a stage can be started.
        
        Returns (is_eligible, error_message).
        """
        # Check if stage exists in our ordered list
        if stage_key not in self.STAGE_KEYS:
            return False, f"Invalid stage: {stage_key}"
        
        # Check if this is the current stage
        if attempt.current_stage != stage_key:
            # Find position of requested stage
            req_idx = self.STAGE_KEYS.index(stage_key)
            curr_idx = self.STAGE_KEYS.index(attempt.current_stage)
            
            if req_idx < curr_idx:
                # Stage already completed - check if it's actually completed
                stage = self.get_stage(attempt.id, stage_key)
                if stage and stage.status == PortfolioBuilderStageStatus.COMPLETED:
                    return False, f"Stage {stage_key} already completed. Use results endpoint."
                return False, f"Stage {stage_key} is not the current stage"
            else:
                return False, f"Stage {stage_key} is locked. Complete previous stages first."
        
        # Check stage status
        stage = self.get_stage(attempt.id, stage_key)
        if not stage:
            return False, f"Stage {stage_key} not found"
        
        if stage.status == PortfolioBuilderStageStatus.COMPLETED:
            return False, f"Stage {stage_key} already completed"
        
        if stage.status == PortfolioBuilderStageStatus.LOCKED:
            return False, f"Stage {stage_key} is locked"
        
        # Check prerequisites - all previous stages must be COMPLETED
        curr_idx = self.STAGE_KEYS.index(stage_key)
        for i in range(curr_idx):
            prev_stage = self.get_stage(attempt.id, self.STAGE_KEYS[i])
            if not prev_stage or prev_stage.status != PortfolioBuilderStageStatus.COMPLETED:
                return False, f"Prerequisite stage {self.STAGE_KEYS[i]} not completed"
        
        return True, None
    
    def start_stage(
        self, 
        attempt: PortfolioBuilderAttempt, 
        stage_key: PortfolioBuilderStageKey
    ) -> StageStartResponse:
        """
        Start or resume a stage.
        
        Creates or resumes the underlying assessment round/interview session.
        """
        # Auto-complete any in-progress stages whose underlying assessment
        # is actually finished (e.g. all MCQ questions answered).  This must
        # run *before* the eligibility check so prerequisite validation sees
        # the correct stage statuses.
        self._sync_in_progress_stages(attempt)
        
        eligible, error = self.validate_stage_eligibility(attempt, stage_key)
        if not eligible:
            raise ValueError(error)
        
        stage = self.get_stage(attempt.id, stage_key)
        
        # Check if already in progress (resume)
        if stage.status == PortfolioBuilderStageStatus.IN_PROGRESS:
            return self._resume_or_create_stage_round(attempt, stage)
        
        # Mark as in progress
        stage.status = PortfolioBuilderStageStatus.IN_PROGRESS
        stage.started_at = stage.started_at or datetime.utcnow()
        attempt.last_activity_at = datetime.utcnow()
        attempt.version += 1
        self.db.flush()
        
        # Create underlying assessment based on stage
        res = self._create_underlying_assessment(attempt, stage)
        self.db.commit()
        return res
    
    def _resume_or_create_stage_round(
        self,
        attempt: PortfolioBuilderAttempt,
        stage: PortfolioBuilderStage,
    ) -> StageStartResponse:
        """Resume an existing stage or create its underlying assessment if missing or expired."""
        from app.models.interview import InterviewSession

        if stage.stage_key in [
            PortfolioBuilderStageKey.APTITUDE,
            PortfolioBuilderStageKey.TECHNICAL_MCQ,
            PortfolioBuilderStageKey.COMBINED_MCQ,
        ]:
            if not stage.assessment_round_id:
                res = self._create_underlying_assessment(attempt, stage)
                self.db.commit()
                return res

            round_obj = (
                self.db.query(AssessmentRound)
                .filter(AssessmentRound.id == stage.assessment_round_id)
                .first()
            )
            if not round_obj:
                res = self._create_underlying_assessment(attempt, stage)
                self.db.commit()
                return res

            # Ensure parent session is in_progress
            session_obj = (
                self.db.query(AssessmentSession)
                .filter(AssessmentSession.id == round_obj.session_id)
                .first()
            )
            if not session_obj or session_obj.status != "in_progress":
                if session_obj:
                    session_obj.status = "in_progress"
                    session_obj.expires_at = datetime.utcnow() + timedelta(hours=3)
                    session_obj.completed_at = None
                else:
                    new_session = self._get_or_create_assessment_session(attempt)
                    round_obj.session_id = new_session.id

            # Ensure round is active
            if round_obj.status != "active" or (
                round_obj.expires_at and round_obj.expires_at <= datetime.utcnow()
            ):
                round_obj.status = "active"
                duration = self.STAGE_DISPLAY[stage.stage_key]["duration_minutes"]
                round_obj.expires_at = datetime.utcnow() + timedelta(minutes=duration)
                round_obj.completed_at = None

            self.db.commit()
            return self._build_resume_response(stage)

        elif stage.stage_key == PortfolioBuilderStageKey.DSA_CODING:
            if not stage.assessment_round_id:
                res = self._create_underlying_assessment(attempt, stage)
                self.db.commit()
                return res

            round_obj = (
                self.db.query(AssessmentRound)
                .filter(AssessmentRound.id == stage.assessment_round_id)
                .first()
            )
            if not round_obj:
                res = self._create_underlying_assessment(attempt, stage)
                self.db.commit()
                return res

            session_obj = (
                self.db.query(AssessmentSession)
                .filter(AssessmentSession.id == round_obj.session_id)
                .first()
            )
            if not session_obj or session_obj.status != "in_progress":
                if session_obj:
                    session_obj.status = "in_progress"
                    session_obj.expires_at = datetime.utcnow() + timedelta(hours=3)
                    session_obj.completed_at = None
                else:
                    new_session = self._get_or_create_assessment_session(attempt)
                    round_obj.session_id = new_session.id

            if round_obj.status != "active" or (
                round_obj.expires_at and round_obj.expires_at <= datetime.utcnow()
            ):
                round_obj.status = "active"
                duration = self.STAGE_DISPLAY[stage.stage_key]["duration_minutes"]
                round_obj.expires_at = datetime.utcnow() + timedelta(minutes=duration)
                round_obj.completed_at = None

            self.db.commit()
            return self._build_resume_response(stage)

        elif stage.stage_key == PortfolioBuilderStageKey.RESUME_INTERVIEW:
            if not stage.interview_session_id or not stage.assessment_round_id:
                res = self._create_underlying_assessment(attempt, stage)
                self.db.commit()
                return res

            int_sess = (
                self.db.query(InterviewSession)
                .filter(InterviewSession.id == stage.interview_session_id)
                .first()
            )
            round_obj = (
                self.db.query(AssessmentRound)
                .filter(AssessmentRound.id == stage.assessment_round_id)
                .first()
            )
            if not int_sess or not round_obj:
                res = self._create_underlying_assessment(attempt, stage)
                self.db.commit()
                return res

            session_obj = (
                self.db.query(AssessmentSession)
                .filter(AssessmentSession.id == round_obj.session_id)
                .first()
            )
            if not session_obj or session_obj.status != "in_progress":
                if session_obj:
                    session_obj.status = "in_progress"
                    session_obj.expires_at = datetime.utcnow() + timedelta(hours=3)
                    session_obj.completed_at = None
                else:
                    new_session = self._get_or_create_assessment_session(attempt)
                    round_obj.session_id = new_session.id
                    int_sess.session_id = new_session.id

            if round_obj.status != "active" or (
                round_obj.expires_at and round_obj.expires_at <= datetime.utcnow()
            ):
                round_obj.status = "active"
                duration = self.STAGE_DISPLAY[stage.stage_key]["duration_minutes"]
                round_obj.expires_at = datetime.utcnow() + timedelta(minutes=duration)
                round_obj.completed_at = None

            if int_sess.status != "ACTIVE":
                int_sess.status = "ACTIVE"
                int_sess.completed_at = None

            self.db.commit()
            return self._build_resume_response(stage)

        else:
            return self._build_resume_response(stage)
    
    def _sync_in_progress_stages(self, attempt: PortfolioBuilderAttempt) -> None:
        """Check in-progress stages and auto-complete them if underlying round completed."""
        changed = False
        for stage in (attempt.stages or []):
            if stage.status == PortfolioBuilderStageStatus.IN_PROGRESS:
                validation = self._validate_stage_completion(stage)
                if validation.get("completed"):
                    stage.status = PortfolioBuilderStageStatus.COMPLETED
                    stage.completed_at = datetime.utcnow()
                    stage.score = validation.get("score")
                    stage.max_score = validation.get("max_score")
                    stage.passed = validation.get("passed", True)
                    
                    next_key = self._get_next_stage_key(stage.stage_key)
                    if next_key:
                        next_stage = self.get_stage(attempt.id, next_key)
                        if next_stage and next_stage.status == PortfolioBuilderStageStatus.LOCKED:
                            next_stage.status = PortfolioBuilderStageStatus.AVAILABLE
                            attempt.current_stage = next_key
                    else:
                        attempt.overall_status = PortfolioBuilderAttemptStatus.COMPLETED
                        attempt.completed_at = datetime.utcnow()
                        attempt.current_stage = PortfolioBuilderStageKey.COMPETENCY_RESULTS
                    changed = True
        if changed:
            attempt.last_activity_at = datetime.utcnow()
            attempt.version += 1
            self.db.flush()
            self.db.commit()
    
    def _build_resume_response(self, stage: PortfolioBuilderStage) -> StageStartResponse:
        """Build response for resuming an existing stage."""
        # Build proper redirect URL with IDs
        if stage.stage_key in [PortfolioBuilderStageKey.APTITUDE, PortfolioBuilderStageKey.TECHNICAL_MCQ, PortfolioBuilderStageKey.COMBINED_MCQ]:
            redirect_url = f"/aptitude?roundId={stage.assessment_round_id}"
        elif stage.stage_key == PortfolioBuilderStageKey.DSA_CODING:
            redirect_url = f"/coding?roundId={stage.assessment_round_id}"
        elif stage.stage_key == PortfolioBuilderStageKey.RESUME_INTERVIEW:
            redirect_url = f"/resume-upload?sessionId={stage.interview_session_id}"
        else:
            redirect_url = "/portfolio-builder/results"
        
        return StageStartResponse(
            stage_key=stage.stage_key,
            stage_status=stage.status,
            assessment_session_id=stage.assessment_round.session_id if stage.assessment_round else None,
            assessment_round_id=stage.assessment_round_id,
            interview_session_id=stage.interview_session_id,
            redirect_url=redirect_url,
            is_resume=True,
            existing_progress=self._get_existing_progress(stage),
        )
    
    def _create_underlying_assessment(
        self, 
        attempt: PortfolioBuilderAttempt, 
        stage: PortfolioBuilderStage
    ) -> StageStartResponse:
        """Create the underlying assessment round/interview for a stage."""
        from app.services.session_service import start_round, get_active_round
        
        # Get or create assessment session for this portfolio builder attempt
        assessment_session = self._get_or_create_assessment_session(attempt)
        
        # Complete any lingering active round from a previous stage so that
        # start_round doesn't reject with "Another assessment round is already active"
        existing_active = get_active_round(self.db, assessment_session.id)
        if existing_active is not None:
            complete_round(self.db, existing_active.id)
        
        if stage.stage_key in [PortfolioBuilderStageKey.APTITUDE, PortfolioBuilderStageKey.TECHNICAL_MCQ, PortfolioBuilderStageKey.COMBINED_MCQ]:
            # MCQ stages - create assessment round
            round_type_map = {
                PortfolioBuilderStageKey.APTITUDE: "aptitude",
                PortfolioBuilderStageKey.TECHNICAL_MCQ: "technical",
                PortfolioBuilderStageKey.COMBINED_MCQ: "combined",
            }
            
            round_type = round_type_map[stage.stage_key]
            
            # Create assessment round using session service
            assessment_round = start_round(
                self.db, 
                assessment_session.id, 
                round_type, 
                practice_type="portfolio_builder"
            )
            # Override max_questions and expiry for portfolio builder
            assessment_round.max_questions = self._get_stage_question_count(stage.stage_key)
            assessment_round.expires_at = datetime.utcnow() + timedelta(minutes=self.STAGE_DISPLAY[stage.stage_key]["duration_minutes"])
            self.db.flush()
            
            # Link to stage
            stage.assessment_round_id = assessment_round.id
            self.db.flush()
            
            redirect_url = f"/aptitude?roundId={assessment_round.id}"
            
            return StageStartResponse(
                stage_key=stage.stage_key,
                stage_status=stage.status,
                assessment_session_id=assessment_session.id,
                assessment_round_id=assessment_round.id,
                redirect_url=redirect_url,
                is_resume=False,
            )
        
        elif stage.stage_key == PortfolioBuilderStageKey.DSA_CODING:
            # Coding stage - create coding round
            assessment_round = start_round(
                self.db,
                assessment_session.id,
                "coding",
                practice_type="portfolio_builder"
            )
            assessment_round.max_questions = self._get_stage_question_count(stage.stage_key)
            assessment_round.expires_at = datetime.utcnow() + timedelta(minutes=self.STAGE_DISPLAY[stage.stage_key]["duration_minutes"])
            self.db.flush()
            
            stage.assessment_round_id = assessment_round.id
            self.db.flush()
            
            redirect_url = f"/coding?roundId={assessment_round.id}"
            
            return StageStartResponse(
                stage_key=stage.stage_key,
                stage_status=stage.status,
                assessment_session_id=assessment_session.id,
                assessment_round_id=assessment_round.id,
                redirect_url=redirect_url,
                is_resume=False,
            )
        
        elif stage.stage_key == PortfolioBuilderStageKey.RESUME_INTERVIEW:
            # Interview stage - create interview session linked to assessment round
            assessment_round = start_round(
                self.db,
                assessment_session.id,
                "interview",
                practice_type="portfolio_builder"
            )
            assessment_round.max_questions = 10  # Default interview turns
            assessment_round.expires_at = datetime.utcnow() + timedelta(minutes=self.STAGE_DISPLAY[stage.stage_key]["duration_minutes"])
            self.db.flush()
            
            # Create interview session
            interview_session = InterviewSession(
                session_id=assessment_session.id,
                round_id=assessment_round.id,
                phase="TECHNICAL",  # Resume-based technical interview
                current_turn=0,
                total_turns=10,
                status="ACTIVE",
                created_at=datetime.utcnow(),
            )
            self.db.add(interview_session)
            self.db.flush()
            
            # Link both to stage
            stage.assessment_round_id = assessment_round.id
            stage.interview_session_id = interview_session.id
            self.db.flush()
            
            redirect_url = f"/resume-upload?sessionId={interview_session.id}"
            
            return StageStartResponse(
                stage_key=stage.stage_key,
                stage_status=stage.status,
                assessment_session_id=assessment_session.id,
                assessment_round_id=assessment_round.id,
                interview_session_id=interview_session.id,
                redirect_url=redirect_url,
                is_resume=False,
            )
        
        elif stage.stage_key == PortfolioBuilderStageKey.COMPETENCY_RESULTS:
            # Results stage - no underlying assessment, just generate report
            redirect_url = "/portfolio-builder/results"
            return StageStartResponse(
                stage_key=stage.stage_key,
                stage_status=stage.status,
                assessment_session_id=assessment_session.id,
                redirect_url=redirect_url,
                is_resume=False,
            )
        
        raise ValueError(f"Unknown stage: {stage.stage_key}")
    
    def _get_or_create_assessment_session(self, attempt: PortfolioBuilderAttempt) -> AssessmentSession:
        """Get or create the parent assessment session for this portfolio builder attempt."""
        # Use the session service function to create/get session
        return create_session(self.db, attempt.user_id)
    
    def _get_stage_question_count(self, stage_key: PortfolioBuilderStageKey) -> int:
        """Get configured question count for a stage."""
        counts = {
            PortfolioBuilderStageKey.APTITUDE: 20,
            PortfolioBuilderStageKey.TECHNICAL_MCQ: 20,
            PortfolioBuilderStageKey.COMBINED_MCQ: 30,
            PortfolioBuilderStageKey.DSA_CODING: 3,
            PortfolioBuilderStageKey.RESUME_INTERVIEW: 10,
            PortfolioBuilderStageKey.COMPETENCY_RESULTS: 0,
        }
        return counts.get(stage_key, 20)
    
    def _get_stage_redirect_url(self, stage_key: PortfolioBuilderStageKey) -> str:
        """Get frontend redirect URL for a stage."""
        url_map = {
            PortfolioBuilderStageKey.APTITUDE: "/portfolio-builder/stage/aptitude",
            PortfolioBuilderStageKey.TECHNICAL_MCQ: "/portfolio-builder/stage/technical-mcq",
            PortfolioBuilderStageKey.COMBINED_MCQ: "/portfolio-builder/stage/combined-mcq",
            PortfolioBuilderStageKey.DSA_CODING: "/portfolio-builder/stage/dsa-coding",
            PortfolioBuilderStageKey.RESUME_INTERVIEW: "/portfolio-builder/stage/resume-interview",
            PortfolioBuilderStageKey.COMPETENCY_RESULTS: "/portfolio-builder/results",
        }
        return url_map.get(stage_key, "/portfolio-builder")
    
    def _get_existing_progress(self, stage: PortfolioBuilderStage) -> Dict[str, Any]:
        """Get existing progress data for resume."""
        progress = {}
        
        if stage.assessment_round:
            progress["assessment_round"] = {
                "id": stage.assessment_round.id,
                "status": stage.assessment_round.status,
                "score": stage.assessment_round.score,
                "started_at": stage.assessment_round.started_at.isoformat() if stage.assessment_round.started_at else None,
            }
        
        if stage.interview_session:
            progress["interview_session"] = {
                "id": stage.interview_session.id,
                "status": stage.interview_session.status,
                "current_turn": stage.interview_session.current_turn,
                "total_turns": stage.interview_session.total_turns,
            }
        
        return progress
    
    # ─────────────────────────────────────────────────────────────────
    # Stage Completion Validation
    # ─────────────────────────────────────────────────────────────────
    
    def complete_stage(
        self, 
        attempt: PortfolioBuilderAttempt, 
        stage_key: PortfolioBuilderStageKey
    ) -> StageCompleteResponse:
        """
        Validate and mark stage as completed.
        
        Server-side validation of actual assessment completion.
        """
        stage = self.get_stage(attempt.id, stage_key)
        if not stage:
            raise ValueError(f"Stage {stage_key} not found")
        
        if stage.status == PortfolioBuilderStageStatus.COMPLETED:
            return StageCompleteResponse(
                stage_key=stage_key,
                status=stage.status,
                score=stage.score,
                passed=stage.passed,
                next_stage_key=self._get_next_stage_key(stage_key),
                next_stage_available=False,
                message="Stage already completed",
            )
        
        # Validate completion based on stage type
        validation_result = self._validate_stage_completion(stage)
        
        if not validation_result["completed"]:
            raise ValueError(validation_result["reason"])
        
        # Mark stage completed
        stage.status = PortfolioBuilderStageStatus.COMPLETED
        stage.completed_at = datetime.utcnow()
        stage.score = validation_result.get("score")
        stage.max_score = validation_result.get("max_score")
        stage.passed = validation_result.get("passed", True)
        
        # Update attempt
        attempt.last_activity_at = datetime.utcnow()
        attempt.version += 1
        
        # Unlock next stage
        next_stage_key = self._get_next_stage_key(stage_key)
        if next_stage_key:
            next_stage = self.get_stage(attempt.id, next_stage_key)
            if next_stage and next_stage.status == PortfolioBuilderStageStatus.LOCKED:
                next_stage.status = PortfolioBuilderStageStatus.AVAILABLE
                attempt.current_stage = next_stage_key
        
        # Check if all stages completed
        if not next_stage_key:
            attempt.overall_status = PortfolioBuilderAttemptStatus.COMPLETED
            attempt.completed_at = datetime.utcnow()
            attempt.current_stage = PortfolioBuilderStageKey.COMPETENCY_RESULTS
        elif stage_key == PortfolioBuilderStageKey.RESUME_INTERVIEW:
            # Auto-complete the Competency Results stage after interview completes
            results_stage = self.get_stage(attempt.id, PortfolioBuilderStageKey.COMPETENCY_RESULTS)
            if results_stage and results_stage.status == PortfolioBuilderStageStatus.AVAILABLE:
                results_stage.status = PortfolioBuilderStageStatus.COMPLETED
                results_stage.completed_at = datetime.utcnow()
                results_stage.score = 100.0
                results_stage.max_score = 100.0
                results_stage.passed = True
                attempt.overall_status = PortfolioBuilderAttemptStatus.COMPLETED
                attempt.completed_at = datetime.utcnow()
                attempt.current_stage = PortfolioBuilderStageKey.COMPETENCY_RESULTS
        
        self.db.flush()
        self.db.commit()
        
        return StageCompleteResponse(
            stage_key=stage_key,
            status=stage.status,
            score=stage.score,
            passed=stage.passed,
            next_stage_key=next_stage_key,
            next_stage_available=next_stage_key is not None,
            message=f"Stage {stage_key} completed successfully",
        )
    
    def _validate_stage_completion(self, stage: PortfolioBuilderStage) -> Dict[str, Any]:
        """Validate that the underlying assessment is actually complete."""
        
        if stage.stage_key in [PortfolioBuilderStageKey.APTITUDE, PortfolioBuilderStageKey.TECHNICAL_MCQ, PortfolioBuilderStageKey.COMBINED_MCQ]:
            # MCQ stages - check assessment round completion
            if not stage.assessment_round:
                return {"completed": False, "reason": "No assessment round linked"}
            
            # If round is already marked completed, use its score
            if stage.assessment_round.status == "completed":
                return {
                    "completed": True,
                    "score": round((stage.assessment_round.score or 0) * 100, 1),
                    "max_score": 100.0,
                    "passed": (stage.assessment_round.score or 0) >= 0.5,
                }
            
            # Round not yet marked "completed" — check if all questions were answered.
            # The frontend may have finished answering but never explicitly completed
            # the round on the backend.
            attempt_count = self.db.query(func.count(AptitudeAttempt.id)).filter(
                AptitudeAttempt.round_id == stage.assessment_round.id
            ).scalar() or 0
            
            max_q = stage.assessment_round.max_questions or self._get_stage_question_count(stage.stage_key)
            
            if attempt_count >= max_q:
                # All questions answered — auto-complete the round and compute score
                correct_count = self.db.query(func.count(AptitudeAttempt.id)).filter(
                    AptitudeAttempt.round_id == stage.assessment_round.id,
                    AptitudeAttempt.is_correct.is_(True),
                ).scalar() or 0
                
                score = correct_count / max(attempt_count, 1)
                stage.assessment_round.score = round(score, 4)
                stage.assessment_round.status = "completed"
                stage.assessment_round.completed_at = datetime.utcnow()
                self.db.flush()
                
                return {
                    "completed": True,
                    "score": round(score * 100, 1),
                    "max_score": 100.0,
                    "passed": score >= 0.5,
                }
            
            # Round is still active and not enough questions answered
            return {"completed": False, "reason": f"Assessment round not completed ({attempt_count}/{max_q} questions answered)"}
        
        elif stage.stage_key == PortfolioBuilderStageKey.DSA_CODING:
            # Coding stage - check coding submissions
            if not stage.assessment_round:
                return {"completed": False, "reason": "No coding round linked"}
            
            if stage.assessment_round.status != "completed":
                return {"completed": False, "reason": "Coding round not completed"}
            
            # Check submissions
            submissions = self.db.query(CodingSubmission).filter(
                CodingSubmission.round_id == stage.assessment_round_id
            ).all()
            
            if not submissions:
                return {"completed": False, "reason": "No coding submissions found"}
            
            # At least one problem should have passing score
            passed_count = sum(1 for s in submissions if (s.score or 0) >= 0.7)
            
            return {
                "completed": True,
                "score": round(max((s.score or 0) for s in submissions) * 100, 1) if submissions else 0,
                "max_score": 100.0,
                "passed": passed_count > 0,
            }
        
        elif stage.stage_key == PortfolioBuilderStageKey.RESUME_INTERVIEW:
            # Interview stage - check interview completion
            if not stage.interview_session:
                return {"completed": False, "reason": "No interview session linked"}
            
            if stage.interview_session.status not in ["COMPLETED", "TERMINATED"]:
                return {"completed": False, "reason": "Interview not completed"}
            
            # Check if enough turns completed
            turns = self.db.query(InterviewSession.turns).filter(
                InterviewSession.id == stage.interview_session_id
            ).first()
            
            # Get turns from relationship
            interview = self.db.query(InterviewSession).options(
                selectinload(InterviewSession.turns)
            ).filter(InterviewSession.id == stage.interview_session_id).first()
            
            completed_turns = [t for t in (interview.turns or []) if t.final_score is not None]
            
            if len(completed_turns) < 3:  # Minimum meaningful interview
                return {"completed": False, "reason": "Insufficient interview turns completed"}
            
            avg_score = sum(t.final_score for t in completed_turns) / len(completed_turns)
            
            return {
                "completed": True,
                "score": round(avg_score * 100, 1),
                "max_score": 100.0,
                "passed": avg_score >= 0.6,  # 60% threshold
            }
        
        elif stage.stage_key == PortfolioBuilderStageKey.COMPETENCY_RESULTS:
            # Results stage - always completable if previous stages done
            return {
                "completed": True,
                "score": 100.0,
                "max_score": 100.0,
                "passed": True,
            }
        
        return {"completed": False, "reason": f"Unknown stage: {stage.stage_key}"}
    
    def _get_next_stage_key(self, current_stage: PortfolioBuilderStageKey) -> Optional[PortfolioBuilderStageKey]:
        """Get the next stage key in sequence."""
        try:
            idx = self.STAGE_KEYS.index(current_stage)
            if idx + 1 < len(self.STAGE_KEYS):
                return self.STAGE_KEYS[idx + 1]
        except ValueError:
            pass
        return None
    
    # ─────────────────────────────────────────────────────────────────
    # Response Building
    # ─────────────────────────────────────────────────────────────────
    
    def build_attempt_response(self, attempt: PortfolioBuilderAttempt) -> PortfolioBuilderAttemptResponse:
        """Build full attempt response with all stages."""
        stages_resp = []
        for stage in sorted(attempt.stages, key=lambda s: s.sequence):
            stages_resp.append(self._build_stage_response(stage))
        
        next_stage = self._get_next_stage_key(attempt.current_stage)
        next_action = None
        next_action_url = None
        
        current_stage_obj = self.get_stage(attempt.id, attempt.current_stage)
        if current_stage_obj:
            if current_stage_obj.status == PortfolioBuilderStageStatus.AVAILABLE:
                next_action = "START"
                next_action_url = self._get_stage_redirect_url(attempt.current_stage)
            elif current_stage_obj.status == PortfolioBuilderStageStatus.IN_PROGRESS:
                next_action = "RESUME"
                next_action_url = self._get_stage_redirect_url(attempt.current_stage)
            elif current_stage_obj.status == PortfolioBuilderStageStatus.COMPLETED:
                if next_stage:
                    next_action = "START"
                    next_action_url = self._get_stage_redirect_url(next_stage)
                else:
                    next_action = "VIEW_RESULTS"
                    next_action_url = "/portfolio-builder/results"
        
        return PortfolioBuilderAttemptResponse(
            id=attempt.id,
            user_id=attempt.user_id,
            current_stage=attempt.current_stage,
            overall_status=attempt.overall_status,
            created_at=attempt.created_at,
            started_at=attempt.started_at,
            last_activity_at=attempt.last_activity_at,
            completed_at=attempt.completed_at,
            stages=stages_resp,
            next_action=next_action,
            next_stage_key=next_stage,
            next_action_url=next_action_url,
        )
    
    def _build_stage_response(self, stage: PortfolioBuilderStage) -> PortfolioBuilderStageResponse:
        """Build stage response with display info and action."""
        display = self.STAGE_DISPLAY[stage.stage_key]
        
        # Determine action based on status
        action = None
        action_url = None
        if stage.status == PortfolioBuilderStageStatus.AVAILABLE:
            action = "START"
            action_url = self._get_stage_redirect_url(stage.stage_key)
        elif stage.status == PortfolioBuilderStageStatus.IN_PROGRESS:
            action = "RESUME"
            action_url = self._get_stage_redirect_url(stage.stage_key)
        elif stage.status == PortfolioBuilderStageStatus.COMPLETED:
            action = "VIEW_RESULTS"
            action_url = self._get_stage_redirect_url(stage.stage_key)
        elif stage.status == PortfolioBuilderStageStatus.LOCKED:
            action = "LOCKED"
        
        return PortfolioBuilderStageResponse(
            stage_key=stage.stage_key,
            sequence=stage.sequence,
            title=display["title"],
            description=display["description"],
            duration_minutes=display["duration_minutes"],
            status=stage.status,
            score=stage.score,
            max_score=stage.max_score,
            passed=stage.passed,
            started_at=stage.started_at,
            completed_at=stage.completed_at,
            failure_reason=stage.failure_reason,
            retry_count=stage.retry_count,
            assessment_round_id=stage.assessment_round_id,
            interview_session_id=stage.interview_session_id,
            action=action,
            action_url=action_url,
        )
    
    def build_progress_response(self, attempt: PortfolioBuilderAttempt) -> PortfolioBuilderProgressResponse:
        """Build lightweight progress response."""
        stages_resp = [self._build_stage_response(s) for s in sorted(attempt.stages, key=lambda s: s.sequence)]
        
        return PortfolioBuilderProgressResponse(
            attempt_id=attempt.id,
            current_stage=attempt.current_stage,
            overall_status=attempt.overall_status,
            stages=stages_resp,
            last_activity_at=attempt.last_activity_at,
        )
    
    # ─────────────────────────────────────────────────────────────────
    # Stage Results
    # ─────────────────────────────────────────────────────────────────
    
    def get_stage_results(self, attempt: PortfolioBuilderAttempt, stage_key: PortfolioBuilderStageKey) -> StageResultResponse:
        """Get detailed results for a completed stage."""
        stage = self.get_stage(attempt.id, stage_key)
        if not stage:
            raise ValueError(f"Stage {stage_key} not found")
        
        display = self.STAGE_DISPLAY[stage_key]
        detail = {}
        
        if stage.stage_key in [PortfolioBuilderStageKey.APTITUDE, PortfolioBuilderStageKey.TECHNICAL_MCQ, PortfolioBuilderStageKey.COMBINED_MCQ]:
            detail = self._get_mcq_stage_detail(stage)
        elif stage.stage_key == PortfolioBuilderStageKey.DSA_CODING:
            detail = self._get_coding_stage_detail(stage)
        elif stage.stage_key == PortfolioBuilderStageKey.RESUME_INTERVIEW:
            detail = self._get_interview_stage_detail(stage)
        elif stage.stage_key == PortfolioBuilderStageKey.COMPETENCY_RESULTS:
            detail = {}
        
        return StageResultResponse(
            stage_key=stage.stage_key,
            stage_title=display["title"],
            status=stage.status,
            score=stage.score,
            max_score=stage.max_score,
            passed=stage.passed,
            started_at=stage.started_at,
            completed_at=stage.completed_at,
            detail=detail,
            assessment_round_id=stage.assessment_round_id,
            interview_session_id=stage.interview_session_id,
        )
    
    def _get_mcq_stage_detail(self, stage: PortfolioBuilderStage) -> Dict[str, Any]:
        """Get MCQ stage detail from aptitude attempts."""
        if not stage.assessment_round:
            return {}
        
        attempts = self.db.query(AptitudeAttempt).filter(
            AptitudeAttempt.round_id == stage.assessment_round_id
        ).all()
        
        if not attempts:
            return {}
        
        # Get question details for topic breakdown
        question_ids = [a.question_id for a in attempts]
        questions = self.db.query(AptitudeQuestion).filter(
            AptitudeQuestion.id.in_(question_ids)
        ).all()
        question_map = {q.id: q for q in questions}
        
        correct = sum(1 for a in attempts if a.is_correct)
        incorrect = sum(1 for a in attempts if a.is_correct is False)
        unanswered = sum(1 for a in attempts if a.is_correct is None)
        
        # Topic breakdown
        topic_stats = {}
        for a in attempts:
            q = question_map.get(a.question_id)
            if q and q.topic_id:
                topic_name = f"topic_{q.topic_id}"  # Could join to get name
                if topic_name not in topic_stats:
                    topic_stats[topic_name] = {"correct": 0, "total": 0}
                topic_stats[topic_name]["total"] += 1
                if a.is_correct:
                    topic_stats[topic_name]["correct"] += 1
        
        topic_breakdown = {
            topic: round(stats["correct"] / stats["total"] * 100, 1) if stats["total"] > 0 else 0
            for topic, stats in topic_stats.items()
        }
        
        return {
            "total_questions": len(attempts),
            "correct": correct,
            "incorrect": incorrect,
            "unanswered": unanswered,
            "accuracy": round(correct / len(attempts) * 100, 1) if attempts else 0,
            "topic_breakdown": topic_breakdown,
        }
    
    def _get_coding_stage_detail(self, stage: PortfolioBuilderStage) -> Dict[str, Any]:
        """Get coding stage detail from submissions."""
        if not stage.assessment_round:
            return {}
        
        submissions = self.db.query(CodingSubmission).filter(
            CodingSubmission.round_id == stage.assessment_round_id
        ).all()
        
        if not submissions:
            return {}
        
        problems_attempted = len(set(s.problem_id for s in submissions))
        problems_passed = len(set(s.problem_id for s in submissions if (s.score or 0) >= 0.7))
        languages = list(set(s.language for s in submissions if s.language))
        
        total_test_cases = 0
        passed_test_cases = 0
        for s in submissions:
            if s.status == "Accepted":
                # Would need to query test cases per problem for exact counts
                pass
        
        return {
            "problems_attempted": problems_attempted,
            "problems_passed": problems_passed,
            "total_submissions": len(submissions),
            "languages_used": languages,
            "best_score": round(max((s.score or 0) for s in submissions) * 100, 1) if submissions else 0,
        }
    
    def _get_interview_stage_detail(self, stage: PortfolioBuilderStage) -> Dict[str, Any]:
        """Get interview stage detail."""
        if not stage.interview_session:
            return {}
        
        interview = self.db.query(InterviewSession).options(
            selectinload(InterviewSession.turns)
        ).filter(InterviewSession.id == stage.interview_session_id).first()
        
        if not interview:
            return {}
        
        turns = interview.turns or []
        scored_turns = [t for t in turns if t.final_score is not None]
        
        dimension_scores = {}
        for t in scored_turns:
            # Could aggregate by question type/topic
            pass
        
        return {
            "total_turns": len(turns),
            "scored_turns": len(scored_turns),
            "average_score": round(sum(t.final_score for t in scored_turns) / len(scored_turns) * 100, 1) if scored_turns else 0,
            "completion_reason": interview.completion_reason,
            "interview_type": interview.phase,
        }
    
    # ─────────────────────────────────────────────────────────────────
    # Consolidated Report (Stage 6)
    # ─────────────────────────────────────────────────────────────────
    
    def generate_consolidated_report(self, attempt: PortfolioBuilderAttempt) -> ConsolidatedReportResponse:
        """Generate the final consolidated competency report."""
        
        # Gather evidence from all completed stages
        completed_stages = [s for s in attempt.stages if s.status == PortfolioBuilderStageStatus.COMPLETED]
        completed_keys = [s.stage_key for s in completed_stages]
        missing_keys = [k for k in self.STAGE_KEYS if k not in completed_keys and k != PortfolioBuilderStageKey.COMPETENCY_RESULTS]
        
        # Section B: Aptitude
        aptitude_stage = self.get_stage(attempt.id, PortfolioBuilderStageKey.APTITUDE)
        aptitude_detail = self._get_mcq_stage_detail(aptitude_stage) if aptitude_stage else {}
        
        # Section C: Technical
        technical_stage = self.get_stage(attempt.id, PortfolioBuilderStageKey.TECHNICAL_MCQ)
        technical_detail = self._get_mcq_stage_detail(technical_stage) if technical_stage else {}
        
        # Section D: Combined
        combined_stage = self.get_stage(attempt.id, PortfolioBuilderStageKey.COMBINED_MCQ)
        combined_detail = self._get_mcq_stage_detail(combined_stage) if combined_stage else {}
        
        # Section E: Coding
        coding_stage = self.get_stage(attempt.id, PortfolioBuilderStageKey.DSA_CODING)
        coding_detail = self._get_coding_stage_detail(coding_stage) if coding_stage else {}
        
        # Section F: Interview
        interview_stage = self.get_stage(attempt.id, PortfolioBuilderStageKey.RESUME_INTERVIEW)
        interview_detail = self._get_interview_stage_detail(interview_stage) if interview_stage else {}
        
        # Section G: Competency Evidence Aggregation
        competency_evidence = self._aggregate_competency_evidence(attempt)
        
        # Section H: Recommendations
        recommendations = self._generate_recommendations(competency_evidence, completed_keys)
        
        # Evidence sources summary
        evidence_sources = {}
        for ce in competency_evidence:
            for src in ce.evidence_sources:
                evidence_sources[src] = evidence_sources.get(src, 0) + 1
        
        has_insufficient = any(not ce.evidence_sufficient for ce in competency_evidence)
        missing_details = []
        if PortfolioBuilderStageKey.APTITUDE not in completed_keys:
            missing_details.append("Aptitude assessment not completed")
        if PortfolioBuilderStageKey.TECHNICAL_MCQ not in completed_keys:
            missing_details.append("Technical MCQ assessment not completed")
        if PortfolioBuilderStageKey.COMBINED_MCQ not in completed_keys:
            missing_details.append("Combined assessment not completed")
        if PortfolioBuilderStageKey.DSA_CODING not in completed_keys:
            missing_details.append("Coding assessment not completed")
        if PortfolioBuilderStageKey.RESUME_INTERVIEW not in completed_keys:
            missing_details.append("Resume-based interview not completed")
        
        return ConsolidatedReportResponse(
            attempt_id=attempt.id,
            user_id=attempt.user_id,
            generated_at=datetime.utcnow(),
            overall_completion_status=attempt.overall_status,
            stages_completed=completed_keys,
            stages_missing=missing_keys,
            completion_date=attempt.completed_at,
            total_duration_minutes=self._calculate_total_duration(attempt),
            
            # Section B
            aptitude_score=aptitude_stage.score if aptitude_stage else None,
            aptitude_max_score=aptitude_stage.max_score if aptitude_stage else None,
            aptitude_topic_breakdown=aptitude_detail.get("topic_breakdown", {}),
            aptitude_correct_count=aptitude_detail.get("correct"),
            aptitude_incorrect_count=aptitude_detail.get("incorrect"),
            
            # Section C
            technical_score=technical_stage.score if technical_stage else None,
            technical_max_score=technical_stage.max_score if technical_stage else None,
            technical_subject_breakdown=technical_detail.get("topic_breakdown", {}),
            
            # Section D
            combined_score=combined_stage.score if combined_stage else None,
            combined_max_score=combined_stage.max_score if combined_stage else None,
            combined_category_breakdown=combined_detail.get("topic_breakdown", {}),
            
            # Section E
            coding_problems_attempted=coding_detail.get("problems_attempted", 0),
            coding_problems_passed=coding_detail.get("problems_passed", 0),
            coding_languages_used=coding_detail.get("languages_used", []),
            coding_competencies=self._extract_coding_competencies(coding_stage),
            
            # Section F
            interview_type=interview_detail.get("interview_type"),
            interview_overall_score=interview_detail.get("average_score"),
            interview_dimension_scores={},  # Could be enhanced with detailed analysis
            interview_competencies=self._extract_interview_competencies(interview_stage),
            
            # Section G
            competency_evidence=competency_evidence,
            
            # Section H
            recommendations=recommendations,
            
            # Metadata
            evidence_sources_summary=evidence_sources,
            has_insufficient_evidence=has_insufficient,
            missing_evidence_details=missing_details,
        )
    
    def _aggregate_competency_evidence(self, attempt: PortfolioBuilderAttempt) -> List[ConsolidatedCompetencyEvidence]:
        """
        Aggregate competency evidence from all completed stages.
        
        Uses StudentCompetency as canonical source, supplemented by
        stage-specific evidence for provenance tracking.
        """
        # Get all competencies for this user
        competencies = self.db.query(StudentCompetency).filter(
            StudentCompetency.user_id == attempt.user_id
        ).all()
        
        # Get evidence counts per skill
        evidence_counts = self.db.query(
            CompetencyEvidence.skill, func.count(CompetencyEvidence.id)
        ).filter(
            CompetencyEvidence.user_id == attempt.user_id
        ).group_by(CompetencyEvidence.skill).all()
        evidence_count_map = {skill: count for skill, count in evidence_counts}
        
        # Get assessment round IDs and interview session IDs for this attempt
        assessment_round_ids = [
            s.assessment_round_id for s in attempt.stages 
            if s.assessment_round_id is not None
        ]
        interview_session_ids = [
            s.interview_session_id for s in attempt.stages 
            if s.interview_session_id is not None
        ]
        
        # Build evidence sources per skill from CompetencyEvidence records
        skill_evidence_sources = {}
        skill_source_scores = {}
        skill_assessment_rounds = {}
        skill_interview_sessions = {}
        
        for comp in competencies:
            # Get evidence records for this skill
            evidences = self.db.query(CompetencyEvidence).filter(
                CompetencyEvidence.user_id == attempt.user_id,
                CompetencyEvidence.skill == comp.skill
            ).all()
            
            sources = set()
            source_scores = {}
            round_ids = set()
            interview_ids = set()
            
            for ev in evidences:
                sources.add(ev.source)
                source_scores[ev.source] = ev.new_score
                if ev.source in ["aptitude", "technical", "combined"] and ev.source_id:
                    round_ids.add(ev.source_id)
                elif ev.source == "interview" and ev.source_id:
                    interview_ids.add(ev.source_id)
            
            skill_evidence_sources[comp.skill] = list(sources)
            skill_source_scores[comp.skill] = source_scores
            skill_assessment_rounds[comp.skill] = list(round_ids)
            skill_interview_sessions[comp.skill] = list(interview_ids)
        
        # Also include skills from portfolio/profile that don't have competency records
        profile = ProfileService.get_or_create_student_profile(self.db, attempt.user_id)
        profile_skills = list(profile.skills_json or [])
        
        results = []
        all_skills = set([c.skill for c in competencies] + profile_skills)
        
        for skill in all_skills:
            comp = next((c for c in competencies if c.skill == skill), None)
            
            sources = skill_evidence_sources.get(skill, [])
            if comp and comp.evidence_source and comp.evidence_source not in sources:
                sources.append(comp.evidence_source)
            
            source_scores = skill_source_scores.get(skill, {})
            if comp and comp.score > 0:
                source_scores[comp.evidence_source or "unknown"] = comp.score
            
            # Determine category
            category = self._categorize_skill(skill)
            
            # Check evidence sufficiency
            evidence_count = evidence_count_map.get(skill.lower(), 0)
            evidence_sufficient = evidence_count >= 2 or (comp and comp.confidence >= 0.7)
            
            # Strengths and improvement areas
            strengths = []
            improvements = []
            if comp:
                if comp.score >= 70:
                    strengths.append(f"Strong {skill} competency (score: {comp.score:.0f})")
                elif comp.score >= 50:
                    strengths.append(f"Moderate {skill} competency (score: {comp.score:.0f})")
                else:
                    improvements.append(f"Needs improvement in {skill} (score: {comp.score:.0f})")
                
                if comp.confidence < 0.5:
                    improvements.append(f"Low confidence in {skill} assessment - more evidence needed")
            
            if not sources:
                improvements.append(f"No assessment evidence for {skill} - self-reported only")
            
            results.append(ConsolidatedCompetencyEvidence(
                competency_name=skill,
                category=category,
                evidence_sources=sources,
                source_scores=source_scores,
                aggregated_score=comp.score if comp else None,
                confidence=comp.confidence if comp else None,
                freshness=comp.freshness if comp else None,
                evidence_count=evidence_count,
                assessment_round_ids=skill_assessment_rounds.get(skill, []),
                interview_session_ids=skill_interview_sessions.get(skill, []),
                strength_areas=strengths,
                improvement_areas=improvements,
                evidence_sufficient=evidence_sufficient,
            ))
        
        # Sort by evidence_sufficient desc, then by score desc
        results.sort(key=lambda x: (not x.evidence_sufficient, -(x.aggregated_score or 0)))
        
        return results
    
    def _categorize_skill(self, skill_name: str) -> str:
        """Categorize skill (copied from portfolio.py for consistency)."""
        s = skill_name.strip().lower()
        prog_langs = {"python", "c++", "c", "java", "javascript", "typescript", "go", "rust", "ruby", "kotlin", "swift", "c#", "php"}
        dev_stack = {"react", "react.js", "next.js", "vue", "angular", "node.js", "express", "fastapi", "django", "flask", "spring", "html", "css", "tailwind", "tailwind css", "bootstrap", "rest api", "graphql"}
        aiml = {"machine learning", "deep learning", "nlp", "natural language processing", "computer vision", "tensorflow", "pytorch", "keras", "scikit-learn", "data science", "pandas", "numpy", "opencv", "llm", "rag", "transformers"}
        core_cs = {"operating systems", "os", "computer networks", "networking", "dbms", "database management systems", "sql", "postgresql", "mysql", "mongodb", "oops", "object oriented programming", "data structures", "dsa", "algorithms", "system design"}
        tools = {"git", "github", "docker", "kubernetes", "aws", "azure", "gcp", "linux", "jira", "postman", "ci/cd", "jenkins", "redis"}
        
        if s in prog_langs or any(p in s for p in ["python", "java", "c++", "javascript", "c#"]):
            return "Programming"
        if s in dev_stack or any(p in s for p in ["react", "node", "fastapi", "django", "flask", "html"]):
            return "Development"
        if s in aiml or any(p in s for p in ["learning", "nlp", "vision", "tensor", "torch"]):
            return "AI/ML"
        if s in core_cs or any(p in s for p in ["os", "network", "dbms", "sql", "oops", "data structures"]):
            return "Core CS"
        if s in tools or any(p in s for p in ["git", "docker", "aws", "linux", "postman"]):
            return "Tools"
        return "General"
    
    def _extract_coding_competencies(self, stage: Optional[PortfolioBuilderStage]) -> List[str]:
        """Extract competencies demonstrated in coding stage."""
        if not stage or not stage.assessment_round:
            return []
        
        submissions = self.db.query(CodingSubmission).filter(
            CodingSubmission.round_id == stage.assessment_round_id
        ).all()
        
        competencies = set()
        for s in submissions:
            if s.problem:
                for tag in (s.problem.tags_list or []):
                    competencies.add(tag)
        
        return list(competencies)
    
    def _extract_interview_competencies(self, stage: Optional[PortfolioBuilderStage]) -> List[str]:
        """Extract competencies demonstrated in interview stage."""
        if not stage or not stage.interview_session:
            return []
        
        interview = self.db.query(InterviewSession).options(
            selectinload(InterviewSession.turns)
        ).filter(InterviewSession.id == stage.interview_session_id).first()
        
        if not interview:
            return []
        
        competencies = set()
        for turn in (interview.turns or []):
            if turn.answer_classification:
                # Extract skills from answer classification
                pass
        
        # Could also use question analysis
        return list(competencies)
    
    def _generate_recommendations(
        self, 
        competency_evidence: List[ConsolidatedCompetencyEvidence],
        completed_keys: List[PortfolioBuilderStageKey]
    ) -> List[Dict[str, Any]]:
        """Generate actionable recommendations from competency gaps."""
        recommendations = []
        
        # Missing stage recommendations
        if PortfolioBuilderStageKey.APTITUDE not in completed_keys:
            recommendations.append({
                "type": "complete_stage",
                "priority": "high",
                "title": "Complete Aptitude Assessment",
                "description": "Finish the Aptitude & Logical Reasoning stage to establish baseline quantitative skills",
                "stage": "APTITUDE",
            })
        
        if PortfolioBuilderStageKey.TECHNICAL_MCQ not in completed_keys:
            recommendations.append({
                "type": "complete_stage",
                "priority": "high",
                "title": "Complete Technical Knowledge Assessment",
                "description": "Assess core CS fundamentals: OS, DBMS, Networks, OOP, DSA",
                "stage": "TECHNICAL_MCQ",
            })
        
        if PortfolioBuilderStageKey.DSA_CODING not in completed_keys:
            recommendations.append({
                "type": "complete_stage",
                "priority": "high",
                "title": "Complete DSA Coding Assessment",
                "description": "Demonstrate practical coding and problem-solving skills",
                "stage": "DSA_CODING",
            })
        
        if PortfolioBuilderStageKey.RESUME_INTERVIEW not in completed_keys:
            recommendations.append({
                "type": "complete_stage",
                "priority": "high",
                "title": "Complete Resume-Based Interview",
                "description": "Validate technical communication and project depth through AI interview",
                "stage": "RESUME_INTERVIEW",
            })
        
        # Competency-based recommendations
        weak_competencies = [ce for ce in competency_evidence if ce.aggregated_score is not None and ce.aggregated_score < 60]
        for ce in weak_competencies[:3]:  # Top 3 weaknesses
            recommendations.append({
                "type": "improve_competency",
                "priority": "medium",
                "title": f"Strengthen {ce.competency_name}",
                "description": f"Current score: {ce.aggregated_score:.0f}. Focus on {ce.category} fundamentals and practice.",
                "competency": ce.competency_name,
                "category": ce.category,
            })
        
        # Insufficient evidence recommendations
        insufficient = [ce for ce in competency_evidence if not ce.evidence_sufficient and ce.evidence_sources]
        for ce in insufficient[:3]:
            recommendations.append({
                "type": "gather_evidence",
                "priority": "medium",
                "title": f"Gather more evidence for {ce.competency_name}",
                "description": f"Only {ce.evidence_count} evidence records. Complete relevant assessments to strengthen profile.",
                "competency": ce.competency_name,
            })
        
        # Self-reported only skills
        self_reported = [ce for ce in competency_evidence if not ce.evidence_sources]
        for ce in self_reported[:3]:
            recommendations.append({
                "type": "validate_skill",
                "priority": "low",
                "title": f"Validate {ce.competency_name} with assessment",
                "description": "Skill is self-reported only. Complete relevant assessments to earn verified status.",
                "competency": ce.competency_name,
            })
        
        return recommendations
    
    def _calculate_total_duration(self, attempt: PortfolioBuilderAttempt) -> Optional[int]:
        """Calculate total time spent on completed stages."""
        if not attempt.started_at or not attempt.completed_at:
            return None
        return int((attempt.completed_at - attempt.started_at).total_seconds() / 60)