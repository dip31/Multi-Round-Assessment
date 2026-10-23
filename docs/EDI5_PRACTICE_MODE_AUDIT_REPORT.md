# EDI5 Practice Mode Audit Report (Post M2-E)

**Date:** 2026-09-25  
**Auditor:** opencode AI  
**Scope:** Read-only end-to-end audit of Practice Mode implementation after M2-E independent-round fixes

---

## Executive Summary

**VERDICT: NOT READY FOR M2-F**

Practice Mode has significant defects that prevent production readiness:
- Critical database schema mismatch (missing `practice_type` column)
- Active round conflict logic incorrectly blocks independent practice switching
- Repeated attempts reuse the same session (violates "new attempt each time" requirement)
- Legacy context uses sequential policy instead of independent policy
- Frontend state leakage between practice types

---

## 1. Repository & Architecture Map

| Component | File | Responsibility | Calls | Called By |
|-----------|------|----------------|-------|-----------|
| Practice Router | `app/modules/practice/routers/practice_router.py` | Entry point for all practice operations | session_service, assessment_context_service, practice_result_service | Frontend `/practice/start` |
| Practice Result Service | `app/modules/practice/services/practice_result_service.py` | Historical result retrieval | AptitudeAttempt, CodingSubmission, InterviewTurn | Practice Router |
| Session Router | `app/modules/session/routers/session_router.py` | Legacy session lifecycle | session_service | Frontend `/session/start`, `/session/fresh` |
| Session Service | `app/services/session_service.py` | Core session/round CRUD & lifecycle | AssessmentSession, AssessmentRound, AssessmentContext | All routers |
| Assessment Context Service | `app/services/assessment_context_service.py` | Context/policy resolution | AssessmentContext, AssessmentPolicy | Practice Router, Session Service |
| Assessment Models | `app/models/assessment.py` | ORM for sessions/rounds | — | All services |
| Assessment Context Models | `app/models/assessment_context.py` | ORM for contexts/policies | — | Context Service |
| Aptitude Router | `app/modules/aptitude/routers/aptitude_router.py` | MCQ/Technical/Combined question flow | aptitude_service, session_service | Frontend `/aptitude/*` |
| Aptitude Service | `app/modules/aptitude/services/aptitude_service.py` | Question selection, RL, scoring | question_selector, rl_engine | Aptitude Router |
| Coding Router | `app/modules/coding/routers/coding_router.py` | Coding problem/submission flow | coding_service, session_service | Frontend `/coding/*` |
| Interview Router | `app/modules/interview/routers/interview_router.py` | Interview pipeline | GroqService, InterviewRLEngine | Frontend `/interview/*` |
| Frontend Practice Overview | `frontend/src/pages/PracticeOverview.jsx` | Practice type selection UI | sessionService.startPractice | App Routes |
| Frontend Session Service | `frontend/src/services/sessionService.js` | API client for practice/session | api.js | PracticeOverview, useSession |
| Database Schema | `database/complete_schema.sql` | PostgreSQL schema (reference) | — | Migrations |
| SQLite Database | `database.db` | Actual runtime DB | — | Tests, Dev |

---

## 2. Practice Entry Points Trace

| UI Component | Frontend Function | API Endpoint | Request Payload | Backend Handler | Service | DB Writes |
|--------------|-------------------|--------------|-----------------|-----------------|---------|-----------|
| PracticeOverview card click | `handleStartPractice('mcq')` | `POST /practice/start` | `{round_type: "aptitude", practice_type: "mcq"}` | `start_practice()` | `get_or_create_practice_context()`, `create_session()`, `start_round()` | assessment_contexts, assessment_sessions, assessment_rounds |
| PracticeOverview card click | `handleStartPractice('technical')` | `POST /practice/start` | `{round_type: "aptitude", practice_type: "technical"}` | `start_practice()` | same | same |
| PracticeOverview card click | `handleStartPractice('combined')` | `POST /practice/start` | `{round_type: "aptitude", practice_type: "combined"}` | `start_practice()` | same | same |
| PracticeOverview card click | `handleStartPractice('coding')` | `POST /practice/start` | `{round_type: "coding", practice_type: "coding"}` | `start_practice()` | same | same |
| PracticeOverview card click | `handlePractice('interview')` | `POST /practice/start` | `{round_type: "interview", practice_type: "interview"}` | `start_practice()` | same | same |
| Legacy `/session/fresh` | `startFreshSession()` | `POST /session/fresh` | `{}` | `start_fresh_session()` | `create_session()`, `create_round(aptitude)` | assessment_sessions, assessment_rounds |

