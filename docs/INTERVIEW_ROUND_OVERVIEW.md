# IntelliHire — AI Interview Round 3: Overview

## Objective
Round 3 (AI Interview Round) assesses candidates across technical accuracy, communication, confidence, and problem solving using an adaptive AI-driven interviewer. The round is a maximum 10-question, 30-minute, resumable session delivering objective scoring, proctoring, and RL-driven difficulty adaptation to approximate live interviewer behavior.

## Where This Round Fits (in the 10-stage pipeline)
1. Application submission
2. Resume parsing
3. Automated screening (Round 1)
4. Online assessment (Round 2)
5. AI Interview Round (Round 3 — this doc)
6. Live technical interview
7. Manager interview
8. Reference checks
9. Offer decision
10. Onboarding

## Candidate User Journey (step by step)
1. Candidate clicks “Start Interview” on IntelliHire dashboard.
2. Browser opens interview UI on port 5173 and requests permissions.
3. Permission check state: webcam and microphone prompts; candidate chooses `voice` or `text`.
4. Session created via POST /api/v1/interview/start (token returned).
5. Backend initializes `interview_sessions` row (answer_mode, current_question_index=0).
6. First question fetched via GET /api/v1/interview/session/{session_id}/next-question.
7. Candidate answers via voice (Groq Whisper STT) or typed text; submits to POST /api/v1/interview/session/{session_id}/submit-answer.
8. AI evaluation (Groq LLaMA 3.1 70B) returns scores, feedback, and RL reward computed; RL Q-table updated (`rl_q_table`, `rl_attempt_log`).
9. Candidate proceeds through up to 10 questions or until completion/termination.
10. On end: POST /api/v1/interview/session/{session_id}/end triggers evaluation, writes `interview_evaluation`, and returns final result via GET /api/v1/interview/session/{session_id}/result.

## Major Features (one-line description each)
- Adaptive difficulty: Q-learning agent (tabular) adapts question difficulty per candidate.
- Voice-enabled: Groq Whisper STT for voice answers and Sarvam Bulbul v3 TTS for audio prompts.
- Idempotent sessions: resumable on refresh with server-side session token.
- Proctoring: real-time events logged in `proctoring_violations`, warnings and termination logic.
- Evaluation: multi-dimensional LLM scoring mapped to numeric rubric.
- RL logging: `rl_attempt_log` stores full per-question RL records for traceability.
- Offline fallbacks: fallback bank for question generation failures.
- Rate-limit handling: queued calls to Groq when needed.

## AI Interviewer Behavior
- Starts at difficulty `medium`.
- Uses `llama-3.1-70b-versatile` for generation and evaluation with defensive prompts.
- For follow-ups, decides probe depth based on candidate correctness and response quality.
- Enforces policy guard: no direct jump from `easy`→`hard`; force `decrease` if wrong_streak≥4; force `increase` if correct_streak≥5.
- Returns structured JSON responses consumable by backend evaluation pipeline.

## Tech Stack (with purpose for each)
- Backend: Python 3.11 + FastAPI — HTTP API, async endpoints.
- ORM: SQLAlchemy (async) — database mapping to PostgreSQL (prod) and SQLite (dev).
- DB: PostgreSQL — primary production database; SQLite via aiosqlite for dev.
- Frontend: React 18 + Vite + TailwindCSS — interview UI on port 5173.
- LLM: Groq API running LLaMA 3.1 70B versatile — question generation and evaluation.
- STT: Groq Whisper (REST) — voice → text transcription (wav, 16kHz mono).
- TTS: Sarvam Bulbul v3 (REST) — text → buffered audio.
- RL Engine: Custom tabular Q-Learning — adaptive difficulty control and Q-table persistence (`rl_q_table`).
- Auth: JWT (python-jose HS256) — stateless session authentication.
- Cache: Redis — session caching and rate limiting.
- Storage: S3-compatible object storage (answer audio URLs).
- Worker: Async background tasks — queued Groq requests and TTS buffering.

## Workflow Summary (numbered steps)
1. Start: POST /api/v1/interview/start — create `interview_sessions` row.
2. Permission checks: frontend obtains media permissions.
3. Next question: GET /api/v1/interview/session/{session_id}/next-question.
4. Answer: voice or text submission to POST /submit-answer.
5. STT (if voice): POST /api/v1/interview/stt → text fallback if timed out.
6. LLM evaluation: POST to Groq with Answer Evaluation prompt.
7. Scoring: map LLM scores → per-dimension, combine → total.
8. RL update: derive reward → Bellman update to `rl_q_table` and log `rl_attempt_log`.
9. Persist: save answer in `interview_answers`.
10. Loop: continue until max questions (10), time limit (30 min), or termination.
11. End: POST /end triggers final aggregation into `interview_evaluation`.
12. Result: GET /result returns final_score and diagnostic breakdown.

## What Makes This Round Novel
- Tight integration between an LLM evaluation pipeline and a tabular RL agent using explicit Bellman updates stored in `rl_q_table`.
- Production-grade proctoring integrated with resume/idempotency to permit safe browser refreshes.
- Multi-modal candidate interaction (voice & text) with robust fallbacks and a deterministic RL policy guard.
- Optimistic Q init and explicit reward clamping ensure conservative exploration with fast adaptation.
