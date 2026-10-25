"""
Tests for Portfolio Builder Service - Core Logic Validation
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.orm import Session

from app.models.portfolio_builder import (
    PortfolioBuilderAttempt,
    PortfolioBuilderStage,
    PortfolioBuilderStageKey,
    PortfolioBuilderStageStatus,
    PortfolioBuilderAttemptStatus,
)
from app.services.portfolio_builder_service import PortfolioBuilderService
from app.schemas.portfolio_builder import (
    STAGE_ORDER,
    STAGE_DISPLAY,
    PortfolioBuilderStageKey,
)


class TestPortfolioBuilderService:
    """Test the PortfolioBuilderService core logic."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.db = Mock(spec=Session)
        self.service = PortfolioBuilderService(self.db)
        self.user_id = 1
    
    def test_stage_order_correct(self):
        """Verify the 6 stages are in correct mandatory order."""
        expected = [
            PortfolioBuilderStageKey.APTITUDE,
            PortfolioBuilderStageKey.TECHNICAL_MCQ,
            PortfolioBuilderStageKey.COMBINED_MCQ,
            PortfolioBuilderStageKey.DSA_CODING,
            PortfolioBuilderStageKey.RESUME_INTERVIEW,
            PortfolioBuilderStageKey.COMPETENCY_RESULTS,
        ]
        assert STAGE_ORDER == expected
    
    def test_stage_display_info_complete(self):
        """Verify all stages have display metadata."""
        for stage_key in STAGE_ORDER:
            assert stage_key in STAGE_DISPLAY
            display = STAGE_DISPLAY[stage_key]
            assert "number" in display
            assert "title" in display
            assert "description" in display
            assert "duration_minutes" in display
            assert display["number"] == STAGE_ORDER.index(stage_key) + 1
    
    def test_validate_stage_eligibility_first_stage_available(self):
        """First stage (APTITUDE) should be available for new attempt."""
        attempt = Mock(spec=PortfolioBuilderAttempt)
        attempt.id = 1
        attempt.current_stage = PortfolioBuilderStageKey.APTITUDE
        attempt.stages = []
        
        # Mock get_stage to return a stage with AVAILABLE status
        stage = Mock(spec=PortfolioBuilderStage)
        stage.status = PortfolioBuilderStageStatus.AVAILABLE
        stage.stage_key = PortfolioBuilderStageKey.APTITUDE
        
        self.service.get_stage = Mock(return_value=stage)
        
        eligible, error = self.service.validate_stage_eligibility(attempt, PortfolioBuilderStageKey.APTITUDE)
        assert eligible is True
        assert error is None
    
    def test_validate_stage_eligibility_locked_stage_rejected(self):
        """Locked stages should be rejected."""
        attempt = Mock(spec=PortfolioBuilderAttempt)
        attempt.id = 1
        attempt.current_stage = PortfolioBuilderStageKey.APTITUDE
        
        stage = Mock(spec=PortfolioBuilderStage)
        stage.status = PortfolioBuilderStageStatus.LOCKED
        stage.stage_key = PortfolioBuilderStageKey.TECHNICAL_MCQ
        
        self.service.get_stage = Mock(return_value=stage)
        
        eligible, error = self.service.validate_stage_eligibility(attempt, PortfolioBuilderStageKey.TECHNICAL_MCQ)
        assert eligible is False
        assert "locked" in error.lower()
    
    def test_validate_stage_eligibility_completed_stage_rejected(self):
        """Already completed stages should be rejected for restart."""
        attempt = Mock(spec=PortfolioBuilderAttempt)
        attempt.id = 1
        attempt.current_stage = PortfolioBuilderStageKey.TECHNICAL_MCQ
        
        stage = Mock(spec=PortfolioBuilderStage)
        stage.status = PortfolioBuilderStageStatus.COMPLETED
        stage.stage_key = PortfolioBuilderStageKey.APTITUDE
        
        self.service.get_stage = Mock(return_value=stage)
        
        eligible, error = self.service.validate_stage_eligibility(attempt, PortfolioBuilderStageKey.APTITUDE)
        assert eligible is False
        assert "already completed" in error.lower()
    
    def test_validate_stage_eligibility_wrong_order_rejected(self):
        """Skipping stages should be rejected."""
        attempt = Mock(spec=PortfolioBuilderAttempt)
        attempt.id = 1
        attempt.current_stage = PortfolioBuilderStageKey.APTITUDE
        
        stage = Mock(spec=PortfolioBuilderStage)
        stage.status = PortfolioBuilderStageStatus.LOCKED
        stage.stage_key = PortfolioBuilderStageKey.COMBINED_MCQ
        
        self.service.get_stage = Mock(return_value=stage)
        
        eligible, error = self.service.validate_stage_eligibility(attempt, PortfolioBuilderStageKey.COMBINED_MCQ)
        assert eligible is False
        assert "locked" in error.lower() or "prerequisite" in error.lower()
    
    def test_validate_stage_eligibility_prerequisites_not_met(self):
        """Stage should be rejected if prerequisites not completed."""
        attempt = Mock(spec=PortfolioBuilderAttempt)
        attempt.id = 1
        attempt.current_stage = PortfolioBuilderStageKey.TECHNICAL_MCQ
        
        # Mock get_stage for current stage (available)
        current_stage = Mock(spec=PortfolioBuilderStage)
        current_stage.status = PortfolioBuilderStageStatus.AVAILABLE
        current_stage.stage_key = PortfolioBuilderStageKey.TECHNICAL_MCQ
        
        # Mock get_stage for prerequisite (aptitude) - NOT completed
        prereq_stage = Mock(spec=PortfolioBuilderStage)
        prereq_stage.status = PortfolioBuilderStageStatus.AVAILABLE  # Not completed!
        prereq_stage.stage_key = PortfolioBuilderStageKey.APTITUDE
        
        def get_stage_side_effect(attempt_id, stage_key):
            if stage_key == PortfolioBuilderStageKey.TECHNICAL_MCQ:
                return current_stage
            elif stage_key == PortfolioBuilderStageKey.APTITUDE:
                return prereq_stage
            return None
        
        self.service.get_stage = Mock(side_effect=get_stage_side_effect)
        
        eligible, error = self.service.validate_stage_eligibility(attempt, PortfolioBuilderStageKey.TECHNICAL_MCQ)
        assert eligible is False
        assert "prerequisite" in error.lower()
    
    def test_get_next_stage_key(self):
        """Test next stage key progression."""
        assert self.service._get_next_stage_key(PortfolioBuilderStageKey.APTITUDE) == PortfolioBuilderStageKey.TECHNICAL_MCQ
        assert self.service._get_next_stage_key(PortfolioBuilderStageKey.TECHNICAL_MCQ) == PortfolioBuilderStageKey.COMBINED_MCQ
        assert self.service._get_next_stage_key(PortfolioBuilderStageKey.COMBINED_MCQ) == PortfolioBuilderStageKey.DSA_CODING
        assert self.service._get_next_stage_key(PortfolioBuilderStageKey.DSA_CODING) == PortfolioBuilderStageKey.RESUME_INTERVIEW
        assert self.service._get_next_stage_key(PortfolioBuilderStageKey.RESUME_INTERVIEW) == PortfolioBuilderStageKey.COMPETENCY_RESULTS
        assert self.service._get_next_stage_key(PortfolioBuilderStageKey.COMPETENCY_RESULTS) is None
    
    def test_get_stage_redirect_urls(self):
        """Test redirect URLs for each stage."""
        urls = {
            PortfolioBuilderStageKey.APTITUDE: "/portfolio-builder/stage/aptitude",
            PortfolioBuilderStageKey.TECHNICAL_MCQ: "/portfolio-builder/stage/technical-mcq",
            PortfolioBuilderStageKey.COMBINED_MCQ: "/portfolio-builder/stage/combined-mcq",
            PortfolioBuilderStageKey.DSA_CODING: "/portfolio-builder/stage/dsa-coding",
            PortfolioBuilderStageKey.RESUME_INTERVIEW: "/portfolio-builder/stage/resume-interview",
            PortfolioBuilderStageKey.COMPETENCY_RESULTS: "/portfolio-builder/results",
        }
        for stage_key, expected_url in urls.items():
            assert self.service._get_stage_redirect_url(stage_key) == expected_url
    
    def test_categorize_skill(self):
        """Test skill categorization."""
        assert self.service._categorize_skill("Python") == "Programming"
        assert self.service._categorize_skill("React") == "Development"
        assert self.service._categorize_skill("Machine Learning") == "AI/ML"
        assert self.service._categorize_skill("Operating Systems") == "Core CS"
        assert self.service._categorize_skill("Docker") == "Tools"
        assert self.service._categorize_skill("UnknownSkill") == "General"
    
    def test_question_counts(self):
        """Test stage question counts."""
        counts = {
            PortfolioBuilderStageKey.APTITUDE: 20,
            PortfolioBuilderStageKey.TECHNICAL_MCQ: 20,
            PortfolioBuilderStageKey.COMBINED_MCQ: 30,
            PortfolioBuilderStageKey.DSA_CODING: 3,
            PortfolioBuilderStageKey.RESUME_INTERVIEW: 10,
            PortfolioBuilderStageKey.COMPETENCY_RESULTS: 0,
        }
        for stage_key, expected_count in counts.items():
            assert self.service._get_stage_question_count(stage_key) == expected_count


class TestPortfolioBuilderSchemas:
    """Test Pydantic schemas for Portfolio Builder."""
    
    def test_stage_key_enum_values(self):
        """Test that all stage keys are valid enum values."""
        keys = [k.value for k in PortfolioBuilderStageKey]
        expected = ["APTITUDE", "TECHNICAL_MCQ", "COMBINED_MCQ", "DSA_CODING", "RESUME_INTERVIEW", "COMPETENCY_RESULTS"]
        assert keys == expected
    
    def test_stage_status_enum_values(self):
        """Test stage status enum."""
        statuses = [s.value for s in PortfolioBuilderStageStatus]
        expected = ["LOCKED", "AVAILABLE", "IN_PROGRESS", "COMPLETED", "FAILED"]
        assert statuses == expected
    
    def test_attempt_status_enum_values(self):
        """Test attempt status enum."""
        statuses = [s.value for s in PortfolioBuilderAttemptStatus]
        expected = ["ACTIVE", "COMPLETED", "EXPIRED", "ABANDONED"]
        assert statuses == expected


if __name__ == "__main__":
    pytest.main([__file__, "-v"])