# IntelliHire — Interview API Contracts

Base API path: /api/v1/interview
Auth: JWT (python-jose HS256) in `Authorization: Bearer <token>`. Unless noted, all endpoints require auth.

---

## POST /api/v1/interview/start
- Description: Initialize a new interview session and return `session_id` and `session_token`.
- Auth required: Yes (Authorization header)
- Request body:
  {
    "role": "string (required, 1-64 chars)",
    "answer_mode": "voice|text (required)",
    "preferred_language": "string (optional, e.g., 'en-US')"
  }
- Validation:
  - `role` must match allowed roles; length <= 64.
  - `answer_mode` must be 'voice' or 'text'.
- Success response: 201 Created
  {
    "session_id": "UUID",
    "session_token": "string",
    "status": "INITIALIZING",
    "start_time": "2026-05-25T09:00:00Z",
    "answer_mode": "voice"
  }
- Error responses:
  - 400 Bad Request — invalid fields
  - 401 Unauthorized — missing/invalid JWT
  - 429 Too Many Requests — rate limit on session creation
  - 500 Internal Server Error — DB write failure

---

## GET /api/v1/interview/session/{session_id}/status
- Description: Fetch live session metadata and status.
- Auth required: Yes
- Request: No body. Path param `session_id` UUID.
- Success response: 200 OK
  {
    "session_id":"UUID",
    "status":"READY",
    "current_question_index":2,
    "answer_mode":"voice",
    "warning_count":0,
    "time_elapsed_seconds":450
  }
- Error responses:
  - 401 Unauthorized
  - 404 Not Found — session not found
  - 410 Gone — session expired/terminated

---

## GET /api/v1/interview/session/{session_id}/next-question
- Description: Return the next question for the session; triggers RL action decision for difficulty and creates `interview_questions` row if needed.
- Auth required: Yes
- Request: No body. Query param optional `force_refresh=true` to bypass caching.
- Success response: 200 OK
  {
    "question_id":"UUID",
    "question_text":"string",
    "difficulty":"easy|medium|hard",
    "category":"string|null",
    "time_limit":120,
    "question_index":3,
    "tts_audio_url":"https://.../tts123.wav"  -- optional
  }
- Behavior:
  - Increments `current_question_index` when client acknowledges `QUESTION_ASKED` transition.
  - If RL policy guard forces `decrease`/`increase`, difficulty set accordingly.
- Error responses:
  - 401 Unauthorized
  - 404 Not Found — session missing
  - 429 Too Many Requests — Groq rate limiting or generation queue full
  - 503 Service Unavailable — fallback bank exhausted or generator error

---

## POST /api/v1/interview/session/{session_id}/submit-answer
- Description: Submit an answer (voice or text); if voice, include `answer_audio_url` which backend will forward to STT endpoint.
- Auth required: Yes
- Request body:
  {
    "question_id": "UUID (required)",
    "answer_text": "string (nullable if audio provided)",
    "answer_audio_url": "string (nullable if text provided)",
    "response_time_ms": "integer (required)",
    "client_request_id": "string (idempotency key, required)"
  }
- Validation:
  - One of `answer_text` or `answer_audio_url` must be present.
  - `response_time_ms` must be >=0.
- Success response: 200 OK
  {
    "answer_id":"UUID",
    "scores":{"technical":8.0,"communication":7.5,"confidence":7.0,"problem_solving":7.5,"total":7.75},
    "ai_feedback":"string",
    "rl": {"state_before":"...","action_taken":"increase","reward":0.45,"state_after":"..."},
    "next_question_available": true
  }
- Error responses:
  - 400 Bad Request — missing fields or invalid idempotency key
  - 401 Unauthorized
  - 404 Not Found — session or question not found
  - 409 Conflict — duplicate client_request_id already processed (returns existing answer record)
  - 422 Unprocessable Entity — STT/transcription failed and no text fallback
  - 503 Service Unavailable — Groq evaluation rate-limited (retryable)

---

