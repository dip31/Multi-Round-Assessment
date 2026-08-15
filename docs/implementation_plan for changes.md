# Final Implementation Plan — Debugging & Stabilization v3

## Background

This is the third and final revision. All root causes are traced to specific files and lines.
All architectural decisions are made before execution begins. The plan now incorporates all
9 review corrections.

---

## Architectural Decisions (resolved before any code changes)

| Decision | Resolution |
|----------|-----------|
| Run vs Submit schemas | **Two separate schemas**: `CodingRunResponse` (stateless) and `CodingSubmissionResponse` (persistent). `submission_id` and `submitted_at` remain required and non-optional on submissions. |
| Hidden test data exposure | `/run` returns per-case `{input, expected, actual, passed}` for visible cases only. `/submit` returns **aggregate only**: `{passed, total, score, status}` — no hidden inputs or expected outputs. |
| Axios + TTS error model | HTTP 503 does enter `catch` under axios default `validateStatus`. Inspect `error.response?.status`, `error.response?.headers['content-type']`. On 200, additionally validate `Content-Type ≈ audio/wav` and `byteLength > 1000`. |
| Sarvam logging | Log: exception type, HTTP status code, text length, response audio count, audio byte length, latency. Do NOT log: API key, base64 audio body, candidate transcript, raw Sarvam request. |
| Proctoring ownership | `useAdvancedProctoring` **owns** all: camera init, mic init, MediaPipe, rAF, violation detection, backend event sending, stream cleanup. Components call `startMonitoring` / `stopMonitoring`. No duplicated lifecycle logic. |
| Interview ID type | **Confirmed integer** — `InterviewSession.id` is `Integer` PK in [`interview.py` line 33](file:///d:/Projects/EDI%204/Multi-Round-Assesment-v8n/app/models/interview.py). `parseInt(interviewId, 10)` is correct. |
| Completion reason | Store `completion_reason` enum: `ALL_QUESTIONS_COMPLETED \| USER_SUBMITTED \| TIME_EXPIRED`. Session `status` stays as `ACTIVE \| COMPLETED`. These are separate orthogonal fields. |
| Result page architecture | Three dedicated pages: `ResultPage.jsx` (aptitude, already exists), `InterviewReport.jsx` (interview, already exists at `/interview/report/:interviewId`), `CodingResultPage.jsx` (new). Combined report is a separate future effort. |
| Judge0 status | Mock evaluator is active. This is explicitly documented and acknowledged — not silently assumed. |

---

## Execution Order

```
CODING ROUND
├── 1. Reproduce Submit 500 → capture traceback
├── 2. Audit DB seed data for question fields
├── 3. Separate CodingRunResponse / CodingSubmissionResponse schemas
├── 4. Fix code_evaluator: return per-case detail on run; aggregate only on submit
├── 5. Fix /run and /submit route responses to use correct schemas
├── 6. Verify visible/hidden boundary (confirmed correct; no changes needed)
├── 7. Fix coding question rendering in CodingEditor.jsx (after DB confirmed)
└── 8. Integrate shared proctoring hook into CodingEditor

INTERVIEW ROUND
├── 9. Add Sarvam diagnostic logging
├── 10. Diagnose TTS: server logs + axios error response inspection
├── 11. Fix TTS axios error handling + successful response validation
├── 12. Fix proctoring hook call in InterviewRoom.jsx (pass sessionId integer)
├── 13. Audit useAdvancedProctoring cleanup API (stopMonitoring / cleanup)
├── 14. Fix media lifecycle cleanup on unmount
├── 15. Add completion_reason to InterviewSession model (migration)
├── 16. Add POST /interview/session/{id}/complete endpoint (idempotent)
├── 17. Add Submit Interview button + confirmation in InterviewRoom.jsx
└── 18. Verify InterviewReport.jsx is correctly wired (route exists: /interview/report/:interviewId)

SETTINGS / TESTS
└── 19. Fix OPENAI_API_KEY settings error to unblock pytest

REGRESSION
└── 20. Full flow: Aptitude → Coding → Interview → Reports
```

---

## CODING ROUND

### Issue 1: Submit → HTTP 500 — Reproduce First

> [!CAUTION]
> Do NOT apply any fix until the server traceback is captured. The 500 could be:
> - Pydantic validation (`submitted_at: datetime` receiving `None`)
> - `submission_id: int` receiving `None` from `/run` (second independent 500 source)
> - DB FK constraint failure if `round_id` is invalid
> - Exception in `run_and_evaluate` / Judge0 / mock evaluator

Run backend with `--log-level debug` and attempt a code submission. Read the full Python traceback from the Uvicorn terminal output. Then apply only the confirmed fix.

---

### Issue 2: Separate Run and Submit Schemas

**Problem:** Both `/run` and `/submit` currently use `CodingSubmissionResponse` ([`coding.py` line 51](file:///d:/Projects/EDI%204/Multi-Round-Assesment-v8n/app/schemas/coding.py)), forcing `submission_id` and `submitted_at` to be `Optional` to support stateless run operations. This is poor API modeling.

**Fix:** Two purpose-specific schemas.

#### [MODIFY] [coding.py (schemas)](file:///d:/Projects/EDI%204/Multi-Round-Assesment-v8n/app/schemas/coding.py)

```python
class CodingTestCaseResult(BaseModel):
    """Per-test-case result for /run only (visible cases)."""
    input_data: str
    expected_output: str
    actual_output: str
    passed: bool

class CodingRunResponse(BaseModel):
    """Response from POST /coding/run — stateless, no DB row created."""
    status: str                          # accepted | wrong_answer | runtime_error | etc.
    test_cases_passed: int
    total_test_cases: int
    execution_time: Optional[float] = None
    test_case_results: List[CodingTestCaseResult] = []  # visible cases only

class CodingSubmissionResponse(BaseModel):
    """Response from POST /coding/submit — persistent, DB row created."""
    submission_id: int                   # Required. Never null.
    status: str
    score: float                         # 0.0–1.0
    test_cases_passed: int
    total_test_cases: int
    submitted_at: datetime               # Required. Populated from DB after commit.
    execution_time: Optional[float] = None
```

---

### Issue 3: Hidden Test Data Must Never Be Exposed

**Confirmed safe in backend:** [`coding_service.py` line 92](file:///d:/Projects/EDI%204/Multi-Round-Assesment-v8n/app/modules/coding/services/coding_service.py) — `visible_only` filter is server-enforced. Frontend cannot choose which test cases are used.

**Remaining gap:** `code_evaluator.py` does not currently return per-case detail at all. Need to add it for `/run` only, and ensure it is **never** included in the `/submit` response.

#### [MODIFY] [code_evaluator.py](file:///d:/Projects/EDI%204/Multi-Round-Assesment-v8n/app/modules/coding/utils/code_evaluator.py)

- Add `test_case_results: List[dict]` to the return dict of both `_mock_evaluate` and `evaluate_submission`, **only when `visible_only=True`** (pass this flag through):
  ```python
  if visible_only:
      result["test_case_results"] = [
          {
              "input_data": tc.input_data,
              "expected_output": tc.expected_output,
              "actual_output": actual,   # from stdout
              "passed": passed_bool,
          }
          for tc, actual, passed_bool in zip(test_cases, actuals, pass_flags)
      ]
  ```
- When `visible_only=False` (submit): do NOT include `test_case_results` in return dict.

#### [MODIFY] [coding_router.py](file:///d:/Projects/EDI%204/Multi-Round-Assesment-v8n/app/modules/coding/routers/coding_router.py)

- `/run` endpoint: `response_model=CodingRunResponse` — maps `test_case_results` from evaluator
- `/submit` endpoint: `response_model=CodingSubmissionResponse` — uses `submission.submitted_at` after `db.refresh(submission)`. Never includes hidden inputs or expected outputs.

---

### Issue 4: Coding Question Data Flow Audit

Fields exist in model and schema; unknown if DB data is populated.

#### Step: Inspect seed data

#### [VIEW] [seed_coding_questions.py](file:///d:/Projects/EDI%204/Multi-Round-Assesment-v8n/scripts/seed_coding_questions.py)

Check whether seeded problems include `input_format`, `output_format`, `constraints`, and whether test cases include `explanation`.

Also run:
```sql
SELECT id, title,
  input_format IS NOT NULL AS has_input_fmt,
  output_format IS NOT NULL AS has_output_fmt,
  constraints IS NOT NULL AS has_constraints
FROM coding_problems LIMIT 5;

SELECT id, explanation IS NOT NULL AS has_explanation, is_hidden
FROM coding_test_cases LIMIT 10;
```

#### [MODIFY] [seed_coding_questions.py](file:///d:/Projects/EDI%204/Multi-Round-Assesment-v8n/scripts/seed_coding_questions.py)
If fields are empty: add proper `input_format`, `output_format`, `constraints`, and `explanation` to all seeded problems. Re-run seed.

#### [MODIFY] [CodingEditor.jsx](file:///d:/Projects/EDI%204/Multi-Round-Assesment-v8n/frontend/src/components/CodingEditor.jsx)
After DB is confirmed populated:
- Render `input_format`, `output_format`, `constraints`, `explanation` conditionally (only when non-null)
- Fix literal `\n` display — use `{field.split('\n').map((line, i) => <p key={i}>{line}</p>)}`
- Render `CodingRunResponse.test_case_results` as a per-case table in the run output panel

---

### Issue 5: Coding Proctoring — Shared Hook, Single Ownership

#### [MODIFY] [CodingEditor.jsx](file:///d:/Projects/EDI%204/Multi-Round-Assesment-v8n/frontend/src/components/CodingEditor.jsx)
The component receives `sessionId` as a prop from `CodingRound.jsx`.

```js
const { metrics, startMonitoring, stopMonitoring } = useAdvancedProctoring(sessionId);

useEffect(() => {
    startMonitoring();
    return () => stopMonitoring();
}, []);

// Tab visibility tracking (lightweight, hook-independent)
useEffect(() => {
    const handleVisibility = () => {
        if (document.hidden) logViolation('TAB_SWITCH');
    };
    document.addEventListener('visibilitychange', handleVisibility);
    return () => document.removeEventListener('visibilitychange', handleVisibility);
}, []);
```

The hook handles all camera/mic/MediaPipe init and cleanup internally. `CodingEditor` only calls `startMonitoring` / `stopMonitoring`.

---

## INTERVIEW ROUND

### Issue 6: TTS "Audio Unavailable" — Trace All Zones

#### Identified failure zones

```
Zone 1: POST /interview/tts?text=...  (axios call in interviewService.js:88)
Zone 2: FastAPI route (interview_router.py:929) calls sarvam_service.text_to_speech()
Zone 3: Sarvam API — may fail: no key, rate limit, empty audios[], network error
Zone 4: axios response — HTTP 4xx/5xx enters catch(); BUT body is ArrayBuffer due to
         responseType:'arraybuffer', making error.response.data unreadable as JSON
Zone 5: AudioContext.decodeAudioData(arrayBuffer) — fails if body is not valid WAV
```

> [!NOTE]
> Axios **does** reject non-2xx HTTP responses under default `validateStatus`. So Zone 4 errors do reach `catch`. However, `error.response.data` will be an ArrayBuffer (not readable JSON) — making diagnosis of the actual Sarvam error message invisible to the developer without decoding.

#### Step 6.1 — Add backend diagnostic logging

#### [MODIFY] [sarvam_service.py](file:///d:/Projects/EDI%204/Multi-Round-Assesment-v8n/app/services/sarvam_service.py)

Add at module startup:
```python
logger.info(f"Sarvam client ready: {sarvam_client is not None}, key set: {bool(SARVAM_API_KEY)}")
```

In `text_to_speech()` before Sarvam call:
```python
logger.info(f"TTS request: text_len={len(text)}")
t0 = time.monotonic()
```

After successful response:
```python
logger.info(f"TTS success: audios_count={len(response.audios)}, bytes={len(audio_bytes)}, latency={time.monotonic()-t0:.2f}s")
```

In exception handler — log type + status, not body or key:
```python
logger.error(f"Sarvam TTS failed: type={type(e).__name__}, status={status_code}")
```

#### Step 6.2 — Fix axios error handling for TTS

#### [MODIFY] [interviewService.js](file:///d:/Projects/EDI%204/Multi-Round-Assesment-v8n/frontend/src/services/interviewService.js)

```js
export const synthesizeSpeech = async (text) => {
    let response;
    try {
        response = await api.post(
            `/interview/tts?text=${encodeURIComponent(text)}`,
            null,
            { responseType: 'arraybuffer', timeout: 30000 }
        );
    } catch (err) {
        // HTTP 4xx/5xx — decode the ArrayBuffer error body for diagnostics
        const status = err.response?.status;
        let detail = `HTTP ${status}`;
        try {
            const decoded = new TextDecoder().decode(err.response?.data);
            const parsed = JSON.parse(decoded);
            detail = parsed.detail || detail;
        } catch (_) {}
        throw new Error(`TTS failed: ${detail}`);
    }

    // Validate successful response
    const contentType = response.headers?.['content-type'] || '';
    const byteLen = response.data?.byteLength ?? 0;
    if (!contentType.includes('audio') || byteLen < 1000) {
        throw new Error(`TTS response invalid: content-type=${contentType}, bytes=${byteLen}`);
    }

    return response.data;
};
```

#### Step 6.3 — Fix AudioContext lifecycle

#### [MODIFY] [InterviewRoom.jsx](file:///d:/Projects/EDI%204/Multi-Round-Assesment-v8n/frontend/src/pages/InterviewRoom.jsx)

In `playAudio`:
- Before starting: stop any existing `audioSourceRef.current`
- Resume suspended AudioContext (Chrome autoplay policy):
  ```js
  if (audioContext.state === 'suspended') await audioContext.resume();
  ```

On component unmount (in startup `useEffect` cleanup):
```js
audioContextRef.current?.close();
```

---

### Issue 7: Interview Proctoring Hook Mismatch — Confirmed Root Cause

[`InterviewRoom.jsx` line 38–41](file:///d:/Projects/EDI%204/Multi-Round-Assesment-v8n/frontend/src/pages/InterviewRoom.jsx): passes config object as `sessionId`.
[`useAdvancedProctoring.js` line 132](file:///d:/Projects/EDI%204/Multi-Round-Assesment-v8n/frontend/src/hooks/useAdvancedProctoring.js): `(sessionId, onViolation)` — every `Number(sessionId)` evaluates to `NaN`.

#### [MODIFY] [InterviewRoom.jsx](file:///d:/Projects/EDI%204/Multi-Round-Assesment-v8n/frontend/src/pages/InterviewRoom.jsx)

Move `const interviewId = localStorage.getItem('interview_id')` to **before** the hook call. Then:

```js
// BEFORE (wrong)
const proctoring = useAdvancedProctoring({ idleThreshold: 30, roundType: 'INTERVIEW' });

// AFTER (correct — interviewId is PostgreSQL integer)
const interviewId = localStorage.getItem('interview_id');
const proctoring = useAdvancedProctoring(
    interviewId ? parseInt(interviewId, 10) : null,
    null
);
```

---

### Issue 8: Media Lifecycle Cleanup

#### Step 8.1 — Audit hook cleanup API

#### [VIEW] [useAdvancedProctoring.js](file:///d:/Projects/EDI%204/Multi-Round-Assesment-v8n/frontend/src/hooks/useAdvancedProctoring.js)
Confirm what `stopMonitoring` or equivalent cleanup function the hook exposes and whether it stops camera/mic tracks and cancels rAF.

#### Step 8.2 — Complete cleanup on unmount

#### [MODIFY] [InterviewRoom.jsx](file:///d:/Projects/EDI%204/Multi-Round-Assesment-v8n/frontend/src/pages/InterviewRoom.jsx)

Startup `useEffect` return function must:
```js
return () => {
    clearInterval(timerIntervalRef.current);
    clearInterval(tipPollingRef.current);
    try { audioSourceRef.current?.stop(); } catch (_) {}
    audioContextRef.current?.close();
    proctoring.stopMonitoring?.();   // releases camera, mic, MediaPipe, rAF
};
```

---

### Issue 9: Early Interview Completion

#### Step 9.1 — Add completion_reason to InterviewSession model

#### [MODIFY] [interview.py (model)](file:///d:/Projects/EDI%204/Multi-Round-Assesment-v8n/app/models/interview.py)

```python
# Add to InterviewSession class
status: Mapped[str] = mapped_column(String(20), server_default="ACTIVE", nullable=False)
completion_reason: Mapped[str | None] = mapped_column(
    String(30), nullable=True
)  # ALL_QUESTIONS_COMPLETED | USER_SUBMITTED | TIME_EXPIRED
completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
```

> [!IMPORTANT]
> This requires a database migration. Generate and apply an Alembic migration or run `ALTER TABLE` manually.

**Completion reason semantics:**
- `status` = `ACTIVE` or `COMPLETED` — session lifecycle state
- `completion_reason` = `ALL_QUESTIONS_COMPLETED` | `USER_SUBMITTED` | `TIME_EXPIRED` — how it ended
- These are separate orthogonal fields; never conflate them.

#### Step 9.2 — Add idempotent complete endpoint

#### [MODIFY] [interview_router.py](file:///d:/Projects/EDI%204/Multi-Round-Assesment-v8n/app/modules/interview/routers/interview_router.py)

Add `POST /interview/session/{interview_id}/complete`:
```python
@router.post("/session/{interview_id}/complete")
async def complete_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    interview = db.query(InterviewSession).filter(InterviewSession.id == interview_id).first()
    if not interview:
        raise HTTPException(404, "Interview not found")

    # Idempotent: if already completed, return existing computed values
    if interview.status == "COMPLETED":
        turns = db.query(InterviewTurn).filter(InterviewTurn.interview_id == interview_id,
                                               InterviewTurn.is_followup == False).all()
        scores = [t.final_score for t in turns if t.final_score is not None]
        return {
            "status": "COMPLETED",
            "completion_reason": interview.completion_reason,
            "questions_attempted": len(turns),
            "questions_total": interview.total_turns,
            "performance_score": round(sum(scores) / max(len(scores), 1), 2),
            "completion_ratio": round(len(turns) / max(interview.total_turns, 1), 2),
        }

    # Mark completed
    interview.status = "COMPLETED"
    interview.completion_reason = "USER_SUBMITTED"
    interview.completed_at = datetime.utcnow()
    db.commit()

    turns = db.query(InterviewTurn).filter(InterviewTurn.interview_id == interview_id,
                                           InterviewTurn.is_followup == False).all()
    scores = [t.final_score for t in turns if t.final_score is not None]
    return {
        "status": "COMPLETED",
        "completion_reason": "USER_SUBMITTED",
        "questions_attempted": len(turns),
        "questions_total": interview.total_turns,
        "performance_score": round(sum(scores) / max(len(scores), 1), 2),
        "completion_ratio": round(len(turns) / max(interview.total_turns, 1), 2),
    }
```

#### Step 9.3 — Add Submit Interview button

#### [MODIFY] [InterviewRoom.jsx](file:///d:/Projects/EDI%204/Multi-Round-Assesment-v8n/frontend/src/pages/InterviewRoom.jsx)

- Add prominent "Submit Interview" button, visible at all times in the header
- On click: show confirmation dialog displaying `questions_attempted / total_turns`
- On confirm:
  1. Stop audio: `audioSourceRef.current?.stop()`
  2. Stop proctoring: `proctoring.stopMonitoring?.()`
  3. Close AudioContext: `audioContextRef.current?.close()`
  4. Clear all intervals
  5. `POST /interview/session/{interviewId}/complete`
  6. `navigate('/interview/report/' + interviewId)`

---

### Issue 10: Interview Result — Route Already Exists

**Discovered:** Route `/interview/report/:interviewId` → `InterviewReport.jsx` (21 pages, 15KB) **already exists** in [App.jsx line 147–153](file:///d:/Projects/EDI%204/Multi-Round-Assesment-v8n/frontend/src/App.jsx). This page is separate from `ResultPage.jsx` (aptitude only).

The `ResultPage.jsx` → `getResult()` → `/aptitude/result` path is correct for aptitude.

**Remaining work:**

#### Step 10.1 — Audit InterviewReport.jsx data flow

#### [VIEW] [InterviewReport.jsx](file:///d:/Projects/EDI%204/Multi-Round-Assesment-v8n/frontend/src/pages/InterviewReport.jsx)
Confirm it calls `GET /interview/session/{interviewId}/report` and properly renders `overall_score`, `content_score`, `behavior_score`, `turn_reviews`, `followup_rate`, `feedback_summary`.

#### Step 10.2 — Extend InterviewReportResponse with missing fields

#### [MODIFY] [interview_schema.py](file:///d:/Projects/EDI%204/Multi-Round-Assesment-v8n/app/modules/interview/schemas/interview_schema.py)

Add to `InterviewReportResponse`:
```python
intent_score: Optional[float] = None     # currently missing
completion_ratio: Optional[float] = None  # attempted / total
completion_reason: Optional[str] = None  # ALL_QUESTIONS_COMPLETED | USER_SUBMITTED | TIME_EXPIRED
```

#### Step 10.3 — Add CodingResultPage (new, separate)

#### [NEW] `frontend/src/pages/CodingResultPage.jsx`
Dedicated page for coding round results. Renders: problems attempted, per-problem score, test cases passed/total, language used, execution time. Separate from aptitude or interview result domains.

#### [MODIFY] [App.jsx](file:///d:/Projects/EDI%204/Multi-Round-Assesment-v8n/frontend/src/App.jsx)
Add route: `/coding/result` → `CodingResultPage`

---

## SETTINGS / TESTS

### Issue 11: Unblock pytest

#### Evidence
pytest collection fails: `OPENAI_API_KEY` in `.env` violates `extra = "forbid"` in `Settings`.

#### [MODIFY] [settings.py](file:///d:/Projects/EDI%204/Multi-Round-Assesment-v8n/app/config/settings.py)
Add `OPENAI_API_KEY: Optional[str] = None` to the `Settings` class. This allows the key to be in `.env` without breaking validation, without removing it.

---

## Judge0 Status (Explicitly Documented)

> [!NOTE]
> The mock evaluator ([`code_evaluator.py` line 28](file:///d:/Projects/EDI%204/Multi-Round-Assesment-v8n/app/modules/coding/utils/code_evaluator.py)) is **intentionally active** for this stabilization pass. Mock mode activates automatically when `JUDGE0_URL` is not set in `.env`. The mock compares input vs. expected output as strings. Before final demonstration, either activate Judge0 by setting `JUDGE0_URL` in `.env`, or explicitly describe the evaluation engine as operating in development/mock mode in the project presentation.

---

## Verification Plan

### Per-issue verification

| # | Issue | Verification |
|---|-------|-------------|
| 1 | Coding 500 | POST /coding/submit → HTTP 200 with `submission_id` (int), `submitted_at` (datetime), `score` |
| 2 | Schema separation | POST /coding/run → `CodingRunResponse` with `test_case_results`. POST /submit → `CodingSubmissionResponse` with no hidden test detail. |
| 3 | Hidden data | Confirm `/submit` response body contains only `passed`, `total`, `score`, `status` — no `input_data` or `expected_output` for hidden cases. |
| 4 | Question rendering | All problem fields render in UI; no literal `\n` characters visible. |
| 5 | TTS | Backend logs show Sarvam call, latency, byte count. Browser plays audio. "Audio unavailable" toast does not appear. If Sarvam fails, browser console shows readable error message (not garbled ArrayBuffer). |
| 6 | Proctoring hook | Backend proctoring log endpoint receives events with valid integer `session_id`. |
| 7 | Media cleanup | After interview ends, browser DevTools → Media tab shows no active camera/mic streams. |
| 8 | Early submit | Submit Interview → confirmation → POST complete → redirects to `/interview/report/:id`. If called twice, returns same data (idempotent). |
| 9 | Interview result | `/interview/report/:id` shows `overall_score`, `turn_reviews`, `followup_rate`, `feedback_summary`, `completion_reason`. |
| 10 | pytest | `pytest tests/test_smoke.py` collects without errors. |

### Regression Flow

```
1. Login
2. Start Aptitude → complete → /result (aptitude)
3. Start Coding → view problem (all fields rendered) → run (per-case results) →
   submit (score returned, no hidden data) → /coding/result
4. Start Interview → answer 3 questions → Submit Early →
   /interview/report/:id (shows completion_ratio, performance_score, completion_reason: USER_SUBMITTED)
5. Start Interview → answer all 10 → auto-complete →
   /interview/report/:id (completion_reason: ALL_QUESTIONS_COMPLETED)
6. Verify proctoring events logged in DB for both coding and interview rounds
```

---

## Deferred

- **InterviewRoom UI redesign** — after all logic is stable and regression passes
- **Combined/Final Report page** — separate effort after individual round results work
- **Judge0 activation** — before final demonstration only