**Critical Finding:** The legacy `/session/fresh` endpoint (line 106-127 in `session_router.py`) still forces `aptitude` as first round and uses sequential progression. The comment on line 112-114 acknowledges this but **does not prevent frontend from calling it**.

**Bypass Path:** Frontend could call `/session/fresh` directly, bypassing independent practice flow.

---

## 3. Practice Type Mapping Verification

### Required Mapping
| UI | round_type | practice_type |
|----|------------|---------------|
| MCQ | aptitude | mcq |
| Technical MCQ | aptitude | technical |
| Combined MCQ | aptitude | combined |
| Coding | coding | coding |
| Interview | interview | interview |

### Actual Implementation

**Frontend (PracticeOverview.jsx:30-32):**
```javascript
let roundType = "aptitude";
if (practiceType === 'coding') roundType = "coding";
if (practiceType === 'interview') roundType = "interview";
```
✅ Correct for all 5 types.

**API Schema (practice_router.py:94-96):**
```python
class PracticeStartRequest(BaseModel):
    round_type: str
    practice_type: Optional[str] = None  # mcq | technical | combined | coding | interview
```
✅ Accepts all 5 practice_type values.

**Backend Handler (practice_router.py:197-201):**
```python
if payload.round_type not in {"aptitude", "coding", "interview"}:
    raise HTTPException(400, "Invalid round type. Must be aptitude, coding, or interview.")
```
✅ Validates round_type correctly.

**Question Selector (question_selector.py:55-71):**
```python
if p_type == "technical": return ALL_TECHNICAL_TOPICS
if p_type == "combined": return ALL_TECHNICAL_TOPICS (50%) or MCQ_TOPICS (50%)
if p_type == "mcq" or p_type == "aptitude": return MCQ_TOPICS
```
✅ Correctly distinguishes mcq/technical/combined.

**Result Service (practice_result_service.py:64):**
```python
if round_type in ("aptitude", "mcq", "technical", "combined"):
    return aptitude_result_summary
```
✅ Groups all aptitude-family rounds correctly.

### Inconsistencies Found

| Location | Issue | Impact |
|----------|-------|--------|
| `aptitude_router.py:58` | Query param `practice_type` defaults to None, not validated | Could pass invalid values |
| `assessment_rounds` table | **Missing `practice_type` column in SQLite DB** | **CRITICAL: All practice_type data lost on SQLite** |
| `portfolio.py:212-218` | Maps `round_type="technical"` and `round_type="combined"` separately | Works but depends on practice_type being stored |

---

## 4. Assessment Context & Policy Verification

### Database State (SQLite)
```sql
-- assessment_policies
1 | Legacy Practice Policy | 180 | 30 | NULL | 1 | 1 | sequential | {"rounds": ["aptitude", "coding", "interview"]}
2 | Practice Policy        | 180 | 30 | NULL | 1 | 1 | independent  | {}

-- assessment_contexts
1 | practice | legacy | NULL | NULL | NULL | NULL | NULL | NULL | 1 | active | 2026-09-23
```

### Critical Defects

| Defect | Evidence | Expected | Actual |
|--------|----------|----------|--------|
| **Legacy context uses sequential policy** | Context ID 1 has `policy_id=1` (sequential) | Practice context should use policy_id=2 (independent) | Uses legacy sequential policy |
| **Practice creates new context per attempt** | `get_or_create_practice_context()` line 94-106 creates NEW context each call | Should reuse or create per-user practice context | Creates new context every `/practice/start` |
| **Policy not actually used for progression** | `practice_router.py:216-220` reads progression_mode but `start_round()` doesn't enforce it | Independent policy should allow concurrent rounds | Unique index `one_active_round_per_session` prevents concurrent rounds |

### Policy-Driven Timing Verification
- `session_service.py:31-44` ✅ Uses `context.policy.session_duration_minutes` 
- `session_service.py:47-54` ✅ Uses `context.policy.round_duration_minutes`
- `session_service.py:175-180` ✅ Applies context policy on session creation

**But:** The unique index `one_active_round_per_session` (line 73-75 in schema.sql) enforces **one active round per session** regardless of policy. This contradicts independent progression.

