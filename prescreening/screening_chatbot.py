"""
prescreening/screening_chatbot.py
════════════════════════════════════════════════════════════════════
Stage 5 — AI Chatbot Pre-Screening
FastAPI application that:
  - Creates unique chatbot sessions (token-based)
  - Generates role-specific knockout questions via Claude API
  - Accepts and stores candidate answers
  - Triggers answer evaluation on session completion
"""

import asyncio
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from shared.db.database import db_session, get_db
from shared.db.models import Application, Candidate, ChatbotAnswer, ChatbotSession, Job

# ─── Env ────────────────────────────────────────────────────────────────────
load_dotenv()

CHATBOT_ENABLED = os.getenv("CHATBOT_ENABLED", "false").lower() == "true"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
COMPANY_NAME = os.getenv("COMPANY_NAME", "Our Company")
SESSION_TTL_HOURS = 48

# ─── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("screening_chatbot")

# ─── Gemini client (optional) ───────────────────────────────────────────────
gemini_model = None
if CHATBOT_ENABLED:
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel('gemini-pro')
        log.info("✅ Gemini AI chatbot enabled")
    except Exception as e:
        log.warning(f"⚠️  Failed to initialize Gemini client: {e}")
        log.info("Falling back to fixed questions mode")
        gemini_model = None
else:
    log.info("📋 Using fixed prescreening questions (CHATBOT_ENABLED=false)")

# ─── Fixed Prescreening Questions ───────────────────────────────────────────
FIXED_QUESTIONS = [
    "What motivated you to apply for this position at our company?",
    "Describe your most relevant work experience for this role.",
    "What are your key technical skills and how have you applied them?",
    "How do you handle tight deadlines and pressure in a work environment?",
    "What are your salary expectations for this position?",
    "When would you be available to start if selected?"
]

# ─── FastAPI app ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="Screening Chatbot API",
    description="AI-powered pre-screening chatbot for HR recruitment",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# PYDANTIC SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    candidate_id: str
    job_id: str


class CreateSessionResponse(BaseModel):
    session_id: str
    token: str
    expires_at: str
    chatbot_url: str


class StartSessionResponse(BaseModel):
    session_id: str
    candidate_name: str
    job_title: str
    questions: list[str]
    total_questions: int


class AnswerRequest(BaseModel):
    token: str
    question_index: int
    answer_text: str


class AnswerResponse(BaseModel):
    status: str           # 'next_question' | 'complete'
    next_question_index: int | None = None
    next_question: str | None = None
    message: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _generate_questions(job_title: str, jd_text: str) -> list[str]:
    """Generate 6 pre-screening questions - uses fixed questions or Gemini AI if enabled."""
    
    # If chatbot is disabled, return fixed questions
    if not CHATBOT_ENABLED or gemini_model is None:
        log.info("Using fixed prescreening questions")
        return FIXED_QUESTIONS
    
    # Use Gemini AI to generate custom questions
    prompt = (
        f"Generate exactly 6 pre-screening interview questions for a {job_title} position.\n"
        f"Job Description: {jd_text[:2000]}\n\n"
        f"Focus the questions on:\n"
        f"1. Motivation and interest in the role\n"
        f"2. Relevant work experience\n"
        f"3. Key technical skills\n"
        f"4. Work style and handling pressure\n"
        f"5. Salary expectations\n"
        f"6. Availability to start\n\n"
        f"Return ONLY a JSON array of 6 question strings. No explanation. No numbering. "
        f"Example: [\"Question 1?\", \"Question 2?\", ...]"
    )
    
    try:
        response = gemini_model.generate_content(prompt)
        import json
        text = response.text.strip()
        
        # Handle markdown code block wrapping
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        
        questions = json.loads(text.strip())
        log.info("Generated custom questions using Gemini AI")
        return questions[:6]  # cap at 6
        
    except Exception as exc:
        log.error("Gemini question generation failed: %s", exc)
        log.info("Falling back to fixed questions")
        return FIXED_QUESTIONS



