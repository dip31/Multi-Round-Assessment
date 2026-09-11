"""
FastAPI application entry point.

Creates the app instance, registers middleware from the middleware layer,
and mounts the versioned API router.  Run with::

    uvicorn app.main:app --reload
"""

import logging
import os
from contextlib import asynccontextmanager

# Configure logging before the earliest startup checkpoint so RSS diagnostics
# are emitted even during module import.
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/rag_pipeline.log"),
        logging.StreamHandler()
    ]
)

from app.services.memory_diagnostics import log_memory

log_memory("startup: early")

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.config.settings import settings
from app.middleware.cors import add_cors_middleware
from app.middleware.rate_limit import add_rate_limit_middleware
from app.middleware.request_logging import add_request_logging_middleware

logger = logging.getLogger(__name__)
log_memory("startup: after app imports")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.SKIP_HEAVY_STARTUP:
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

        # Warm up YOLO phone detection model
        try:
            from app.services.phone_detection_service import get_yolo_model
            model = get_yolo_model()
            if model is not None:
                print("[Startup] YOLOv8n model ready")
            else:
                print("[Startup] YOLOv8n model not available")
        except Exception as e:
            print(f"[Startup] YOLO warmup failed: {e}")
    else:
        print("[Startup] Heavy model warmups skipped for fast local auth/login startup")

    log_memory("startup: after CV/YOLO initialization")
    log_memory("startup: after audio initialization")
    log_memory("startup: after RAG initialization")
    log_memory("startup: after embedding initialization")

    # Stage 3 / Stage 4: orchestrate shared infra health in one place.
    # Redis is required by Celery broker/backend (Stage 4) but optional for the
    # request path (cache-only). Log status; never fail startup so the existing
    # assessment flow keeps working even if Redis is briefly unavailable.
    try:
        from app.services.redis_client import get_redis_client, redis_available
        get_redis_client()
        print(f"[Startup] Redis: {'ready' if redis_available() else 'unavailable (continuing)'}")
    except Exception as e:
        print(f"[Startup] Redis health check failed: {e}")

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
log_memory("startup: after router initialization")
log_memory("startup: application ready")


# ── Health check ──────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
def health_check() -> dict:
    """Simple liveness probe."""
    return {"status": "ok"}