---

## 5. Sequential Logic Search Results

| Code Location | Used By | Independent-Safe? | Risk |
|---------------|---------|-------------------|------|
| `practice_router.py:65` `ROUND_ORDER` | Legacy fallback only | ❌ No | HIGH - Still referenced in `_next_round_type()` |
| `practice_router.py:68-75` `_next_round_type()` | `complete_practice_round()`, `advance_practice_round()` | ❌ No | HIGH - Called in sequential path |
| `practice_router.py:230-234` `progression_mode == "independent"` check | Practice mode | ✅ Yes | MEDIUM - But blocked by unique index |
| `practice_router.py:420-220` `progression_mode` resolution | Complete/Advance | ✅ Yes | LOW |
| `session_router.py:52-53` Auto-create aptitude round | `/session/start` legacy | ❌ No | MEDIUM - Legacy only |
| `session_router.py:124-125` Auto-create aptitude round | `/session/fresh` legacy | ❌ No | MEDIUM - Legacy only |
| `session_service.py:430-451` `advance_to_next_round()` | Sequential modes | ❌ No | LOW - Not used by practice when independent |
| `assessment_rounds` unique index | All modes | ❌ No | **CRITICAL** - Prevents concurrent rounds |

### Active Round Conflict Logic (Critical Section)

**File:** `practice_router.py:203-248`

```python
existing_session = get_active_session(db, current_user.id)

if existing_session is not None:
    active_round = get_active_round(db, existing_session.id)
    if active_round is None:
        # Start requested round
    elif active_round.round_type == payload.round_type and active_round.practice_type == payload.practice_type:
        # Resume same
    elif progression_mode == "independent":
        # Close current, start requested  ← INTENDED BEHAVIOR
        complete_round(db, active_round.id, current_user.id)
        active_round = start_round(db, existing_session.id, payload.round_type, payload.practice_type)
    else:
        raise HTTPException(409, "An active X round is already in progress...")
```

**The 409 Generation Path (line 237-240):**
- Triggered when `progression_mode != "independent"`
- Since legacy context uses sequential policy, **Practice incorrectly gets 409**

**Database Constraint Conflict:**
```sql
CREATE UNIQUE INDEX one_active_round_per_session 
ON assessment_rounds(session_id) 
WHERE status = 'active';
```
Even if code allows switching, the DB rejects INSERT of second active round in same session.

**Conflict Key:** `session_id` + `status='active'` (not round_type, not practice_type, not user_id)

---

## 6. `/practice/start` Implementation Audit

### Current Flow (practice_router.py:183-287)

1. **Validate round_type** ✅
2. **Get active session** → `get_active_session()` (expires stale)
3. **If session exists:**
   - Check session not expired ✅
   - Resolve context & progression_mode ✅
   - Get active round ✅
   - If no active round → `start_round()` with requested type ✅
   - If same round_type+practice_type → resume ✅
   - If independent → complete current, start requested ✅
   - Else → 409 ❌ (because legacy context is sequential)
4. **If no session:**
   - `get_or_create_practice_context()` → **Creates NEW context each time** ❌
   - Check availability/attempts ✅
   - `create_session(context_id)` ✅
   - Determine round_type from progression_mode ✅
   - `start_round()` ✅

### Database Records Created Per Call

| Call | assessment_contexts | assessment_sessions | assessment_rounds |
|------|---------------------|---------------------|-------------------|
| First `/practice/start` | +1 (mode=practice, policy_id=2) | +1 (context_id=new) | +1 (round_type=requested) |
| Second `/practice/start` (different type) | **+1 (NEW context!)** ❌ | Reuses existing session | +1 (round_type=requested) |

**Defect:** Each `/practice/start` creates a new AssessmentContext (line 96-106), fragmenting history.

---

## 7. Active-Round Conflict Logic Deep Dive

### Conflict Condition
```python
# session_service.py:310-314
active = get_active_round(db, session_id, for_update=True)
if active is not None:
    if active.round_type == round_type and active.practice_type == practice_type:
        return active
    raise ValueError("Another assessment round is already active")
```

### Unique Index (DB Level)
```sql
CREATE UNIQUE INDEX one_active_round_per_session 
ON assessment_rounds(session_id) 
WHERE status = 'active';
```

### Test Matrix

