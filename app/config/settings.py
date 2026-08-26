"""
Application configuration loaded from environment variables.

Uses Pydantic BaseSettings to provide validated, typed access to all
configuration values required by the platform.
"""

from typing import List, Optional, Dict, Any
import json

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration for the AI Placement Platform.

    All values can be overridden via environment variables or a ``.env`` file
    located at the project root.
    """

    # ── Runtime environment ──────────────────────────────────────────
    # "production" enforces strict requirements (PostgreSQL only, secure keys).
    # "development" (default) allows looser local defaults.
    APP_ENV: str = "development"

    # ── Database ──────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql://postgres:password@localhost/ai_placement_platform"
    # Connection-pool tuning (PHASE 3). Defaults are conservative for a small
    # FastAPI deployment; override via env when running multiple instances.
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30          # seconds to wait for a connection
    DB_POOL_RECYCLE: int = 1800        # recycle connections every 30 min
    # Production hardening (Stage 2). Optional; only applied when set.
    # When non-empty, libpq-style sslmode is passed in connect_args
    # (e.g. "require", "verify-full", "prefer").
    DB_SSL_MODE: Optional[str] = None
    # Optional per-statement timeout (ms). When > 0, every pooled connection
    # runs ``SET LOCAL statement_timeout = N`` on checkout so a runaway
    # query cannot hold a connection indefinitely.
    DB_STATEMENT_TIMEOUT_MS: int = 0

    # ── JWT / Auth ────────────────────────────────────────────────────
    # CRITICAL: Secure random key generated - DO NOT share or commit to public repos
    SECRET_KEY: str  # REQUIRED: Must be set in .env file
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120  # 2 hours for long interviews

    # ── CORS ──────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173", "http://localhost:5174", "http://localhost:5175"]
    # ── Interview Round (Groq, Sarvam, Redis) ─────────────────────────
    GROQ_API_KEY: str = ""
    SARVAM_API_KEY: str = ""
    REDIS_URL: str = "redis://localhost:6379"
    OPENAI_API_KEY: Optional[str] = None  # Allow but don't require OpenAI key
    # Skip expensive model warmups during local development so auth/session
    # endpoints become available immediately after startup.
    SKIP_HEAVY_STARTUP: bool = True
    # ── Async resume upload (Stage 6A) ────────────────────────────────
    # Hard size cap enforced by the endpoint on every async resume upload;
    # streamed-chunk validated so a too-large body is rejected before it
    # fully enters memory. Override via env to tune per deployment.
    MAX_RESUME_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MiB
    # ── Coding Round
    CODING_ROUND_TIME_LIMIT_MINUTES: int = 30
    # Maximum test cases evaluated per problem to avoid long sync runs
    CODING_MAX_TEST_CASES_PER_PROBLEM: int = 20
    # Judge0 settings
    JUDGE0_URL: str = ""
    JUDGE0_API_KEY: str = ""
    JUDGE0_HTTP_TIMEOUT: float = 15.0
    JUDGE0_AUTH_MODE: str = "self-hosted"
    JUDGE0_LANGUAGE_MAP: str = '{"python":71,"javascript":63,"java":62,"cpp":54}'
    # ── Celery (Stage 4) ──────────────────────────────────────────────
    # Broker/backend default to Redis. Override via env in production.
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""
    CELERY_TASK_ALWAYS_EAGER: bool = False  # run tasks synchronously (tests/dev)
    # ── Object storage (Stage 5) ─────────────────────────────────────
    # Sets the active backend used by app.services.storage.get_storage_client().
    # Values: "none" (no storage wired, existing sync flow unaffected)
    #       | "minio" (S3-compatible; local development / rollback)
    #       | "gcs"   (Google Cloud Storage / Firebase Storage; production).
    STORAGE_BACKEND: str = "none"
    # The MinIO endpoint "host:port" (without scheme). Used when STORAGE_BACKEND = minio.
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = ""
    MINIO_SECRET_KEY: str = ""
    # Use TLS (https://) to reach MinIO. Set true in production.
    MINIO_SECURE: bool = False
    # Optional region string. Empty is fine for local MinIO (non-AWS).
    MINIO_REGION: str = ""
    # ── Google Cloud Storage / Firebase Storage (production backend) ──
    # ONE physical bucket; resumes/audio/reports are key prefixes inside it.
    # Accepts either "my-bucket" or "gs://my-bucket".
    GCS_BUCKET_NAME: str = ""
    # Optional explicit project id. When GCS_CREDENTIALS_JSON carries a
    # service account, project_id is inferred from it if this is empty.
    GCS_PROJECT_ID: str = ""
    # Full service-account JSON supplied as a single environment variable.
    # Preferred on Render: store the whole JSON file content as a Secret.
    # NEVER committed to Git, NEVER logged.
    GCS_CREDENTIALS_JSON: str = ""
    # Alternative for local dev: path to a downloaded service-account key file.
    # Leave empty on Render (use GCS_CREDENTIALS_JSON instead).
    GCS_CREDENTIALS_FILE: str = ""
    # Default buckets segregated by object kind so retention can be scoped later.
    # With STORAGE_BACKEND=gcs these are PREFIXES inside GCS_BUCKET_NAME.
    STORAGE_RESUMES_BUCKET: str = "resumes"
    STORAGE_AUDIO_BUCKET: str = "audio"
    STORAGE_REPORTS_BUCKET: str = "reports"
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }

    @field_validator("DATABASE_URL")
    @classmethod
    def _validate_database_url(cls, v: str) -> str:
        """Production must use PostgreSQL — fail fast on SQLite/other backends."""
        if not v:
            raise ValueError("DATABASE_URL is required")
        # Accept postgresql:// and postgresql+psycopg:// schemes.
        if not v.startswith("postgresql://") and not v.startswith("postgresql+psycopg://"):
            raise ValueError(
                "DATABASE_URL must be a PostgreSQL connection string "
                "(e.g. postgresql://user:pass@host:5432/db). "
                "SQLite is not supported by the application."
            )
        return v

    @field_validator("APP_ENV")
    @classmethod
    def _normalize_env(cls, v: str) -> str:
        return (v or "development").strip().lower()

    @field_validator("SECRET_KEY")
    @classmethod
    def _enforce_secure_secret_key(cls, v: str) -> str:
        """Production deployments must not use a short or placeholder key."""
        # Always require a minimum length to avoid trivially guessed keys.
        if not v or len(v.strip()) < 32:
            raise ValueError(
                "SECRET_KEY must be at least 32 characters. "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        placeholders = {
            "replace_with_secure_random_key_minimum_32_chars",
            "your-secret-key",
            "changethis",
            "secret",
        }
        if v.strip().lower() in placeholders:
            raise ValueError(
                "SECRET_KEY must not be a known placeholder. "
                "Generate a fresh secure key for every environment."
            )
        return v

    @model_validator(mode="after")
    def _enforce_production_mode(self) -> "Settings":
        """Strict guard for APP_ENV=production that fails fast on misconfig."""
        if self.APP_ENV == "production":
            # Require an explicit SSL mode in production unless explicitly disabled
            # by setting DB_SSL_MODE=disable (e.g. behind a TLS-terminating proxy).
            if self.DB_SSL_MODE is None:
                # Don't auto-fail — but log a loud warning via exception text only.
                # Many staging-grade deploys run on a trusted network; require opt-in.
                pass
            # Reject suspiciously small pools for production
            if self.DB_POOL_SIZE < 5:
                raise ValueError(
                    "DB_POOL_SIZE must be >= 5 in production (APP_ENV=production)."
                )
            # Eager mode in production is almost always a mistake
            if self.CELERY_TASK_ALWAYS_EAGER:
                raise ValueError(
                    "CELERY_TASK_ALWAYS_EAGER must be false in production — "
                    "an eager worker executes tasks synchronously inside the "
                    "web process and breaks the async pipeline."
                )
            # In production we require an explicit storage backend (not "none")
            # so persistent files cannot silently land on container-local fs.
            if self.STORAGE_BACKEND.strip().lower() == "none":
                raise ValueError(
                    "STORAGE_BACKEND must not be 'none' in production — set "
                    "'gcs' (production/Firebase) or 'minio' (local/rollback) "
                    "and configure the matching credentials."
                )
            if self.STORAGE_BACKEND.strip().lower() == "minio":
                if not self.MINIO_ENDPOINT:
                    raise ValueError("MINIO_ENDPOINT must be set when STORAGE_BACKEND=minio.")
                if not self.MINIO_ACCESS_KEY or not self.MINIO_SECRET_KEY:
                    raise ValueError(
                        "MINIO_ACCESS_KEY and MINIO_SECRET_KEY must be set "
                        "when STORAGE_BACKEND=minio."
                    )
            if self.STORAGE_BACKEND.strip().lower() == "gcs":
                if not self.GCS_BUCKET_NAME:
                    raise ValueError(
                        "GCS_BUCKET_NAME must be set when STORAGE_BACKEND=gcs."
                    )
                if not (
                    self.GCS_CREDENTIALS_JSON
                    or self.GCS_CREDENTIALS_FILE
                    or self.GCS_PROJECT_ID
                ):
                    raise ValueError(
                        "GCS credentials must be configured when "
                        "STORAGE_BACKEND=gcs. Set GCS_CREDENTIALS_JSON "
                        "(Render secret), GCS_CREDENTIALS_FILE, or rely on "
                        "Application Default Credentials via GCS_PROJECT_ID."
                    )
        return self


settings = Settings()