def _get_valid_session(token: str, db: Session) -> ChatbotSession:
    """Fetch and validate a chatbot session by token."""
    session = db.query(ChatbotSession).filter_by(token=token).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session token not found.")
    if session.status == "COMPLETED":
        raise HTTPException(status_code=400, detail="This screening session is already completed.")
    if session.status == "EXPIRED" or datetime.now(timezone.utc) > session.expires_at.replace(tzinfo=timezone.utc):
        session.status = "EXPIRED"
        db.commit()
        raise HTTPException(status_code=410, detail="Session token has expired.")
    return session


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/chatbot/session", response_model=CreateSessionResponse, status_code=201)
def create_session(req: CreateSessionRequest, db: Session = Depends(get_db)):
    """
    POST /chatbot/session
    Generate a unique screening token for a candidate+job pair and persist the session.
    """
    candidate = db.query(Candidate).filter_by(id=req.candidate_id).first()
    job       = db.query(Job).filter_by(id=req.job_id).first()

    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate {req.candidate_id} not found.")
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {req.job_id} not found.")

    token      = str(uuid.uuid4())
    now        = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=SESSION_TTL_HOURS)

    session = ChatbotSession(
        candidate_id=req.candidate_id,
        job_id=req.job_id,
        token=token,
        created_at=now,
        expires_at=expires_at,
        status="PENDING",
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    screening_base = os.getenv("SCREENING_BASE_URL", "https://screening.company.com/chat")
    chatbot_url    = f"{screening_base}?token={token}"

    log.info("Created session %s for candidate %s / job %s", session.session_id, req.candidate_id, req.job_id)
    return CreateSessionResponse(
        session_id=str(session.session_id),
        token=token,
        expires_at=expires_at.isoformat(),
        chatbot_url=chatbot_url,
    )


@app.get("/chatbot/start", response_model=StartSessionResponse)
def start_session(token: str, db: Session = Depends(get_db)):
    """
    GET /chatbot/start?token={uuid}
    Validate token, generate Claude questions from the JD, return question list.
    """
    session   = _get_valid_session(token, db)
    candidate = db.query(Candidate).filter_by(id=session.candidate_id).first()
    job       = db.query(Job).filter_by(id=session.job_id).first()

    # Generate questions if not already done
    if not session.questions:
        questions = _generate_questions(job.title, job.jd_text or "")
        session.questions = questions
        session.status    = "IN_PROGRESS"
        db.commit()
    else:
        questions = session.questions

    log.info("Session %s started — %d questions generated", session.session_id, len(questions))
    return StartSessionResponse(
        session_id=str(session.session_id),
        candidate_name=candidate.name,
        job_title=job.title,
        questions=questions,
        total_questions=len(questions),
    )


@app.post("/chatbot/answer", response_model=AnswerResponse)
def submit_answer(req: AnswerRequest, db: Session = Depends(get_db)):
    """
    POST /chatbot/answer
    Accept a single answer, store it, and return next question or completion status.
    """
    session = _get_valid_session(req.token, db)

    if req.question_index < 0 or req.question_index >= len(session.questions):
        raise HTTPException(status_code=400, detail="Invalid question_index.")

    # Check if already answered
    existing = (
        db.query(ChatbotAnswer)
        .filter_by(session_id=session.session_id, question_index=req.question_index)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="This question has already been answered.")

    answer = ChatbotAnswer(
        session_id=session.session_id,
        question_index=req.question_index,
        question=session.questions[req.question_index],
        answer=req.answer_text,
        answered_at=datetime.now(timezone.utc),
    )
    db.add(answer)
    db.commit()

    total   = len(session.questions)
    next_idx = req.question_index + 1

    if next_idx >= total:
        # ── All answered: mark COMPLETED and trigger evaluation ──────────────
        session.status = "COMPLETED"
        db.commit()
        log.info("Session %s COMPLETED — triggering evaluation", session.session_id)

        # Trigger evaluation asynchronously (import here to avoid circular imports)
        import threading
        from prescreening.answer_evaluator import evaluate_session
        threading.Thread(
            target=evaluate_session,
            args=(str(session.session_id),),
            daemon=True,
        ).start()

        return AnswerResponse(
            status="complete",
            message="Thank you! Your responses have been submitted. We'll be in touch soon. 🎉",
        )

    return AnswerResponse(
        status="next_question",
        next_question_index=next_idx,
        next_question=session.questions[next_idx],
    )


@app.get("/chatbot/health")
def health():
    return {"status": "ok", "service": "screening_chatbot"}


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("prescreening.screening_chatbot:app", host="0.0.0.0", port=8001, reload=True)
