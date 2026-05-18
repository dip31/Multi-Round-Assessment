"""
Application configuration loaded from environment variables.

Uses Pydantic BaseSettings to provide validated, typed access to all
configuration values required by the platform.
"""

from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration for the AI Placement Platform.

    All values can be overridden via environment variables or a ``.env`` file
    located at the project root.
    """

    # ── Database ──────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql://postgres:password@localhost/ai_placement_platform"

    # ── JWT / Auth ────────────────────────────────────────────────────
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # ── CORS ──────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:4000",
        "http://192.168.56.1:3000",
        "http://192.168.56.1:4000",
    ]

    # ── Judge0 Code Execution ─────────────────────────────────────────
    JUDGE0_API_URL: str = "http://localhost:2358"
    JUDGE0_API_KEY: str = ""
    JUDGE0_MAX_POLL_ATTEMPTS: int = 30
    JUDGE0_POLL_INTERVAL_SECONDS: float = 1.0
    USE_MOCK_JUDGE0: bool = False

    # ── Coding Round Configuration ────────────────────────────────────
    CODING_ROUND_TIME_LIMIT_MINUTES: int = 90
    CODING_ROUND_PROBLEMS_COUNT: int = 3

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


settings = Settings()
