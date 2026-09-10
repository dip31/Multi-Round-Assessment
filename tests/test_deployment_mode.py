"""
Tests for DEPLOYMENT_MODE configuration validation.
"""

import os
import pytest
from unittest.mock import patch, Mock
from pydantic import ValidationError


class TestDeploymentModeConfiguration:
    """Test DEPLOYMENT_MODE configuration validation."""

    def test_demo_mode_accepted(self, monkeypatch):
        """DEPLOYMENT_MODE=demo should be accepted."""
        monkeypatch.setenv("DEPLOYMENT_MODE", "demo")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
        
        # Re-import settings to pick up new env
        import importlib
        from app.config import settings as settings_module
        importlib.reload(settings_module)
        
        assert settings_module.settings.is_demo is True
        assert settings_module.settings.is_production is False
        assert settings_module.settings.celery_enabled is False
        assert settings_module.settings.resume_processing_mode == "sync"

    def test_production_mode_accepted(self, monkeypatch):
        """DEPLOYMENT_MODE=production should be accepted with required config."""
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
        
        assert settings_module.settings.is_demo is False
        assert settings_module.settings.is_production is True
        assert settings_module.settings.celery_enabled is True
        assert settings_module.settings.resume_processing_mode == "celery"

    def test_invalid_mode_rejected(self, monkeypatch):
        """Invalid DEPLOYMENT_MODE should raise ValidationError."""
        monkeypatch.setenv("DEPLOYMENT_MODE", "testing")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
        
        import importlib
        from app.config import settings as settings_module
        
        with pytest.raises(ValidationError, match="DEPLOYMENT_MODE must be one of"):
            importlib.reload(settings_module)

    def test_empty_mode_defaults_to_demo(self, monkeypatch):
        """Empty DEPLOYMENT_MODE should default to demo."""
        monkeypatch.setenv("DEPLOYMENT_MODE", "")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
        
        import importlib
        from app.config import settings as settings_module
        importlib.reload(settings_module)
        
        assert settings_module.settings.is_demo is True

    def test_case_insensitive(self, monkeypatch):
        """DEPLOYMENT_MODE should be case-insensitive."""
        monkeypatch.setenv("DEPLOYMENT_MODE", "DEMO")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
        
        import importlib
        from app.config import settings as settings_module
        importlib.reload(settings_module)
        
        assert settings_module.settings.is_demo is True

    def test_production_requires_celery_config(self, monkeypatch):
        """Production mode should require Celery broker/backend config."""
        monkeypatch.setenv("DEPLOYMENT_MODE", "production")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
        monkeypatch.setenv("STORAGE_BACKEND", "gcs")
        monkeypatch.setenv("GCS_BUCKET_NAME", "test-bucket")
        monkeypatch.setenv("GCS_PROJECT_ID", "test-project")
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        monkeypatch.setenv("REDIS_URL", "")
        monkeypatch.setenv("CELERY_BROKER_URL", "")
        monkeypatch.setenv("CELERY_RESULT_BACKEND", "")
        # Missing REDIS_URL/CELERY_BROKER_URL
        
        import importlib
        from app.config import settings as settings_module
        
        with pytest.raises(ValidationError, match="CELERY_BROKER_URL or REDIS_URL must be set"):
            importlib.reload(settings_module)

    def test_production_requires_storage_backend(self, monkeypatch):
        """Production mode should require explicit storage backend."""
        monkeypatch.setenv("DEPLOYMENT_MODE", "production")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        # Missing STORAGE_BACKEND (defaults to "none")
        
        import importlib
        from app.config import settings as settings_module
        
        with pytest.raises(ValidationError, match="STORAGE_BACKEND must not be 'none'"):
            importlib.reload(settings_module)

    def test_demo_does_not_require_celery(self, monkeypatch):
        """Demo mode should not require Celery config."""
        monkeypatch.setenv("DEPLOYMENT_MODE", "demo")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        # No Redis, no Celery config
        
        import importlib
        from app.config import settings as settings_module
        importlib.reload(settings_module)
        
        # Should not raise
        assert settings_module.settings.is_demo is True

    def test_demo_does_not_require_gcs(self, monkeypatch):
        """Demo mode should not require GCS config."""
        monkeypatch.setenv("DEPLOYMENT_MODE", "demo")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        # No GCS config
        
        import importlib
        from app.config import settings as settings_module
        importlib.reload(settings_module)
        
        # Should not raise
        assert settings_module.settings.is_demo is True

    def test_demo_resume_storage_isolation(self, monkeypatch):
        """In demo mode, resumes bucket uses LocalStorageClient, while audio/reports use configured STORAGE_BACKEND."""
        monkeypatch.setenv("DEPLOYMENT_MODE", "demo")
        monkeypatch.setenv("STORAGE_BACKEND", "minio")
        monkeypatch.setenv("MINIO_ENDPOINT", "localhost:9000")
        monkeypatch.setenv("MINIO_ACCESS_KEY", "minio")
        monkeypatch.setenv("MINIO_SECRET_KEY", "minio123")
        monkeypatch.setenv("SECRET_KEY", "a" * 32)
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")

        import importlib
        from app.config import settings as settings_module
        importlib.reload(settings_module)

        from app.services.storage.factory import get_storage_client, reset_storage_client
        from app.services.storage.local_backend import LocalStorageClient
        from app.services.storage.minio_backend import MinIOStorageClient

        reset_storage_client()
        resume_client = get_storage_client("resumes")
        assert isinstance(resume_client, LocalStorageClient)

        with patch("app.services.storage.minio_backend.MinIOStorageClient") as mock_minio_cls:
            mock_minio_cls.return_value = Mock(spec=MinIOStorageClient)
            audio_client = get_storage_client("audio")
            assert audio_client is mock_minio_cls.return_value
        reset_storage_client()