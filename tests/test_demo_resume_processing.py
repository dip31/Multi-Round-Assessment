"""
Tests for demo mode resume processing (SyncResumeProcessor).
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from sqlalchemy.orm import Session

from app.models.resume_processing import ResumeProcessingJob
from app.services.resume_strategy import SyncResumeProcessor, get_resume_processing_strategy
from app.services.resume_processor import ResumeProcessor, ResumeProcessingError
from app.services.groq_service import GroqService


class TestSyncResumeProcessor:
    """Test SyncResumeProcessor for demo mode."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return Mock(spec=Session)

    @pytest.fixture
    def mock_groq(self):
        """Create a mock GroqService."""
        groq = Mock(spec=GroqService)
        groq.generate_question_pool.return_value = [
            {"id": "q1", "question": "Test question 1", "role": "SDE", "difficulty": "MEDIUM"},
            {"id": "q2", "question": "Test question 2", "role": "SDE", "difficulty": "MEDIUM"},
        ]
        return groq

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
        """Create a SyncResumeProcessor instance."""
        return SyncResumeProcessor(mock_db, mock_groq)

    def test_strategy_name(self, processor):
        """Test strategy name."""
        assert processor.get_strategy_name() == "sync"

    def test_process_success(self, processor, mock_db, mock_job):
        """Test successful resume processing."""
        with patch('app.services.resume_strategy.get_storage_client') as mock_get_storage:
            mock_storage = Mock()
            mock_storage.get.return_value = b"PDF content"
            mock_get_storage.return_value = mock_storage
            
            # Mock the ResumeProcessor.process_resume_bytes to return a result
            with patch.object(processor.processor, 'process_resume_bytes') as mock_process:
                from app.services.resume_processor import ProcessingResult
                mock_process.return_value = ProcessingResult(
                    job_id=1,
                    pool_id=42,
                    detected_role="SDE",
                    question_count=2,
                )
                
                result = processor.process(mock_job, b"PDF content")
                
                assert result.status == "completed"
                assert result.pool_id == 42
                mock_storage.put.assert_called_once()
                mock_storage.get.assert_called_once()
                mock_storage.delete.assert_called_once()

    def test_process_parsing_failure(self, processor, mock_db, mock_job):
        """Test handling of parsing failure."""
        with patch('app.services.resume_strategy.get_storage_client') as mock_get_storage:
            mock_storage = Mock()
            mock_storage.get.return_value = b"PDF content"
            mock_get_storage.return_value = mock_storage
            
            with patch.object(processor.processor, 'process_resume_bytes') as mock_process:
                mock_process.side_effect = ResumeProcessingError(
                    "We couldn't read your resume.",
                    error_type="unparsable"
                )
                
                result = processor.process(mock_job, b"PDF content")
                
                assert result.status == "failed"
                assert "couldn't read" in result.error_message.lower()
                mock_storage.delete.assert_called_once()

    def test_process_groq_failure(self, processor, mock_db, mock_job):
        """Test handling of Groq API failure."""
        with patch('app.services.resume_strategy.get_storage_client') as mock_get_storage:
            mock_storage = Mock()
            mock_storage.get.return_value = b"PDF content"
            mock_get_storage.return_value = mock_storage
            
            with patch.object(processor.processor, 'process_resume_bytes') as mock_process:
                mock_process.side_effect = ResumeProcessingError(
                    "We couldn't analyze your resume.",
                    error_type="pipeline"
                )
                
                result = processor.process(mock_job, b"PDF content")
                
                assert result.status == "failed"
                mock_storage.delete.assert_called_once()

    def test_process_db_failure(self, processor, mock_db, mock_job):
        """Test handling of database failure."""
        with patch('app.services.resume_strategy.get_storage_client') as mock_get_storage:
            mock_storage = Mock()
            mock_storage.get.return_value = b"PDF content"
            mock_get_storage.return_value = mock_storage
            
            with patch.object(processor.processor, 'process_resume_bytes') as mock_process:
                mock_process.side_effect = ResumeProcessingError(
                    "Backend services are temporarily unavailable.",
                    error_type="db_transient"
                )
                
                result = processor.process(mock_job, b"PDF content")
                
                assert result.status == "failed"
                mock_storage.delete.assert_called_once()

    def test_process_unexpected_exception(self, processor, mock_db, mock_job):
        """Test handling of unexpected exception."""
        with patch('app.services.resume_strategy.get_storage_client') as mock_get_storage:
            mock_storage = Mock()
            mock_storage.get.return_value = b"PDF content"
            mock_get_storage.return_value = mock_storage
            
            with patch.object(processor.processor, 'process_resume_bytes') as mock_process:
                mock_process.side_effect = Exception("Unexpected error")
                
                result = processor.process(mock_job, b"PDF content")
                
                assert result.status == "failed"
                mock_storage.delete.assert_called_once()

    def test_temp_file_cleaned_on_success(self, processor, mock_db, mock_job):
        """Test that temp file is cleaned up on success."""
        with patch('app.services.resume_strategy.get_storage_client') as mock_get_storage:
            mock_storage = Mock()
            mock_storage.get.return_value = b"PDF content"
            mock_get_storage.return_value = mock_storage
            
            with patch.object(processor.processor, 'process_resume_bytes') as mock_process:
                from app.services.resume_processor import ProcessingResult
                mock_process.return_value = ProcessingResult(
                    job_id=1,
                    pool_id=42,
                    detected_role="SDE",
                    question_count=2,
                )
                
                processor.process(mock_job, b"PDF content")
                
                # Verify delete was called with temp key pattern
                mock_storage.delete.assert_called_once()
                call_args = mock_storage.delete.call_args
                assert call_args[0][0] == "resumes"
                assert call_args[0][1].startswith("temp_1_")

    def test_temp_file_cleaned_on_failure(self, processor, mock_db, mock_job):
        """Test that temp file is cleaned up on failure."""
        with patch('app.services.resume_strategy.get_storage_client') as mock_get_storage:
            mock_storage = Mock()
            mock_storage.get.return_value = b"PDF content"
            mock_get_storage.return_value = mock_storage
            
            with patch.object(processor.processor, 'process_resume_bytes') as mock_process:
                mock_process.side_effect = ResumeProcessingError("Failed", "unparsable")
                
                processor.process(mock_job, b"PDF content")
                
                # Verify delete was called even on failure
                mock_storage.delete.assert_called_once()

    def test_no_celery_delay_called(self, processor, mock_db, mock_job):
        """Test that Celery delay is NOT called in demo mode."""
        with patch('app.services.resume_strategy.get_storage_client') as mock_get_storage:
            mock_storage = Mock()
            mock_storage.get.return_value = b"PDF content"
            mock_get_storage.return_value = mock_storage
            
            with patch.object(processor.processor, 'process_resume_bytes') as mock_process:
                from app.services.resume_processor import ProcessingResult
                mock_process.return_value = ProcessingResult(
                    job_id=1,
                    pool_id=42,
                    detected_role="SDE",
                    question_count=2,
                )
                
                with patch('app.worker.tasks.process_resume_job') as mock_celery:
                    processor.process(mock_job, b"PDF content")
                    mock_celery.delay.assert_not_called()


class TestStrategyFactory:
    """Test get_resume_processing_strategy factory."""

    def test_demo_returns_sync_processor(self, monkeypatch):
        """Factory should return SyncResumeProcessor for demo mode."""
        monkeypatch.setenv("DEPLOYMENT_MODE", "demo")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
        
        import importlib
        from app.config import settings as settings_module
        importlib.reload(settings_module)
        
        from app.services.resume_strategy import get_resume_processing_strategy
        from app.services.groq_service import GroqService
        
        mock_db = Mock(spec=Session)
        mock_groq = Mock(spec=GroqService)
        
        strategy = get_resume_processing_strategy(mock_db, mock_groq)
        assert isinstance(strategy, SyncResumeProcessor)

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