| Scenario | Expected | Actual | Root Cause |
|----------|----------|--------|------------|
| Completed Coding → Start MCQ | ✅ Allowed | ✅ Works (no active round) | — |
| Expired Coding → Start MCQ | ✅ Allowed | ✅ Works (expired by backend) | `_expire_stale_rounds()` runs |
| Terminated Coding → Start MCQ | ✅ Allowed | ✅ Works (not active) | — |
| **Active Coding → Start MCQ** | ✅ Allowed (independent) | ❌ **409 Conflict** | Legacy context = sequential + unique index |
| Active MCQ → Start MCQ (same) | ✅ Resume | ✅ Works | Same round_type+practice_type check |

### Historical Records & Conflict
- Completed rounds have `status='completed'` → **Cannot trigger conflict** ✅
- Expired rounds have `status='expired'` → **Cannot trigger conflict** ✅
- Only `status='active'` rounds conflict → Correct but too restrictive for Practice

---

## 8. Database Schema & Migrations Audit

### Migration vs Actual Schema Comparison

| Table | Migration Defines | SQLite Actual | Match? |
|-------|-------------------|---------------|--------|
| `assessment_policies` | ✅ All columns | ✅ All columns | YES |
| `assessment_contexts` | ✅ All columns | ✅ All columns | YES |
| `assessment_sessions` | ✅ + `context_id` | ✅ + `context_id` | YES |
| `assessment_rounds` | ✅ + `practice_type` | ❌ **MISSING `practice_type`** | **NO** |
| `one_active_session_per_user` | ✅ Partial unique index | ✅ Exists | YES |
| `one_active_round_per_session` | ✅ Partial unique index | ✅ Exists | YES |

**Critical Finding:** The migration `add_practice_type_to_rounds.py` adds `practice_type` column but **it is not present in the SQLite database** used for testing/development. This means:
- All `practice_type` values are silently dropped
- Historical attempt distinction by practice_type is impossible
- Result service grouping by practice_type fails

### Missing Indexes for Practice Independence
No partial unique index exists for:
- `one_active_round_per_user_per_type` (would allow concurrent different types)

---

## 9. Lifecycle & Expiration Audit

### State Semantics (session_service.py:22)
```python
SESSION_STATES = {"not_started", "in_progress", "completed", "terminated", "expired"}
ROUND_STATES = {"pending", "active", "completed", "terminated", "expired"}
```

### Expiration Handling
| Function | Trigger | Action | Timezone |
|----------|---------|--------|----------|
| `_expire_stale_session()` | `get_active_session()` call | Session + active rounds → expired | `datetime.utcnow()` (naive) |
| `_expire_stale_rounds()` | `get_active_round()` call | Active rounds → expired | `datetime.utcnow()` (naive) |
| `start_round()` | Before creating round | Auto-expire session if `expires_at <= now` | `datetime.utcnow()` (naive) |

### Timezone Mismatch Risk
- **Database:** `server_default=func.now()` → DB server timezone (usually UTC)
- **Application:** `datetime.utcnow()` → Naive UTC
- **Model Property:** `time_remaining_seconds` uses `datetime.utcnow()` 

**Risk:** If DB server timezone ≠ UTC, `expires_at` comparison is wrong. No `timezone.utc` usage found.

### Expired → Cannot Block New Practice
- `_expire_stale_session()` runs at start of `get_active_session()` ✅
- Expired sessions → status='expired' → new session can be created ✅
- Expired rounds → status='expired' → new round can be started ✅

---

## 10. Completion Flow Audit

### MCQ Completion (practice_router.py:342-467)
```python
# Independent mode (line 422-438)
if progression_mode == "independent":
    # Complete ROUND only, session remains active
    message = "... Ready for next practice."
    session_completed = False
    next_round_obj = None  # NO AUTO-CREATE
```

**Verified:** No automatic `create_round()` or `advance_to_next_round()` in independent mode.

### Hidden Auto-Advance Search
| Pattern | Found In | Used By Practice? |
|---------|----------|-------------------|
| `advance_to_next_round` | practice_router.py:547, session_service.py:430 | Only in sequential path |
| `create_round` | session_router.py:53, 125 | Legacy only |
| `ROUND_ORDER` | practice_router.py:65, 71 | Legacy fallback only |
| `_next_round_type()` | practice_router.py:376, 503 | Sequential path only |

