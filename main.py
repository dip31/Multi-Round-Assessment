"""
AI Recruitment Multi-Agent System — Main Application
FastAPI entry point that wires all agents together.
"""
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from shared.db.database import init_db, generate_id
from shared.queue.event_bus import event_bus

# Import agent routers
from intake.job_requisition_api import router as job_requisition_router
from intake.job_poster import router as job_poster_router
from sourcing.resume_collector import router as resume_collector_router
from sourcing.profile_parser import router as profile_parser_router
from sourcing.candidate_form import router as candidate_form_router
from screening.screening_api import router as screening_router
from outreach.outreach_api import router as outreach_router
from prescreening.prescreening_api import router as prescreening_router

# Stage 6 & 7 routers
try:
    # Temporarily disabled to avoid NLTK issues
    # from interview.routers.interview_router import router as interview_router
    # from interview.routers.auth_bypass import router as auth_bypass_router
    # from evaluation.routers.session_router import router as evaluation_router
    INTERVIEW_AVAILABLE = False  # Temporarily disabled
except ImportError as e:
    print(f"⚠️ Interview/Evaluation modules not available: {e}")
    INTERVIEW_AVAILABLE = False


# Ensure the temporary interview auth bypass is available for the frontend
INTERVIEW_AUTH_BYPASS_AVAILABLE = False
interview_auth_bypass = None
try:
    from interview.routers import auth_bypass as interview_auth_bypass
    INTERVIEW_AUTH_BYPASS_AVAILABLE = True
except Exception as e:
    print(f"⚠️ Could not import interview auth bypass router: {e}")


