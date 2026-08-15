"""
Application configuration loaded from environment variables.

Uses Pydantic BaseSettings to provide validated, typed access to all
configuration values required by the platform.
"""

from typing import List, Optional, Dict, Any
import json

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration for the AI Placement Platform.

    All values can be overridden via environment variables or a ``.env`` file
    located at the project root.
    """

    # ── Database ──────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql://postgres:password@localhost/ai_placement_platform"

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
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


settings = Settings()