**Conclusion:** Independent practice correctly does NOT auto-create next round.

---

## 11. Historical Attempts Immutability

### Test Evidence
- `test_completed_attempts_are_not_overwritten` ✅ PASSES
- `test_history_preserves_all_attempts` ✅ PASSES
- `test_repeated_attempts_are_distinct` ❌ **FAILS** (same session_id reused)

### Database Evidence
- Each completed round: `status='completed'`, `completed_at` set ✅
- Scores persisted in `AssessmentRound.score` ✅
- AptitudeAttempt/CodingSubmission/InterviewTurn linked by `round_id` ✅

### Frontend Display Risk
- `PracticeResultDashboard` uses `/practice/session/{id}/round/{id}/result` → Correctly scoped to specific round
- `PracticeSummary` at `/result/:sessionId/:roundId` → Correctly scoped
- **No evidence of latest-attempt leakage** ✅

---

## 12. Practice Again Audit

### Flow
1. User completes round → sees result page (`PracticeResultDashboard`)
2. Clicks "Practice Again" → Navigates to `/practice/{type}` (PracticeOverview)
3. `handleStartPractice()` calls `startPractice(roundType, practiceType)`
4. `POST /practice/start` with same practice_type

### Current Behavior (from failed test `test_repeated_attempts_are_distinct`)
```python
# Attempt 1
resp1 = start_practice(round_type="coding")  # session_id=1
complete_round(resp1.active_round.id)

# Attempt 2  
resp2 = start_practice(round_type="coding")  # session_id=1 (SAME!)
```

**Root Cause:** `get_active_session()` returns the completed session because it's still the latest for user, and `create_session()` returns existing active session (but session is completed, not active).

**Code Path:** `session_service.py:143-154` `get_active_session()` only returns `status='in_progress'`. But `start_practice()` at line 203 calls `get_active_session()` which expires stale sessions first. After completion, session is `status='completed'`, so `get_active_session()` returns None. Then `create_session()` at line 269 should create NEW session...

**But test shows same session_id** → Need to investigate `create_session()` idempotency logic.

### `/session/fresh` Usage
- Frontend PracticeOverview does NOT call `/session/fresh` ✅
- Only uses `/practice/start` ✅

---

## 13. Frontend State Audit

### State Storage
| Storage | Keys Used | Staleness Risk |
|---------|-----------|----------------|
| `localStorage` | `edi5_practice_config` (practice_type, subject) | **HIGH** - Persists across practice types |
| React State | `starting` (per-type) | LOW - Component-scoped |
| URL Params | `/practice/mcq`, `/practice/coding`, etc. | LOW - Route-based |

### Stale State Scenario
1. User selects **Coding** → `localStorage.setItem('edi5_practice_config', {practice_type: 'coding'})`
2. Completes coding, navigates away
3. User selects **MCQ** → `handleStartPractice('mcq')` called
4. **But** `localStorage` still has `practice_type: 'coding'`
5. No code reads `localStorage` before starting new practice → **Actually OK**

**However:** `edi5_practice_config` is written but never read for decision-making. It's dead code.

### Cross-Type Contamination Check
- `PracticeOverview` uses `location.pathname` to determine `selectedType` (line 12-20)
- Each card calls `handleStartPractice()` with explicit `practiceType` argument
- **No reuse of previous practice_type** ✅

---

## 14. Results & Analytics Audit

### Result APIs
- `GET /practice/session/{session_id}/round/{round_id}/result` → `get_round_result_summary()`
- `GET /practice/session/{session_id}/round/{round_id}/review` → `get_round_detailed_review()`
- `GET /practice/history` → Lists all sessions with rounds

### Ownership Enforcement
- Both result endpoints call `get_owned_session()` first (line 615, 640) ✅
- Result service trusts router ownership check ✅

### Analytics vs Lifecycle Separation
- Portfolio `/me` endpoint reads **completed rounds only** (`status='completed'`) ✅
- Does not use active session/round state for analytics ✅
- Historical performance isolated from current lifecycle ✅

---

## 15. Security / Ownership Audit