## POST /api/v1/interview/session/{session_id}/skip-question
- Description: Candidate requests to skip current question. Marks `is_skipped=true` and applies skip penalty.
- Auth required: Yes
- Request body:
  {
    "question_id":"UUID (required)",
    "client_request_id":"string (idempotency key, required)"
  }
- Success response: 200 OK
  {
    "skipped_question_id":"UUID",
    "penalty":1,
    "current_question_index":4,
    "next_question_available": true
  }
- Error responses:
  - 400 Bad Request — missing fields
  - 401 Unauthorized
  - 404 Not Found — question/session not found

---

## POST /api/v1/interview/session/{session_id}/end
- Description: End the interview early (candidate or system), finalize evaluation and persist to `interview_evaluation`.
- Auth required: Yes
- Request body:
  {
    "reason":"string (optional, e.g., 'candidate_finish'|'timeout'|'terminated')"
  }
- Success response: 200 OK
  {
    "session_id":"UUID",
    "status":"COMPLETED",
    "evaluation_id":"UUID",
    "final_score":82.50
  }
- Error responses:
  - 401 Unauthorized
  - 404 Not Found
  - 500 Internal Server Error — evaluation persistence failed

---

## GET /api/v1/interview/session/{session_id}/result
- Description: Retrieve final evaluation for a completed session.
- Auth required: Yes
- Success response: 200 OK
  {
    "session_id":"UUID",
    "technical_score":83.00,
    "communication_score":78.00,
    "confidence_score":80.00,
    "problem_solving_score":86.00,
    "penalty_points":2,
    "final_score":81.00,
    "summary":"Candidate demonstrated strong system design, moderate communication."
  }
- Error responses:
  - 401 Unauthorized
  - 404 Not Found — evaluation not created yet
  - 410 Gone — session terminated without evaluation

---

## POST /api/v1/interview/session/{session_id}/proctoring-event
- Description: Log a proctoring event (tab switch, multiple faces, webcam missing, copy_paste).
- Auth required: Yes
- Request body:
  {
    "event_type":"tab_switch|webcam_missing|multiple_faces|copy_paste|webcam_unavailable",
    "timestamp":"ISO8601 string (optional, otherwise server now)",
    "screenshot_url":"string (nullable)"
  }
- Success response: 201 Created
  {
    "violation_id":"UUID",
    "warning_number":2,
    "session_status":"READY"
  }
- Error responses:
  - 401 Unauthorized
  - 404 Not Found — session missing
  - 422 Unprocessable Entity — invalid event_type

---

## POST /api/v1/interview/tts
- Description: Text → audio via Sarvam Bulbul v3; returns buffered audio URL for frontend playback.
- Auth required: Yes (server-to-server or frontend may call via backend proxy)
- Request body:
  {
    "text":"string (required)",
    "voice":"string (optional, default 'default')",
    "format":"wav|mp3 (optional, default 'wav')",
    "sample_rate":16000
  }
- Success response: 200 OK
  {
    "audio_url":"https://storage.intellihire/tts/abcd.wav",
    "duration_ms":1200
  }
- Error responses:
  - 400 Bad Request — missing text
  - 503 Service Unavailable — TTS provider failure
  - 429 Too Many Requests — provider rate limited

---

## POST /api/v1/interview/stt
- Description: Audio → text via Groq Whisper; used by backend to transcribe voice answers.
- Auth required: Yes
- Request body:
  {
    "audio_url":"string (required)",
    "format":"wav (required, 16kHz mono)",
    "timeout_seconds": 10
  }
- Success response: 200 OK
  {
    "transcript":"string",
    "confidence":0.89,
    "duration_ms":45000
  }
- Error responses:
  - 400 Bad Request — invalid URL or format
  - 422 Unprocessable Entity — audio corrupt or too short
  - 504 Gateway Timeout — STT timeout (>10s)
  - 429 Too Many Requests — Groq rate limiting

---

### Generic error formats
- 4xx/5xx error body:
  {
    "error":"short_code",
    "message":"Detailed message",
    "details":{...optional}
  }
