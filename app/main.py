"""
FastAPI application entry point.

Creates the app instance, registers middleware from the middleware layer,
and mounts the versioned API router.  Run with::

    uvicorn app.main:app --reload
"""

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.middleware.cors import add_cors_middleware
from app.middleware.rate_limit import add_rate_limit_middleware
from app.middleware.request_logging import add_request_logging_middleware

app = FastAPI(
    title="AI Placement Platform API",
    description=(
        "Backend for the AI-Driven Multi-Round Assessment Platform. "
        "Supports aptitude, coding, and interview rounds with "
        "RL-driven difficulty adaptation and proctoring."
    ),
    version="0.1.0",
)

# ── Middleware (order matters: last added = first executed) ────────────
add_rate_limit_middleware(app, max_requests=100, window_seconds=60)
add_request_logging_middleware(app)
add_cors_middleware(app)

# ── Routers ───────────────────────────────────────────────────────────
app.include_router(api_router)


# ── Health check ──────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
def health_check() -> dict:
    """Simple liveness probe."""
    return {"status": "ok"}
