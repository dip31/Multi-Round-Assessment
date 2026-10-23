# EDI5 M2 Assessment Implementation Plan

## Scope and audit status

This document is a read-only audit output. No code, schema, API, migration, or database change was made while preparing it.

Repository state observed:
- Branch: `feature/divesh`
- Tracking: `origin/feature/divesh`
- Working tree: dirty (existing user changes and untracked artifacts present)
- Alembic head: `7b404c6a0d4f`
- Local repo is not a clean baseline; all implementation work must be deferred until the plan is reviewed and approved.

---

## 1. Current architecture

The assessment engine is a lightweight session/round orchestration layer built around a single user-scoped session and a sequence of module-specific rounds.

Current architecture in practice:
- `AssessmentSession` models the student lifecycle and acts as the parent container for all rounds.
- `AssessmentRound` models one round of work (`aptitude`, `coding`, `interview`).
- Module services operate mostly independently and reuse session helpers instead of a single central assessment orchestrator.
- `app/services/session_service.py` is the closest thing to a state machine, but it is not a full lifecycle engine.
- The app uses per-user authorization via `get_current_user()` and then fetches the user’s active session or active round by ID and type.
- Scoring and completion are spread across module service logic rather than a single final-result service.

Important architectural observations:
- There is no `AssessmentContext` table or compatibility layer today.
- There is no canonical state enum set for all lifecycle transitions beyond simple status strings.
- Server-authoritative timing is partially present (`started_at`, `completed_at`, `time_remaining_seconds`), but it is not consistently enforced across all modules.
- Round completion logic is decentralized and influenced by route-level checks.

---

## 2. Current assessment flow

Observed runtime flow:

1. User authenticates
   - File: [app/core/auth.py](app/core/auth.py)
   - Function: `get_current_user()`
   - Behavior: validates bearer JWT and resolves `User` from token
   - Authorization: backend JWT validation; no assessment-specific role guard beyond user ownership

2. Session creation / start
   - File: [app/modules/session/routers/session_router.py](app/modules/session/routers/session_router.py)
   - Function: `start_session()`
   - Endpoint: `POST /session/start`
   - Behavior: checks active session; if none exists, creates `AssessmentSession` with `status='in_progress'` and auto-creates the first aptitude round
   - DB table: `assessment_sessions`, `assessment_rounds`

3. Session status lookup
   - File: [app/modules/session/routers/session_router.py](app/modules/session/routers/session_router.py)
   - Function: `session_status()`
   - Endpoint: `GET /session/status`
   - Behavior: returns user active session or latest session; if none, returns empty `SessionResponse`

4. Session completion / fresh start
   - File: [app/modules/session/routers/session_router.py](app/modules/session/routers/session_router.py)
   - `complete_current_session()` and `start_fresh_session()`
   - Behavior: closes active round, marks session complete, or closes old session before starting fresh

5. Aptitude flow
   - File: [app/modules/aptitude/routers/aptitude_router.py](app/modules/aptitude/routers/aptitude_router.py)
   - Functions: `_require_active_round()`, `next_question()`, `submit_answer_endpoint()`, `get_round_result()`
   - Endpoint(s): `GET /aptitude/next-question`, `POST /aptitude/submit-answer`, `GET /aptitude/result`
   - Behavior: resolves active aptitude round for user, stores attempts, adapts question difficulty with RL state
   - DB tables: `assessment_rounds`, `aptitude_attempts`, `rl_sessions`

6. Coding flow
   - File: [app/modules/coding/routers/coding_router.py](app/modules/coding/routers/coding_router.py)
   - Functions: `start_round()`, `start_after_aptitude()`, `run_code()`, `submit_code()`, `get_results()`
   - Endpoint(s): `POST /coding/start`, `POST /coding/start-after-aptitude`, `POST /coding/run`, `POST /coding/submit`, `GET /coding/results`
   - Behavior: creates coding round, assigns `SessionProblem` rows, evaluates visible/hidden tests via Judge0-style evaluator, persists `CodingSubmission`
   - DB tables: `assessment_rounds`, `session_problems`, `coding_problems`, `coding_test_cases`, `coding_submissions`