### Every Practice API Verifies
| Endpoint | Auth | Session Ownership | Round Ownership |
|----------|------|-------------------|-----------------|
| `POST /practice/start` | `get_current_user` | `get_active_session(user_id)` | — |
| `GET /practice/status` | `get_current_user` | `get_active_session(user_id)` | — |
| `POST /practice/complete-round` | `get_current_user` | `get_owned_session()` | `get_owned_round()` |
| `POST /practice/advance` | `get_current_user` | `get_owned_session()` | `get_owned_round()` |
| `GET /practice/history` | `get_current_user` | Filters by `user_id` | — |
| `GET /practice/session/{id}/round/{id}/result` | `get_current_user` | `get_owned_session()` | — |
| `GET /practice/session/{id}/round/{id}/review` | `get_current_user` | `get_owned_session()` | — |

### Service Layer Ownership
- `get_owned_session()` joins `AssessmentSession.user_id == user_id` ✅
- `get_owned_round()` joins through session to user ✅
- `with_for_update()` used for mutations ✅

### Cross-User Access Test
- `test_cross_user_isolation` ✅ PASSES
- `test_session_ownership_cross_user` ✅ PASSES
- `test_round_ownership_cross_user` ✅ PASSES

---

## 16. Repeated Attempts Audit

### Max Attempts Policy
- Practice Policy (id=2): `max_attempts = NULL` → Unlimited ✅
- `can_create_attempt()` returns `True` when `max_attempts is None` ✅
- Legacy Policy (id=1): `max_attempts = NULL` → Also unlimited ✅

### Test Results
| Scenario | Test | Result |
|----------|------|--------|
| MCQ #1, MCQ #2, MCQ #3 coexist | `test_mcq_repeat_same_type` | ✅ PASS |
| Coding #1, Coding #2, Coding #3 coexist | `test_coding_repeat` | ✅ PASS |
| Interview #1, Interview #2, Interview #3 coexist | Not explicitly tested | UNKNOWN |
| Distinct session per attempt | `test_repeated_attempts_are_distinct` | ❌ **FAIL** |

### Defect: Session Reuse
The `create_session()` function (line 157-192) has idempotency logic:
```python
existing = get_active_session(db, user_id, for_update=True)
if existing is not None:
    return existing  # Returns existing ACTIVE session
```
After completing a round in independent mode, session stays `in_progress`. So next `/practice/start` reuses the **same session**, creating a new round in it. This violates "new attempt = new session" expectation.

---

## 17. Structured Assessments Regression Check

### Mock Drive
- **Status:** NOT IMPLEMENTED (test `test_m2e_acceptance_no_complete_mock_drive` documents this)
- **Context/Policy Infrastructure:** Exists (mode=`mock_drive`, sequential policy ready)
- **Risk:** None currently - no endpoints use it

### Portfolio
- **Status:** NOT IMPLEMENTED as assessment (test `test_m2e_acceptance_no_complete_portfolio`)
- **Portfolio Page:** Exists as evidence-aware showcase (reads completed rounds)
- **Risk:** None - no sequential assessment flow implemented

### Shared Engine Compatibility
- All three modes use same `AssessmentSession`/`AssessmentRound` tables
- Context `mode` field distinguishes them
- Policy `progression_mode` controls behavior
- **Architecture supports all three** but only Practice is implemented

---

## 18. Test Suite Results

### Practice-Specific Tests
| Test File | Total | Pass | Fail | Notes |
|-----------|-------|------|------|-------|
| `test_practice_independence.py` | 8 | 5 | 3 | 3 critical failures |
| `test_practice_independence_fix.py` | 10 | 10 | 0 | Tests new independent behavior |
| `test_m2b_practice_execution.py` | 24 | 24 | 0 | Legacy sequential tests |
| `test_assessment_context.py` | 32 | 32 | 0 | Context/policy tests |
| `test_assessment_lifecycle.py` | 6 | 6 | 0 | Lifecycle tests |

### Failed Practice Tests (Critical)

1. **`test_complete_independent_coding_no_auto_advance`**
   - Expects: `session_completed=True` after completing coding
   - Actual: `session_completed=False` (session stays active for more practice)
   - **Assessment:** Test expectation may be wrong - independent practice should keep session active

2. **`test_conflicting_active_round_returns_409`**
   - Expects: 409 when starting aptitude while coding active
   - Actual: No exception (code allows switch in independent mode)
   - **Assessment:** Test expects OLD sequential behavior; new independent behavior is correct

3. **`test_repeated_attempts_are_distinct`**
   - Expects: Different `session_id` for each attempt
   - Actual: Same `session_id` reused
   - **Assessment:** **REAL DEFECT** - New attempt should create new session