# Stage 8, 9, 10 routers
try:
    from offer.routers.offer_router import router as offer_router
    from onboarding.routers.onboarding_router import router as onboarding_router
    from analytics.routers.analytics_router import router as analytics_router
    STAGES_8_9_10_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Offer/Onboarding/Analytics modules not available: {e}")
    STAGES_8_9_10_AVAILABLE = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database, RabbitMQ, and event subscriptions on startup."""
    await init_db()
    await event_bus.connect()
    print(f"📡 Event bus backend: {event_bus.backend}")
    
    # Start the screening shortlister
    from screening.shortlister import start_event_listener
    await start_event_listener()
    
    # Start Stage 4 & 5 event handlers
    try:
        from outreach.email_sender import process_candidate_shortlisted_event
        event_bus.subscribe("candidate.shortlisted", process_candidate_shortlisted_event)
        print("✅ Outreach email sender subscribed to candidate.shortlisted events")
    except ImportError as e:
        print(f"⚠️ Outreach module not available: {e}")
    
    try:
        from prescreening.screening_chatbot import app as chatbot_app
        print("✅ Prescreening chatbot available")
    except ImportError as e:
        print(f"⚠️ Prescreening module not available: {e}")
    
    # Start Stage 8, 9, 10 autonomous agents
    try:
        from offer.offer_agent import start_offer_agent
        from onboarding.onboarding_agent import start_onboarding_agent
        from analytics.analytics_agent import start_analytics_agent
        
        start_offer_agent()
        start_onboarding_agent()
        start_analytics_agent()
        print("✅ Stages 8, 9, 10 autonomous agents started")
    except ImportError as e:
        print(f"⚠️ Stage 8/9/10 agents not available: {e}")
    
    print("🚀 AI Recruitment System started")
    print("📊 Dashboard: http://localhost:8000")
    print("📚 API Docs:  http://localhost:8000/docs")
    yield
    await event_bus.close()
    print("👋 AI Recruitment System shutting down")


app = FastAPI(
    title="AI Recruitment Multi-Agent System",
    description="Multi-agent RPA system for automated recruitment — Resume Parsing, JD Generation, Job Posting, Candidate Intake",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register Agent Routers ─────────────────────────────
app.include_router(job_requisition_router, prefix="/api")
app.include_router(job_poster_router, prefix="/api")
app.include_router(resume_collector_router, prefix="/api")
app.include_router(profile_parser_router, prefix="/api")
app.include_router(candidate_form_router, prefix="/api")
app.include_router(screening_router, prefix="/api")
app.include_router(outreach_router, prefix="/api")
app.include_router(prescreening_router, prefix="/api")

# Stage 6 & 7 routers
if INTERVIEW_AVAILABLE:
    app.include_router(auth_bypass_router, prefix="/api")
    app.include_router(interview_router, prefix="/api")
    app.include_router(evaluation_router, prefix="/api")
    print("✅ Interview and Evaluation modules loaded")

# Stage 8, 9, 10 routers
if STAGES_8_9_10_AVAILABLE:
    app.include_router(offer_router, prefix="/api")
    app.include_router(onboarding_router, prefix="/api")
    app.include_router(analytics_router, prefix="/api")
    print("✅ Offer, Onboarding, and Analytics modules loaded")

# Mount interview auth bypass router (development helper)
if INTERVIEW_AUTH_BYPASS_AVAILABLE and interview_auth_bypass:
    try:
        app.include_router(interview_auth_bypass.router, prefix="/api")
        app.include_router(interview_auth_bypass.router, prefix="/api/v1")
        print("✅ Interview auth bypass router mounted at /api and /api/v1")
    except Exception as _e:
        print(f"⚠️ Failed to mount interview auth bypass router at runtime: {_e}")


# ── System Endpoints ──────────────────────────────────

@app.get("/api/system/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "ai-recruitment-system",
        "version": "1.0.0",
        "event_bus": event_bus.backend,
        "rabbitmq_connected": event_bus.is_connected and event_bus.backend == "rabbitmq",
    }


@app.get("/api/system/events")
async def get_events():
    """Get the event bus activity log."""
    return {"events": event_bus.get_log(limit=100)}


@app.get("/api/system/production-status")
async def get_production_status():
    """Get production readiness status and API configuration."""
    from config import (
        PRODUCTION_MODE, LINKEDIN_ACCESS_TOKEN, INDEED_API_KEY,
        GITHUB_API_TOKEN, STACKOVERFLOW_API_KEY, 
        LINKEDIN_TALENT_API_KEY, ANGELLIST_API_KEY, GROQ_API_KEY
    )
    
    job_posting_apis = {
        "linkedin": bool(LINKEDIN_ACCESS_TOKEN),
        "indeed": bool(INDEED_API_KEY),
    }
    
    candidate_sourcing_apis = {
        "github": bool(GITHUB_API_TOKEN),
        "stackoverflow": bool(STACKOVERFLOW_API_KEY),
        "linkedin_talent": bool(LINKEDIN_TALENT_API_KEY),
        "angellist": bool(ANGELLIST_API_KEY),
    }
    
    total_job_apis = sum(job_posting_apis.values())
    total_sourcing_apis = sum(candidate_sourcing_apis.values())
    
    return {
        "production_mode": PRODUCTION_MODE,
        "groq_api_configured": bool(GROQ_API_KEY),
        "job_posting": {
            "configured_apis": total_job_apis,
            "total_available": len(job_posting_apis),
            "apis": job_posting_apis,
            "ready": total_job_apis > 0
        },
        "candidate_sourcing": {
            "configured_apis": total_sourcing_apis,
            "total_available": len(candidate_sourcing_apis),
            "apis": candidate_sourcing_apis,
            "ready": total_sourcing_apis > 0
        },
        "overall_status": "production_ready" if (PRODUCTION_MODE and total_job_apis > 0 and total_sourcing_apis > 0 and GROQ_API_KEY) else "simulation_mode",
        "recommendations": [
            "Set PRODUCTION_MODE=true in .env" if not PRODUCTION_MODE else None,
            "Add GROQ_API_KEY to .env for AI features" if not GROQ_API_KEY else None,
            "Add at least one job posting API key" if total_job_apis == 0 else None,
            "Add at least one candidate sourcing API key" if total_sourcing_apis == 0 else None,
        ]
    }


@app.get("/api/system/agents")
async def list_agents():
    """List all registered AI agents and their status."""
    return {
        "agents": [
            {
                "name": "Job Requisition Agent",
                "module": "intake.job_requisition_api",
                "stage": 1,
                "status": "active",
                "description": "Creates and manages job requisitions",
            },
            {
                "name": "JD Generator Agent",
                "module": "intake.jd_generator",
                "stage": 1,
                "status": "active",
                "description": "Generates job descriptions using Groq AI",
            },
            {
                "name": "Job Poster Agent",
                "module": "intake.job_poster",
                "stage": 1,
                "status": "active",
                "description": "Posts jobs to LinkedIn, Indeed, Naukri",
            },
            {
                "name": "Candidate Form Agent",
                "module": "sourcing.candidate_form",
                "stage": 2,
                "status": "active",
                "description": "Collects candidate details via form for screening pipeline",
            },
            {
                "name": "Resume Collector Agent",
                "module": "sourcing.resume_collector",
                "stage": 2,
                "status": "active",
                "description": "Accepts resume uploads (PDF/DOCX)",
            },
            {
                "name": "Profile Parser Agent",
                "module": "sourcing.profile_parser",
                "stage": 2,
                "status": "active",
                "description": "Parses resumes using LlamaIndex + Groq",
            },
            {
                "name": "Screening Engine Agent",
                "module": "screening.screening_api",
                "stage": 3,
                "status": "active",
                "description": "Scores candidates and detects duplicates",
            },
            {
                "name": "Duplicate Detector Agent",
                "module": "screening.duplicate_detector",
                "stage": 3,
                "status": "active",
                "description": "Identifies duplicate candidate profiles",
            },
            {
                "name": "Shortlister Agent",
                "module": "screening.shortlister",
                "stage": 3,
                "status": "active",
                "description": "Processes screening queue and shortlists candidates",
            },
        ]
    }


# ── Serve Frontend ────────────────────────────────────
FRONTEND_DIR = Path(__file__).parent / "frontend"


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the testing dashboard."""
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return HTMLResponse("<h1>AI Recruitment System API</h1><p>Visit <a href='/docs'>/docs</a> for API documentation</p>")


