"""
FastAPI application entry point.

Creates the app instance, registers middleware from the middleware layer,
and mounts the versioned API router.  Run with::

    uvicorn app.main:app --reload
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.middleware.cors import add_cors_middleware
from app.middleware.rate_limit import add_rate_limit_middleware
from app.middleware.request_logging import add_request_logging_middleware
from app.modules.interview.routers import interview_router

logger = logging.getLogger(__name__)

# Configure RAG logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/rag_pipeline.log"),
        logging.StreamHandler()
    ]
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm up embedding model at startup
    # Prevents 30s delay on first resume upload
    try:
        from app.services.embedding_service import (
            get_embedding_model
        )
        get_embedding_model()
        print("[Startup] Embedding model ready")
    except Exception as e:
        print(f"[Startup] Embedding warmup failed: {e}")

    # Warm up FAISS index at startup
    try:
        from app.services.retriever_service import load_kb
        load_kb()
        print("[Startup] KB index ready")
    except Exception as e:
        print(f"[Startup] KB index load failed: {e}")
        print("[Startup] Run: python scripts/build_kb_index.py")

    yield


app = FastAPI(
    title="AI Placement Platform API",
    description=(
        "Backend for the AI-Driven Multi-Round Assessment Platform. "
        "Supports aptitude, coding, and interview rounds with "
        "RL-driven difficulty adaptation and proctoring."
    ),
    version="0.1.0",
    lifespan=lifespan,
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