7. Interview flow
   - File: [app/modules/interview/routers/interview_router.py](app/modules/interview/routers/interview_router.py)
   - Behavior: resume upload, question pool generation, interview session creation, turn management, scoring, report generation
   - Tables: `interview_sessions`, `approved_question_pools`, `interview_turns`, `proctoring_violations`, `proctoring_events`, etc.

8. Final scoring / result assembly
   - File: [app/modules/aptitude/services/aptitude_service.py](app/modules/aptitude/services/aptitude_service.py)
   - File: [app/modules/coding/services/coding_service.py](app/modules/coding/services/coding_service.py)
   - Behavior: aptitude scores are computed from attempts; coding score is derived from best submission per assigned problem; session total is a simple average of completed rounds
   - No single canonical final result object is enforced across the whole assessment

---

## 3. Existing files

### File classification

| File | Classification | Notes |
|---|---|---|
| [app/models/assessment.py](app/models/assessment.py) | ALREADY EXISTS | Canonical session and round model |
| [app/services/session_service.py](app/services/session_service.py) | ALREADY EXISTS | Session/round lifecycle service |
| [app/modules/session/routers/session_router.py](app/modules/session/routers/session_router.py) | ALREADY EXISTS | Session start/status/complete endpoints |
| [app/modules/aptitude/routers/aptitude_router.py](app/modules/aptitude/routers/aptitude_router.py) | ALREADY EXISTS | Aptitude request flow |
| [app/modules/aptitude/services/aptitude_service.py](app/modules/aptitude/services/aptitude_service.py) | ALREADY EXISTS | Aptitude scoring + RL adaptation |
| [app/modules/coding/routers/coding_router.py](app/modules/coding/routers/coding_router.py) | ALREADY EXISTS | Coding round orchestration |
| [app/modules/coding/services/coding_service.py](app/modules/coding/services/coding_service.py) | ALREADY EXISTS | Coding round creation + score finalization |
| [app/modules/interview/routers/interview_router.py](app/modules/interview/routers/interview_router.py) | ALREADY EXISTS | Interview lifecycle and reporting |
| [app/models/interview.py](app/models/interview.py) | ALREADY EXISTS | Interview session and turn models |
| [app/models/coding.py](app/models/coding.py) | ALREADY EXISTS | Coding problem/submission models |
| [app/models/aptitude.py](app/models/aptitude.py) | ALREADY EXISTS | Aptitude data model |
| [app/models/session_problem.py](app/models/session_problem.py) | ALREADY EXISTS | Assigned coding problems per round |
| [app/core/auth.py](app/core/auth.py) | ALREADY EXISTS | JWT user auth |
| [app/schemas/assessment.py](app/schemas/assessment.py) | ALREADY EXISTS | Assessment API response schema |
| [database/schema.sql](database/schema.sql) | ALREADY EXISTS | Canonical DB schema artifact |
| [create_core_tables.py](create_core_tables.py) | ALREADY EXISTS | SQLite bootstrap for core tables |
| [alembic/versions/add_interview_tables.py](alembic/versions/add_interview_tables.py) | ALREADY EXISTS | Interview table creation migration |
| [alembic/versions/add_session_problems.py](alembic/versions/add_session_problems.py) | ALREADY EXISTS | Coding session problem migration |
| [alembic/versions/rebuild_interview_pipeline.py](alembic/versions/rebuild_interview_pipeline.py) | ALREADY EXISTS | Interview pipeline schema evolution |
| [alembic/versions/add_interview_completion_fields.py](alembic/versions/add_interview_completion_fields.py) | ALREADY EXISTS | Interview completion fields |
| [alembic/versions/add_role_detection.py](alembic/versions/add_role_detection.py) | ALREADY EXISTS | Interview role-detection field |
| [app/models/assessment_context.py](app/models/assessment_context.py) | DO NOT EXIST | This is the missing architectural layer |
| [app/services/assessment_context_service.py](app/services/assessment_context_service.py) | CREATE | Needed only if context layer is chosen |
| [app/models/assessment.py](app/models/assessment.py) | MODIFY | Needed for authoritative lifecycle and compatibility support |
| [app/services/session_service.py](app/services/session_service.py) | MODIFY | Needed for authoritative state transitions |
| [app/modules/session/routers/session_router.py](app/modules/session/routers/session_router.py) | MODIFY | Needed for lifecycle and authorization hardening |
| [app/modules/aptitude/routers/aptitude_router.py](app/modules/aptitude/routers/aptitude_router.py) | MODIFY | Needed for round gating and idempotency |
| [app/modules/coding/routers/coding_router.py](app/modules/coding/routers/coding_router.py) | MODIFY | Needed for timer and finalize behavior |
| [app/modules/interview/routers/interview_router.py](app/modules/interview/routers/interview_router.py) | MODIFY | Needed for lifecycle consistency and evidence contract |
| [app/core/auth.py](app/core/auth.py) | MODIFY | Needed for explicit session/round ownership checks |
| [alembic/versions/*.py](alembic/versions) | MODIFY/CREATE | Needed for migration/backfill of lifecycle and context fields |

### Files that must not be changed during M2 implementation
- app/models/assessment.py — not until lifecycle contract is approved
- app/services/session_service.py — not until lifecycle contract is approved
- app/modules/session/routers/session_router.py — not until lifecycle contract is approved
- app/modules/aptitude/routers/aptitude_router.py — not until practice mode contract is approved
- app/modules/coding/routers/coding_router.py — not until coding flow contract is approved
- app/modules/interview/routers/interview_router.py — not until interview contract is approved
- app/core/auth.py — not until authorization contract is approved
- database/schema.sql — no direct schema edits during the audit phase
- alembic/versions/* — no migration creation before plan review
- frontend code — explicitly out of scope for this M2 phase

---

## 4. Existing APIs

Observed current endpoints:

- `POST /session/start` — create or return active session; auto-creates aptitude round
- `GET /session/status` — returns active or latest session for current user
- `POST /session/fresh` — closes active session and creates a new one
- `POST /session/complete` — marks the active session complete
- `GET /aptitude/next-question` — fetches next aptitude question
- `POST /aptitude/submit-answer` — submits MCQ answer and adapts RL difficulty
- `GET /aptitude/result` — returns most recent completed aptitude summary
- `GET /coding/problems` — lists assigned coding problems
- `POST /coding/run` — runs visible tests only
- `POST /coding/submit` — runs visible + hidden tests and persists submission
- `POST /coding/start` — starts coding round for active session
- `POST /coding/start-after-aptitude` — finalizes aptitude and starts coding
- `GET /coding/results` — retrieves user coding round results
- Interview API endpoints under `/interview/...` for resume upload, question-pool generation, interview session lifecycle, response submission, and reports

Current API issue:
- The session/round lifecycle is operationally correct for simple flows but is not deeply authoritative, idempotent, or concurrency-safe at the API layer.

---

## 5. Existing database tables

Canonical assessment tables:
- `users`
- `refresh_tokens`
- `user_resumes`
- `assessment_sessions`
- `assessment_rounds`
- `aptitude_topics`
- `aptitude_questions`
- `admin_question_feedback`
- `aptitude_attempts`
- `rl_sessions`
- `coding_problems`
- `coding_test_cases`
- `session_problems`
- `coding_submissions`
- `interview_sessions`
- `approved_question_pools`
- `interview_turns`
- `proctoring_violations`
- `proctoring_events`
- `advanced_proctoring_events`

Observed schema facts:
- `assessment_sessions` has: `id`, `user_id`, `status`, `started_at`, `completed_at`, `total_score`
- `assessment_rounds` has: `id`, `session_id`, `round_type`, `status`, `score`, `max_questions`, `started_at`, `completed_at`
- `one_active_session_per_user` is defined in PostgreSQL but not enforced in ORM logic; the app still relies on service-level semantics
- Round statuses currently allow some lifecycle states but not a robust enterprise state model (`pending`/`active`/`completed`/`terminated`/`expired` are present but not always used uniformly)
- Interview-specific tables are independent and linked to `assessment_sessions` rather than a dedicated `AssessmentContext`

---

## 6. Existing states

### Session states
Current session status values are effective but inconsistently modeled:
- `not_started`
- `in_progress`
- `completed`
- `terminated`
- `expired`

Observed reality:
- `create_session()` creates `status='in_progress'`
- `complete_session()` updates to `completed`
- `_expire_stale_session()` updates to `expired`
- No explicit `cancelled` or `abandoned` state is centrally enforced

### Round states
Current round status values:
- `pending`
- `active`
- `completed`
- `terminated`
- `expired`

Observed reality:
- `create_round()` creates `status='active'`
- `end_round()` marks completed
- stale active rounds can be expired in session expiry logic
- round cancellation and duplicate advancement are not standardized

### Timing fields
Current timing is present, but partly implicit:
- `AssessmentSession.started_at`
- `AssessmentSession.completed_at`
- `AssessmentRound.started_at`
- `AssessmentRound.completed_at`
- `AssessmentSession.time_remaining_seconds` property is derived client-side but not stored in DB
- No explicit `duration_seconds`, `expires_at`, or backend-control fields are enforced across all modules

---

## 7. Existing scoring

Scoring is fragmented across modules:

- Aptitude scoring:
  - `AptitudeAttempt` stores `selected_option`, `is_correct`, `response_time`, `difficulty`, `reward`
  - [app/modules/aptitude/services/aptitude_service.py](app/modules/aptitude/services/aptitude_service.py) calculates totals, accuracy, average response time, progression, and RL adaptation metrics
  - Completed aptitude result is assembled with `get_latest_completed_aptitude_result()`

- Coding scoring:
  - `CodingSubmission` stores `score`, `execution_time`, `memory_used`, `status`, `judge0_token`
  - [app/modules/coding/services/coding_service.py](app/modules/coding/services/coding_service.py) computes best submission score per problem and sets `AssessmentRound.score`
  - The session total is then derived as the average of completed round scores

- Interview scoring:
  - `InterviewTurn` has `content_score`, `final_score`, `rl_reward`, `behavioral_snapshot`
  - `InterviewSession` contains `rl_state`, `status`, `completion_reason`, and `completed_at`
  - Interview scoring is embedded in question-turn logic and report generation rather than a single final aggregator

Weakness:
- `AssessmentSession.total_score` is not a single authoritative final result object; it is a derived aggregate from completed rounds.
- No central scoring policy exists for `PRACTICE`, `MOCK_DRIVE`, `OFFICIAL`, or `PORTFOLIO_VERIFICATION` modes.

---

## 8. Current problems / gaps

Major gaps identified by audit:

1. No `AssessmentContext` model or context-driven assessment architecture
   - This makes it hard to distinguish `PRACTICE`, `MOCK_DRIVE`, `OFFICIAL`, and `PORTFOLIO_VERIFICATION` flows.

2. Server-authoritative timing is incomplete
   - `time_remaining_seconds` is derived in Python, not stored and enforced centrally at the DB/service layer.
   - Expiration checks exist in session and coding flow but are not consistently centralized.

3. Idempotency and duplicate guard rails are weak
   - Session start returns 200 for an active session instead of enforcing a dedicated duplicate semantics.
   - Round creation and completion can be triggered multiple times depending on timing and route order.

4. Concurrency / duplicate advancement risks remain
   - Race conditions can occur when multiple requests try to create or complete a session/round at the same time.
   - No row-level locking or transactional guard is evident.

5. Authorization is mostly user-scoped but not fully hardened
   - `get_current_user()` verifies identity, but there are no explicit per-session or per-round authorization checks beyond current-user filtering in most route functions.
   - Cross-user data access is implicitly prevented by query filters but not enforced via a deeper policy layer.

6. Scoring is fragmented and not final-result authoritative
   - Each module calculates its own score; there is no unified result assembly and no canonical final status object.

7. Assessment integrations are connected but not layered into a common lifecycle contract
   - Aptitude, coding, and interview each run in their own service logic and are only loosely orchestrated by session helpers.

---

## 9. Proposed target architecture

Recommended target model:
- Keep the existing `AssessmentSession` and `AssessmentRound` as the root compatibility layer.
- Add an optional central `AssessmentContext` layer for multi-mode governance without breaking existing sessions.
- Treat `AssessmentContext` as a policy container, not as a forced rewrite of all existing modules.
- Build a single service contract for: `create_session`, `start_round`, `activate_round`, `complete_round`, `expire_round`, `complete_session`, `calculate_result`, `authorize_user_access`.

Target architecture concept:
- `AssessmentContext`
  - `id`
  - `user_id`
  - `mode` (`PRACTICE`, `MOCK_DRIVE`, `OFFICIAL`, `PORTFOLIO_VERIFICATION`)
  - `status`
  - `source` / `origin` / `evidence_link`
  - `created_at`, `updated_at`, `active_from`, `expires_at`
- `AssessmentSession`
  - remains the runtime execution unit and compatibility root
- `AssessmentRound`
  - remains the module-specific container for aptitude/coding/interview
- `Attempts` / `Submissions` / `Turns`
  - remain specialized and belong to their module tables

This provides a compatibility bridge: existing sessions continue to work while a more structured context layer is added for future official/mock/portfolio use cases.

---

## 10. AssessmentContext design

Need assessment context or not?
- Short answer: yes, probably needed for future official assessment modes and evidence tracking, but it should be introduced as an additive layer and not as a rewrite.
- It is not strictly required for the current app to function, but it is required for scalable assessment governance.

Recommended context fields:
- `id`
- `user_id`
- `session_id` (nullable with backfill compatibility)
- `mode`
- `name` / `label`
- `status`
- `start_ts`
- `end_ts`
- `expires_at`
- `duration_seconds`
- `score` / `final_result`
- `evidence_contract_version`
- `created_at`, `updated_at`

Compatibility strategy:
- Backfill only when there is an existing assessment session; do not force rewrite of active records.
- New sessions should populate `AssessmentContext` at creation time.
- Existing sessions can remain valid if they lack a context row and are treated as `mode='OFFICIAL'` or `legacy` mode.
- Migration must be additive and safe.

---

## 11. Session lifecycle design

Target session lifecycle:
- `created` → `available` → `in_progress` → `completed`
- optional terminal states: `expired`, `abandoned`, `terminated`, `cancelled`

Recommended authoritative transition rules:
- Only one active session may exist for a user at a time.
- Creation is idempotent with a dedupe token or state check.
- Session start is server-authoritative; client cannot force a new session if a valid active one exists.
- Expiration is backend-controlled using server clock and persisted `expires_at`.
- Completion is guarded against duplicate calls.
- Resume reconnect should resolve the current active session or the latest non-terminal one.

---

## 12. Round lifecycle design

Target round lifecycle:
- `pending` → `active` → `completed`
- optional terminal states: `expired`, `cancelled`, `abandoned`

Recommended rules:
- Create new round as pending, then activate after explicit authorization.
- `activate_round()` sets `status='active'` and `started_at`/`expires_at` fields.
- `complete_round()` is idempotent.
- A completed round should be immutable except for audit metadata.
- Duplicate round activation or no-op completion should return same canonical state instead of creating duplicates.

---

## 13. Timing design

Server-authoritative timing contract:
- `started_at`: when the assessment or round began
- `duration_seconds`: exact server-determined length
- `expires_at`: set by backend at activation time
- `completed_at`: set at completion
- `cancelled_at` / `expired_at` / `abandoned_at`: used if the state is terminal but non-completed

Mandatory rules:
- All expiry decisions must be computed server-side from `expires_at` or timestamps stored in DB.
- Avoid deriving remaining time only from non-persisted Python properties.
- The app should not trust client time.
- Reconnect/resume should verify the session is active and within expiry window before granting continued work.

---

## 14. Idempotency design

Idempotency must be treated as a first-class contract.

Requirements:
- Duplicate session start should return the same active session without creating a second session.
- Duplicate round start should either no-op or return the current active round, depending on the route semantics.
- Duplicate completion should not create additional side effects.

Implementation strategy:
- Add a dedicated idempotency key or use a DB-level uniqueness/guard check on session/round state.
- Use service-layer state checks before creating new rows.
- Return canonical objects with a stable operation result instead of mutating state on every duplicate call.

---

## 15. Concurrency design

Concurrency requirements:
- simultaneous start should not create duplicate active sessions for a user
- simultaneous completion should avoid double-writing terminal states
- duplicate advancement across module boundaries should not advance the session twice

Recommended controls:
- Use `SELECT ... FOR UPDATE` or equivalent transaction locking on active session rows for user-scoped mutation.
- Enforce unique active session and active round checks in DB or transactionally within service layer.
- Avoid creating next round until the previous round is successfully completed and committed.
- Add a transition guard function that validates current state before any updates.

---

## 16. Authorization design

Current auth layer:
- `get_current_user()` validates the JWT and returns the authenticated user.

Needed enforcement:
- Student can only access their own assessment session and rounds.
- Student cannot access another student’s `AssessmentSession`, active round, or report.
- Backend must authorize via user identity and session ownership, not only by route membership.

Recommended changes:
- Centralize policy helpers such as `get_user_session_or_404`, `get_user_round_or_404`.
- Check both `session.user_id == current_user.id` and `round.session.user_id == current_user.id` before returning or mutating data.
- Add admin or faculty-policy checks only where required.
- All report endpoints must enforce ownership rules, especially for interview/interview-summary payloads.

---

## 17. Database changes

Planned DB work (post-audit, not to be implemented yet):
- Add `assessment_context` table or equivalent compatibility layer
- Add server-authoritative timing columns: `expires_at`, `duration_seconds`, `cancelled_at`, `abandoned_at`, `terminated_at`
- Normalize lifecycle status values to a master enum or table-backed contract
- Add a unique active session constraint for each user (or enforce through service + transaction)
- Add functionally relevant indexes for `user_id + status`, `session_id + status + round_type`, `expires_at`, and `updated_at`
- Add idempotency metadata or dedupe keys for session/round creation and completion flows
- Maintain backward compatibility for existing sessions without data loss

Migration strategy:
- Additive migrations first
- Backfill with defaults for legacy rows
- Validate with application flows before strengthening constraints

---

## 18. API changes

Recommended API improvements:
- Introduce a canonical session lifecycle API contract rather than ad hoc route semantics.
- Standardize all state transitions under service methods with explicit return semantics.
- Add session and round guard checks for duplicate `start`/`complete`/`advance` calls.
- Enrich response models with lifecycle metadata (`status`, `expires_at`, `time_remaining_seconds`, `mode`, `can_resume`).
- Add explicit `GET /session/{id}/detail` or `GET /round/{id}` API for ownership-safe fetches.
- Standardize `404`, `409`, and `423` semantics for state conflicts and expiry.

---

## 19. Service changes

Service-layer refactor plan:
- Centralize orchestration in `AssessmentSessionService` / `AssessmentRoundService`
- Move lifecycle transitions into one authoritative state machine
- Introduce `AssessmentContextService` for mode and evidence metadata
- Ensure module services call the same state transition service rather than independently mutating `AssessmentSession` and `AssessmentRound`
- Collapse repeated duplicate logic in `start_session`, `complete_session`, `create_round`, `end_round`, and session expiry helpers

---

## 20. Practice Mode plan

Practice mode should remain distinct from official evaluation mode.

Target behavior:
- Practice sessions can be created for low-stakes training or learning workflows.
- Do not port all official-session constraints into practice mode unless explicitly required.
- Practice rounds should allow retries, easier expiry policies, and non-final result persistence if desired.
- Real scoring and evidence should remain separate from official-mode scoring.

Recommended design:
- Add `AssessmentContext.mode = PRACTICE`
- Keep `AssessmentSession` as the runtime but mark this as non-official
- Allow an optional `practice_result` object separate from official evaluation results

---

## 21. Aptitude integration plan

Current aptitude flow is functional but not standardized:
- Active round is resolved from user + active session
- RL state is stored in `rl_sessions`
- Attempts are persisted in `aptitude_attempts`

Required future work:
- Enforce one canonical aptitude round activation contract
- Require server-side expiry and completion before allowing another round
- Serialize aptitude scoring into a single round result object
- Distinguish official vs. practice scoring policies
- Add stronger duplicate prevention when answer submissions are retried or resubmitted

---

## 22. Coding / Judge0 integration plan

Current coding flow uses `run_and_evaluate()` and `finalize_coding_round()`.

Needed improvements:
- Persist submission state once, not repeatedly across duplicate endpoint calls
- Add idempotent result finalization by `submission_id` / `problem_id` / `round_id`
- Add explicit timer expiry guard and server-controlled finalization
- Add onset/outcome status mapping for Judge0 states and failure reasons
- Store a canonical coding round score and final submission summary in a standardized result object

---

## 23. Interview integration plan

Current interview flow is more independent than aptitude/coding and relies on interview-specific tables.

Needed improvements:
- Bind interview to the same `AssessmentSession` / `AssessmentRound` lifecycle contract
- Add explicit interview round activation and completion transitions
- Persist a report that is consistent with final session scoring
- Add evidence bundle fields for question pool, turn history, consent, score, and completion reason
- Introduce a single contract for resume, question-pool, and final interview report generation

---

## 24. Scoring / result plan

Target result model:
- Each round has a canonical result object
- Each session has a final result object assembled only once
- Each `AssessmentContext` may carry a mode-specific scoring policy
- Final result contract should include:
  - aptitude score
  - coding score
  - interview score
  - weighted total
  - pass/fail or classification
  - completion status
  - evidence links

Important rule:
- Scores should be derived by the service layer and persisted with a single `final_result` or `score_summary` payload, not silently recomputed in multiple places during reads.

---

## 25. Mock Drive preparation

Mock Drive should be treated as a distinct assessment context mode.

Questions to resolve before implementation:
- Is Mock Drive a practice-only environment or a pre-official simulation?
- Is it scored differently from official evaluation?
- Is the same session lifecycle reused or a separate context created?

Recommended approach:
- Add `AssessmentContext.mode='MOCK_DRIVE'`
- Reuse session/round components but tag all results with mock-drive metadata
- Keep evaluation rules separate from official rules

---

## 26. Portfolio Verification preparation

Portfolio Verification is likely a later-stage mode that needs an evidence-oriented contract.

Recommended design:
- `AssessmentContext.mode='PORTFOLIO_VERIFICATION'`
- Keep evidence attachments and artifact references in a standardized format
- Tie the result to a portfolio record, not only to a session score
- Allow verifying resume, project submissions, plus interview evidence without collapsing into a single exam-like result

---

## 27. Evidence integration contract

The assessment engine must eventually produce a consistent evidence bundle for each assessment result.

Evidence bundle should include:
- session metadata
- round metadata
- mode metadata
- aptitude attempt details
- coding submission details
- interview turn records and final report
- any proctoring / violation flags if applicable
- timestamped provenance and ownership markers

Contract requirement:
- evidence should be derived from canonical tables and not duplicated ad hoc in route responses
- report generation must be stable, auditable, and bound to user ownership rules

---

## 28. Testing strategy

Required validation for M2 implementation:
- Unit tests for state transitions (`created`, `available`, `in_progress`, `expired`, `completed`)
- Unit tests for round activation and completion idempotency
- Concurrency tests for duplicate start / complete / advance requests
- Authorization tests for student vs. other-user access
- End-to-end tests for full assessment flow: session → aptitude → coding → interview → final result
- Coverage for expiry and reconnect flow
- Coverage of Practice vs. Official vs. Portfolio Verification mode

Recommended order:
1. lifecycle state tests
2. authorization tests
3. round idempotency tests
4. concurrency tests
5. integrated end-to-end route tests

---

## 29. Migration strategy

Do not implement schema changes during this audit phase.

When implementation starts, use a staged migration strategy:
1. Additive schema changes only
2. Backfill existing legacy rows to populate new metadata fields
3. Add new indexes after backfill validation
4. Update ORM models to match the migration
5. Run verification queries against production-like data

Migration categories:
- assessment lifecycle fields
- context table and foreign keys
- session/round state normalization
- scoring summary fields
- evidence metadata fields

---

## 30. Rollback strategy

Rollback plan:
- Keep all schema changes additive first and reversible
- Never remove old columns or statuses until all app code has been validated
- Retain legacy compatibility for rows without context data
- Use feature-flag or mode-guard routing for mode-specific behavior if needed
- Revert migration in reverse order if verification fails

---

## 31. Risks

1. Hidden business assumptions around official versus practice sessions
2. Client-generated timing and duplicate submission edge cases
3. Race conditions in round advancement and session completion
4. Interview/report pipeline may not align with the base session lifecycle
5. Backfill issues on existing session data if a context layer is added
6. Contract drift between modules and result aggregation

---

## 32. Files that must NOT be changed

These are explicitly out of scope for the M2 implementation until the lifecycle contract is approved:
- [app/models/assessment.py](app/models/assessment.py)
- [app/services/session_service.py](app/services/session_service.py)
- [app/modules/session/routers/session_router.py](app/modules/session/routers/session_router.py)
- [app/modules/aptitude/routers/aptitude_router.py](app/modules/aptitude/routers/aptitude_router.py)
- [app/modules/coding/routers/coding_router.py](app/modules/coding/routers/coding_router.py)
- [app/modules/interview/routers/interview_router.py](app/modules/interview/routers/interview_router.py)
- [app/core/auth.py](app/core/auth.py)
- [database/schema.sql](database/schema.sql)
- [alembic/versions](alembic/versions)
- Frontend assessment screens and UX flows

---

## 33. Implementation milestones

### Milestone 1: lifecycle contract approval
- Formalize session, round, and timing contract
- Approve `expired`, `cancelled`, `abandoned` semantics
- Confirm authorization model

### Milestone 2: live-state hardening
- Add server-authoritative timing fields
- Add idempotency guards
- Add duplicate-start and duplicate-completion protection

### Milestone 3: AssessmentContext layer
- Add `AssessmentContext` table
- Backfill and compatibility rules
- Add mode-specific metadata and evidence hooks

### Milestone 4: scoring and result standardization
- Centralize round result aggregation
- Centralize final session result
- Align aptitude, coding, and interview to same contract

### Milestone 5: integration and release validation
- End-to-end tests
- Authorization validation
- Migration validation and rollback rehearsal

---

## 34. Definition of Done

The M2 implementation is complete when all of the following are true:
- Session lifecycle is canonical and authoritative
- Round lifecycle is canonical and authoritative
- Timing is server-controlled and persisted
- Duplicate start / advance / complete flows are idempotent
- Concurrency issues are prevented by design
- Student-only authorization is enforced at the backend for all session/round/report access
- Final assessment result is derived from a canonical service contract
- Aptitude, coding, and interview modules map to the same lifecycle and auth model
- `AssessmentContext` exists only if the mode-based design is approved and executed
- DB migration and backfill are tested against existing live-like data
- end-to-end audit/assessment flow passes

---

## Executive summary

Current assessment architecture:
- Lightweight, module-based, user-scoped assessment engine built around `AssessmentSession` and `AssessmentRound` with aptitude/coding/interview modules operating semi-independently.

Biggest 5 gaps:
1. No canonical `AssessmentContext` model or mode-aware design
2. Expiry/timing logic is only partly server-authoritative
3. Idempotency and duplicate-state protections are incomplete
4. Concurrency and duplicate advancement risks remain
5. Scoring and result assembly are fragmented across modules and not centrally authoritative

Proposed architecture:
- Maintain existing session/round model as compatibility layer
- Add `AssessmentContext` as a mode-aware policy layer
- Standardize lifecycle transitions, timing, idempotency, auth, and result assembly through central services

Files that would change in a future implementation:
- [app/models/assessment.py](app/models/assessment.py)
- [app/services/session_service.py](app/services/session_service.py)
- [app/modules/session/routers/session_router.py](app/modules/session/routers/session_router.py)
- [app/modules/aptitude/routers/aptitude_router.py](app/modules/aptitude/routers/aptitude_router.py)
- [app/modules/coding/routers/coding_router.py](app/modules/coding/routers/coding_router.py)
- [app/modules/interview/routers/interview_router.py](app/modules/interview/routers/interview_router.py)
- [app/core/auth.py](app/core/auth.py)
- relevant migration files under [alembic/versions](alembic/versions)

Migrations required:
- Add `assessment_context` or equivalent
- Add lifecycle timing columns (`expires_at`, `duration_seconds`, `cancelled_at`, `abandoned_at`)
- Add stronger active-session and active-round uniqueness constraints
- Add scoring and evidence fields for final result metadata
- Backfill legacy rows to safe defaults

Recommended implementation order:
1. Approve lifecycle contract and server-timing rules
2. Harden auth and duplication protections
3. Introduce AssessmentContext compatibility layer
4. Standardize scoring and results
5. Wire aptitude/coding/interview into the same lifecycle contract
6. Add migration/backfill and validation

Exact first milestone:
- Milestone 1: define and approve the authoritative assessment lifecycle contract (session/round transitions, timing, expiry, auth, and result semantics) before any model or migration changes are made.