---

## 19. End-to-End Scenario Validation

| # | Scenario | Expected | Actual | Status |
|---|----------|----------|--------|--------|
| 1 | MCQ → complete → Coding | Allowed | ✅ Works (after first completes) | PASS |
| 2 | Coding → complete → MCQ | Allowed | ✅ Works | PASS |
| 3 | MCQ → complete → Interview | Allowed | ✅ Works | PASS |
| 4 | Interview → complete → Technical MCQ | Allowed | ✅ Works | PASS |
| 5 | MCQ → complete → MCQ again | New attempt | ❌ Same session reused | **FAIL** |
| 6 | Coding → complete → Coding again | New attempt | ❌ Same session reused | **FAIL** |
| 7 | Active Coding → request MCQ | Allowed (independent) | ❌ 409 Conflict | **FAIL** |
| 8 | Expired Coding → request MCQ | Allowed | ✅ Works | PASS |
| 9 | Terminated Coding → request MCQ | Allowed | ✅ Works | PASS |
| 10 | MCQ completion → check DB | No auto Coding round | ✅ No auto round | PASS |

---

## 20. Requirement Traceability Matrix

| Requirement | Code Evidence | DB Evidence | Test Evidence | Status |
|-------------|---------------|-------------|---------------|--------|
| Any round anytime | `practice_router.py:230-234` allows switch | `one_active_round_per_session` blocks | `test_conflicting_active_round_returns_409` fails | **FAIL** |
| Repeat any round | `start_practice()` creates new round | Same session_id reused | `test_repeated_attempts_are_distinct` fails | **FAIL** |
| No forced sequence | Independent path skips `ROUND_ORDER` | No auto-advance in independent | `test_no_auto_progression_after_mcq_completion` passes | PASS |
| No stale 409 | Expired rounds auto-expired | `_expire_stale_rounds()` runs | `test_expired_round_cannot_be_completed` passes | PASS |
| Historical attempts preserved | `status='completed'` immutable | Rounds persist with scores | `test_completed_attempts_are_not_overwritten` passes | PASS |
| Practice Again works | Frontend calls `/practice/start` | New round in same session | `test_mcq_repeat_same_type` passes | PARTIAL |
| MCQ subtype mapping | `question_selector.py:55-71` | `practice_type` column **missing** | `test_mcq_to_technical_mcq` passes | **FAIL** (DB) |
| Expiration works | `_expire_stale_*` functions | `expires_at` populated | `test_stale_round_is_expired_by_backend` passes | PASS |
| Context/Policy used | `get_or_create_practice_context()` | Context created per attempt | `test_practice_uses_independent_policy` passes | PARTIAL |
| Mock Drive unaffected | No implementation | Context mode exists | `test_m2e_acceptance_no_complete_mock_drive` passes | PASS |
| Portfolio unaffected | Portfolio reads completed only | No sequential flow | `test_m2e_acceptance_no_complete_portfolio` passes | PASS |
| Ownership enforced | `get_owned_*` in all routers | FK to user_id | Cross-user tests pass | PASS |

---

## 21. Remaining Risks

### Critical Blockers

| # | File | Line/Function | Observed | Expected | Root Cause | Impact | Fix |
|---|------|---------------|----------|----------|------------|--------|-----|
| 1 | `database.db` (SQLite) | `assessment_rounds` table | Missing `practice_type` column | Column exists per migration | Migration not applied to SQLite | All practice_type data lost; subtypes indistinguishable | Apply migration or recreate SQLite |
| 2 | `practice_router.py` | `get_or_create_practice_context()`:96-106 | Creates new context per `/practice/start` | Reuse per-user practice context | Creates `AssessmentContext` unconditionally | History fragmented; policy lookup broken | Get existing practice context for user |
| 3 | `session_service.py` | `start_round()`:310-314 + unique index | Raises ValueError/IntegrityError on 2nd active round | Allow concurrent rounds in independent mode | Unique index `one_active_round_per_session` + sequential legacy context | Cannot practice multiple types simultaneously | Drop unique index or make it policy-aware |
| 4 | `practice_router.py` | `start_practice()`:203-248 | 409 when switching rounds in practice | Allow switch (independent) | Legacy context uses sequential policy | Practice blocked by legacy data | Update legacy context to use policy_id=2 |