@app.get("/candidate/prescreening", response_class=HTMLResponse)
async def serve_candidate_prescreening():
    """Serve the candidate-facing prescreening interface."""
    prescreening_path = FRONTEND_DIR / "candidate-prescreening.html"
    if prescreening_path.exists():
        return FileResponse(prescreening_path)
    return HTMLResponse("<h1>Prescreening Not Available</h1>")


@app.get("/candidate/interview", response_class=HTMLResponse)
async def serve_candidate_interview():
    """Redirect to the multi-round assessment interview app."""
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>AI Interview</title>
        <meta http-equiv="refresh" content="0; url=http://localhost:5173/interview">
        <style>
            body {
                font-family: system-ui, -apple-system, sans-serif;
                display: flex;
                align-items: center;
                justify-content: center;
                height: 100vh;
                margin: 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }
            .container {
                text-align: center;
                padding: 2rem;
                background: rgba(255,255,255,0.1);
                backdrop-filter: blur(10px);
                border-radius: 20px;
                box-shadow: 0 8px 32px rgba(0,0,0,0.1);
            }
            h1 { margin: 0 0 1rem 0; }
            p { margin: 0.5rem 0; opacity: 0.9; }
            .spinner {
                width: 50px;
                height: 50px;
                border: 4px solid rgba(255,255,255,0.3);
                border-top-color: white;
                border-radius: 50%;
                animation: spin 1s linear infinite;
                margin: 2rem auto;
            }
            @keyframes spin {
                to { transform: rotate(360deg); }
            }
            .link {
                display: inline-block;
                margin-top: 1rem;
                padding: 0.75rem 1.5rem;
                background: white;
                color: #667eea;
                text-decoration: none;
                border-radius: 10px;
                font-weight: 600;
                transition: transform 0.2s;
            }
            .link:hover {
                transform: scale(1.05);
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎤 AI Interview</h1>
            <p>Redirecting to interview interface...</p>
            <div class="spinner"></div>
            <p>If not redirected automatically, click below:</p>
            <a href="http://localhost:5173/interview" class="link">
                Open Interview Interface →
            </a>
            <p style="font-size: 0.9rem; margin-top: 2rem; opacity: 0.7;">
                The interview system is running on React (port 5173)<br>
                Backend API is running on port 8000
            </p>
        </div>
    </body>
    </html>
    """)


# Mount static files for frontend assets
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


# Global exception handler for unhandled errors
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch all unhandled exceptions and return them as JSON."""
    import traceback
    error_id = generate_id()
    error_details = {
        "error_id": error_id,
        "type": exc.__class__.__name__,
        "message": str(exc),
        "path": str(request.url),
        "method": request.method,
    }
    
    # Log the full traceback for debugging
    print(f"❌ Unhandled exception [{error_id}]: {exc.__class__.__name__}")
    traceback.print_exc()
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "error_id": error_id,
            "details": error_details if True else None,  # Set to False to hide details in production
        }
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions with JSON responses."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "status_code": exc.status_code,
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
