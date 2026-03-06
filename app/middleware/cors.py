"""
CORS middleware configuration.

Extracts CORS setup from ``main.py`` so it can be managed independently
and swapped or extended without touching the application entry point.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import settings


def add_cors_middleware(app: FastAPI) -> None:
    """Register the CORS middleware on *app* using allowed origins from settings."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
