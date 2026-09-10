"""
Tests for production mode resume processing (CeleryResumeProcessor).
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.orm import Session
from datetime import datetime

from app.models.resume_processing import ResumeProcessingJob
from app.services.resume_strategy import CeleryResumeProcessor, get_resume_processing_strategy
from app.services.groq_service import GroqService


class TestCeleryResumeProcessor:
    """Test CeleryResumeProcessor for production mode."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return Mock(spec=Session)

    @pytest.fixture
    def mock_groq(self):
        """Create a mock GroqService."""
        return Mock(spec=GroqService)

    @pytest.fixture
    def mock_job(self):
        """Create a mock ResumeProcessingJob."""
        job = Mock(spec=ResumeProcessingJob)
        job.id = 1
        job.user_id = 1
        job.session_id = 1
        job.storage_key = "resumes/1/1/test.pdf"
        job.status = "PENDING"
        job.progress_step = None
        job.error_message = None
        job.retry_count = 0
        job.started_at = None
        job.completed_at = None
        job.job_metadata = {}
        return job

    @pytest.fixture
    def processor(self, mock_db, mock_groq):
        """Create a CeleryResumeProcessor instance."""
        return CeleryResumeProcessor(mock_db, mock_groq)

    def test_strategy_name(self, processor):
        """Test strategy name."""
        assert processor.get_strategy_name() == "celery"

    def test_process_enqueues_celery_task(self, processor, mock_db, mock_job):
        """Test that process enqueues Celery task."""
        with patch('app.worker.tasks.process_resume_job') as mock_task:
            mock_task.delay = Mock()
            
            result = processor.process(mock_job, b"PDF content")
            
            assert result.status == "enqueued"
            mock_task.delay.assert_called_once_with(job_id=1, storage_key="resumes/1/1/test.pdf")
            # Job should remain PENDING
            assert mock_job.status == "PENDING"

    def test_process_enqueue_failure(self, processor, mock_db, mock_job):
        """Test handling of Celery enqueue failure."""
        with patch('app.worker.tasks.process_resume_job') as mock_task:
            mock_task.delay.side_effect = Exception("Broker unreachable")
            
            result = processor.process(mock_job, b"PDF content")
            
            assert result.status == "failed"
            assert "queue" in result.error_message.lower()
            # Job should be marked FAILED
            assert mock_job.status == "FAILED"
            assert mock_job.error_message is not None
            assert mock_job.completed_at is not None
            mock_db.commit.assert_called()

    def test_process_passes_correct_job_id(self, processor, mock_db, mock_job):
        """Test that correct job_id is passed to Celery."""
        mock_job.id = 42
        mock_job.storage_key = "resumes/42/42/custom.pdf"
        
        with patch('app.worker.tasks.process_resume_job') as mock_task:
            mock_task.delay = Mock()
            
            processor.process(mock_job, b"PDF content")
            
            mock_task.delay.assert_called_once_with(job_id=42, storage_key="resumes/42/42/custom.pdf")

    def test_process_passes_correct_storage_key(self, processor, mock_db, mock_job):
        """Test that correct storage_key is passed to Celery."""
        mock_job.storage_key = "resumes/user123/session456/file.pdf"
        
        with patch('app.worker.tasks.process_resume_job') as mock_task:
            mock_task.delay = Mock()
            
            processor.process(mock_job, b"PDF content")
            
            mock_task.delay.assert_called_once_with(job_id=1, storage_key="resumes/user123/session456/file.pdf")

    def test_job_remains_pending_after_enqueue(self, processor, mock_db, mock_job):
        """Test that job status remains PENDING after successful enqueue."""
        with patch('app.worker.tasks.process_resume_job') as mock_task:
            mock_task.delay = Mock()
            
            result = processor.process(mock_job, b"PDF content")
            
            assert result.status == "enqueued"
            assert mock_job.status == "PENDING"
            assert mock_job.error_message is None


class TestProductionStrategyFactory:
    """Test factory returns CeleryResumeProcessor in production mode."""

    def test_production_returns_celery_processor(self, monkeypatch):
        """Factory should return CeleryResumeProcessor for production mode."""
        monkeypatch.setenv("DEPLOYMENT_MODE", "production")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        monkeypatch.setenv("STORAGE_BACKEND", "gcs")
        monkeypatch.setenv("GCS_BUCKET_NAME", "test-bucket")
        monkeypatch.setenv("GCS_PROJECT_ID", "test-project")
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        
        import importlib
        from app.config import settings as settings_module
        importlib.reload(settings_module)
        
        from app.services.resume_strategy import get_resume_processing_strategy, CeleryResumeProcessor
        from app.services.groq_service import GroqService
        
        mock_db = Mock(spec=Session)
        mock_groq = Mock(spec=GroqService)
        
        strategy = get_resume_processing_strategy(mock_db, mock_groq)
        assert isinstance(strategy, CeleryResumeProcessor)