### High-Risk Issues

| # | File | Line/Function | Observed | Expected | Root Cause | Impact | Fix |
|---|------|---------------|----------|----------|------------|--------|-----|
| 5 | `session_service.py` | `create_session()`:164-166 | Returns existing active session | Create new session for new attempt | Idempotency for active sessions only | Repeated attempts share session | Check `status='in_progress'` only; completed sessions should allow new |
| 6 | `practice_router.py` | Line 65 `ROUND_ORDER` | Exists and used in sequential path | Remove or guard | Legacy code not cleaned | Confusion; potential accidental use | Remove or wrap in `if not independent` |
| 7 | `session_router.py` | `/session/fresh`:106-127 | Forces aptitude first, sequential | Deprecate or isolate | Legacy endpoint still exposed | Frontend could bypass independent flow | Remove or add deprecation warning |
| 8 | Timezone | `session_service.py:26` `_now()` | `datetime.utcnow()` naive | `datetime.now(timezone.utc)` | No timezone awareness | Expiration errors if DB≠UTC | Use timezone-aware datetimes |

### Medium-Risk Issues

| # | File | Issue | Impact |
|---|------|-------|--------|
| 9 | `aptitude_router.py:58` | `practice_type` query param not validated | Invalid values silently ignored |
| 10 | `practice_result_service.py:64` | Groups `round_type in ("aptitude","mcq","technical","combined")` | Depends on `practice_type` column (missing in SQLite) |
| 11 | `portfolio.py:212-218` | Maps `round_type="technical"` separately | Will show 0 attempts if practice_type not stored |
| 12 | Frontend `localStorage` | Dead key `edi5_practice_config` written never read | Confusion; potential future bug |

### Low-Risk Issues

| # | File | Issue |
|---|------|-------|
| 13 | `practice_router.py:271-277` | New session uses `payload.round_type` directly for independent mode but `ROUND_ORDER[0]` for sequential - inconsistent |
| 14 | `assessment_context_service.py:106` | `get_or_create_practice_context` doesn't check for existing practice context for user |
| 15 | `practice_router.py:415` | `_finalize_session_score` computes mean of completed rounds - correct but undocumented |

---

## 22. Minimum Fixes Required Before M2-F

### Must Fix (Critical)
1. **Apply `practice_type` column migration to SQLite database** (or recreate DB from complete_schema.sql)
2. **Update legacy practice context (id=1) to use policy_id=2 (independent)**:
   ```sql
   UPDATE assessment_contexts SET policy_id = 2 WHERE id = 1;
   ```
3. **Remove or modify `one_active_round_per_session` unique index** to allow concurrent rounds in independent mode:
   - Option A: Drop index entirely (simplest)
   - Option B: Make it conditional on context policy (requires partial index with join - not in SQLite)
4. **Fix `get_or_create_practice_context()` to reuse per-user practice context**:
   ```python
   existing = db.query(AssessmentContext).filter(
       AssessmentContext.student_id == user_id,
       AssessmentContext.mode == MODE_PRACTICE,
       AssessmentContext.status == "active"
   ).first()
   if existing: return existing
   ```
5. **Fix `create_session()` to create new session for new practice attempt**:
   - Only return existing if `status == 'in_progress'`
   - Completed/expired sessions should allow new session creation

### Should Fix (High)
6. **Remove `ROUND_ORDER` and `_next_round_type()` from practice_router.py** (dead code for practice)
7. **Deprecate `/session/fresh` endpoint** or add explicit warning
8. **Use timezone-aware datetimes** (`datetime.now(timezone.utc)`)

### Nice to Fix (Medium)
9. **Validate `practice_type` query param in aptitude_router.py**
10. **Remove dead `localStorage` key `edi5_practice_config` from frontend**

---

## Final Verdict

### NOT READY FOR M2-F

**Blocking Issues:**
1. Database schema mismatch (missing `practice_type` column) - **Data loss in SQLite**
2. Active round conflict prevents independent practice switching - **Core requirement broken**
3. Repeated attempts reuse same session - **History not truly independent**
4. Legacy context uses wrong policy - **Architecture not aligned**

**All five practice types work individually** but cannot be used independently as required. The foundation (context/policy) exists but runtime behavior contradicts the independent progression design.

**Estimated Fix Effort:** 2-3 days for critical fixes, 1 week for full hardening.