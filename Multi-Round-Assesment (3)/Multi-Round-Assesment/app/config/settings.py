"""
Application configuration loaded from environment variables.

Uses Pydantic BaseSettings to provide validated, typed access to all
configuration values required by the platform.
"""

from typing import List
from pathlib import Path


from pydantic_settings import BaseSettings


BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Central configuration for the AI Placement Platform.

    All values can be overridden via environment variables or a ``.env`` file
    located at the project root.
    """

    # ── Database ──────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql://postgres:password@localhost/ai_placement_platform"


    # ── JWT / Auth ────────────────────────────────────────────────────
    # CRITICAL: Secure random key generated - DO NOT share or commit to public repos
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120  # 2 hours for long interviews

    # ── CORS ──────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173", "http://localhost:5174", "http://localhost:5175"]
    # ── Interview Round (Groq, Sarvam, Redis) ─────────────────────────
    GROQ_API_KEY: str = ""
    SARVAM_API_KEY: str = ""
    REDIS_URL: str = "redis://localhost:6379"
    model_config = {
        "env_file" : BASE_DIR / ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }


settings = Settings()
