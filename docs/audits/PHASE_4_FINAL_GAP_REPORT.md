# EDI5 Phase 4 — Final Completion Audit and Targeted Execution Plan

- **Type:** Read-only gap audit + prioritized execution plan. **No application code, frontend, database,
  schema, migration, or configuration was changed.** The only artifact produced is this report.
- **Audit date:** 2026-10-11
- **Scope:** Phase 4A (historical data / patterns), Phase 4B (company-role blueprints: configuration,
  approval, versioning, snapshot pinning), Phase 4C (blueprint→Mock-Drive integration, question pools,
  candidate round lifecycle, evidence mapping, scoring, Student/TPO analytics).
- **Constraints honored:** no schema/migration/data/backup changes; no broad refactor; the recent
  question-pool topic-canonicalization fix was not touched; Phase F schema-drift remediation not started;
  nothing committed or staged.

---

## A. Method and evidence

The audit inspected code, tests, and the existing Phase 4 documents:
`docs/audits/HISTORICAL_ASSESSMENT_CONFIGURATION_AUDIT.md`,
`docs/audits/HISTORICAL_ASSESSMENT_CONFIGURATION_FIX.md`,
`docs/audits/PHASE_E_DATABASE_VERIFICATION_REPORT.md`, `docs/TPO_IMPLEMENTATION.md`,
`docs/implementation_plan for changes.md`.

Existing reported results were treated as claims and checked against source. In addition, the
self-contained (in-memory SQLite) Phase 4 suites were **run now**, one file per process (see §F). Reported
vs. run-now is distinguished throughout.

**Run-now evidence (per file, isolated process):**

| Test file | Result (run now) |
|---|---|
| `tests/test_company_historical_data.py` | 18 passed |
| `tests/test_historical_pattern_configuration.py` | 37 passed |
| `tests/test_historical_tpo_configuration_persistence.py` | 5 passed |
| `tests/test_historical_blueprint_route.py` | 2 passed |
| `tests/test_company_blueprint.py` | 11 passed |
| `tests/test_role_assessment_generation.py` | 34 passed |
| `tests/test_question_pool_generation.py` | 39 passed |
| `tests/test_mock_drive.py` | 17 passed |
| `tests/test_mock_drive_blueprint_integration.py` | 42 passed |
| `tests/test_competency_mapping.py` | 44 passed |
| `tests/test_assessment_lifecycle.py` | 5 passed |
| `tests/test_server_authoritative_time.py` | 12 passed |
| `tests/test_mock_drive_security_isolation.py` | 13 passed |
| `tests/test_interview_router.py` | 2 passed |
| `tests/test_mock_drive_interview_round_identity.py` | 2 passed |
| `tests/test_mock_drive_interview_bootstrap.py` | 4 passed |
| `tests/test_aptitude_blueprint_submit_flow.py` | 9 passed |
| `tests/test_m2b_practice_execution.py` | 29 passed |
| `tests/test_practice_independence.py` | 8 passed |

> **Harness caveat (verified now):** a *single* pytest process running 9 Phase 4A/4C files together
> produced `20 failed, 157 passed, 28 errors`, yet every one of those files passes **individually and in
> pairs/triples**. The combined-run failures are cross-module test pollution, not product defects. This
> must be resolved before a single-command sign-off is trustworthy (see **G0**).

---

## B. Verified Phase 4 completion status

| # | Requirement | Classification | Basis |
|---|---|---|---|
| 1 | Historical-data/pattern generation & persistence | **Implemented and verified** | `company_data_service.generate_pattern` (1071–1240); durable `tpo_configuration` ledger + `evidence_rounds` (schema in `HISTORICAL_ASSESSMENT_CONFIGURATION_FIX.md:7–63`); run-now tests 18/37/5/2 pass |
| 2 | Company/role blueprint config, approval, versioning, snapshot pinning | **Implemented and verified** | version bump + status reset `company_blueprint_service.py:260,291–292`; approval gates `:212–219` and `mock_drive_service._validate_and_attach_blueprint` (86–93); deep-copy snapshot `assessment_blueprint_service.py:15–81`; tests 11 + integration 42 |
| 3 | Mock Drive creation, publication, question-pool readiness, candidate assignment | **Partially implemented** | CRUD/publish/eligibility exist (`app/api/v1/mock_drive.py`, `mock_drive_service.py:317–435`), but publish gate is scoped to LLM provenance only (**G2**) and there is no pool-readiness check at start (**G3**); no assignment record |
| 4 | Exact counts, topic coverage, blueprint/version isolation, generic-fallback prevention | **Partially implemented** | Counts/topic-coverage/`(blueprint_id,version,round_type)` isolation verified (`test_question_pool_generation.py` 39; canonicalization fix intact); **generic-fallback leak remains** for blueprint-backed interview rounds (interview_router.py:297–341) |
| 5 | Round progression: aptitude → coding → technical interview → optional HR | **Implemented and verified** | Round order/identity in `mock_drive_service._enabled_rounds_in_order` (494–536), `_apply_round_key`/`_mock_round_key_for_round` (461–491); integration tests cover 3-round progression + advance; HR is optional via `selected_rounds` |
| 6 | Server-authoritative timing, refresh/resume, duplicate-session prevention, timeout recovery, finalization | **Partially implemented** | Timing/resume/dedup implemented & verified (12 + integration); **timeout recovery missing** (no auto-submit, no `TIME_EXPIRED`, no advance on expiry); finalize is not lock-guarded |
| 7 | Candidate result persistence & retrieval | **Partially implemented** | Per-round results persisted/retrievable; **no consolidated Mock-Drive result endpoint** (`GET /mock-drives/{id}/status` returns only `completed_rounds`/`status`) |
| 8 | Competency evidence mapping lifecycle & idempotency | **Implemented and verified** | 44 run-now tests; unique constraint `uq_competency_evidence_mapping`; idempotent `_add_if_new` (162–181); failure recording (308–344); reprocess endpoint |
| 9 | Competency scoring/normalization & defined semantics | **Missing — blocked by product decision** | No score computed/stored/exposed by design (`competency_mapping_service.py:11,203`; `competency.py:5–7`); `weight_pct` configured but unused |
| 10 | Student analytics and TPO analytics | **Student: verified; TPO: partially implemented** | Student `/report/analytics` + `/report/student-analytics` (implemented); TPO reuses `/report/admin/*` aggregates but no drive-scoped participation/distributions/competency-coverage module |
| 11 | Security isolation and legacy/practice compatibility | **Implemented and verified (runtime)** | `test_mock_drive_security_isolation.py` 13 passed, `test_practice_independence.py` 8 passed; caveat: 3 DB-bound tests + guard weakness (G0) |

---

## C. Prioritized gap register

Ordering: journey blockers first, then scoring and analytics. Each gap lists the user-visible requirement,
current implementation, exact defect, smallest fix, focused tests, and dependencies.

### G0 — Phase 4 test suites are not reliably runnable in a single process (sign-off blocker)

- **Requirement:** A final sign-off run (or CI command) must reliably exercise Phase 4.
- **Current:** Each listed suite is self-contained (in-memory SQLite + `dependency_overrides[get_db]`) and
  passes alone/pairs, but 3+ Phase 4A/4C files in one process yield 20 failures / 28 errors
  (repro: the 9-file command in §F). Additionally `EDI5_TESTING` is set with `os.environ.setdefault`
  (`tests/conftest.py:14,142`), so a pre-set `EDI5_TESTING=0` disables the DB guard; and
  `test_practice_independence_fix.py`, `test_practice_and_interview_modes.py`, `test_assessment_context.py`
  bind to the real application engine (`get_db()`/`SessionLocal()`), writing to the dev DB if the guard is
  defeated.
- **Exact defect:** Cross-module polluter is<｜begin▁of▁sentence｜>『≥3 specific modules together』(pairs clean); root cause is
  module-scoped global override/teardown interaction. Isolation guard is defeatable.
- **Smallest fix:** (a) Force `os.environ["EDI5_TESTING"] = "1"` (unconditional) in `conftest.py`;
  (b) convert the three DB-bound tests to self-contained SQLite fixtures (or mark them to require
  `EDI5_TEST_DATABASE_URL`); (c) make module-scoped `get_db` overrides symmetric/autouse-per-module and
  identify the polluting module pair. Do **not** change product code.
- **Focused tests:** `pytest -q tests/test_<each Phase 4 file>` individually; then a combined run must be
  green; `tests/test_db_isolation_guard.py` must stay green.
- **Dependencies:** none (pure test infra).

### G1 — Generic-fallback leak: blueprint-backed interview rounds can generate at candidate time

- **Requirement:** A published Mock-Drive round must serve the approved blueprint's validated question pool,
  never an ad-hoc/generic pool.
- **Current:** `_generate_question_pool_for_session` (`app/modules/interview/routers/interview_router.py:253–341`).
  If a complete generated pool exists, it is cloned with no LLM call (268–284). Otherwise, **when a blueprint
  snapshot + round config exist but the pool is incomplete**, it builds blueprint constraints (311–317) and
  calls `groq_service.generate_question_pool(...)` at candidate time, retrying once, and only 503s if still
  short (318–341). `groq_service` returns its hardcoded generic fallback bank on provider failure
  (`app/services/groq_service.py:398`).
- **Exact defect:** Blueprint-backed interview rounds silently fall back to candidate-time LLM/generic
  generation whenever no validated pool is present, instead of failing closed to the publish gate.
- **Smallest fix:** For a blueprint-backed interview round, if `complete_pool_for_round` returns no complete
  pool, return HTTP 503/409 immediately (no candidate-time LLM, no fallback bank). Restrict candidate-time
  generation to the non-blueprint (practice/legacy) path only.
- **Focused tests:** New test in `tests/test_mock_drive_blueprint_integration.py` (or a new
  `tests/test_interview_pool_no_fallback.py`): blueprint-backed interview round with no complete pool →
  `POST /interview/session/.../next` returns 503/409 and `groq_service.generate_question_pool` is **not**
  called (monkeypatch spy); non-blueprint session still generates.
- **Dependencies:** aligns with G2 (gate) and G3 (start check).

### G2 — Publish gate only covers LLM-provenance blueprints

- **Requirement:** Publishing a Mock Drive must be blocked until every enabled round that needs a
  pre-generated pool has a complete, validated pool.
- **Current:** `publish_mock_drive` (`app/services/mock_drive_service.py:317–394`) calls
  `question_pool_generation_service.publish_blocking_errors` (383). That function **returns `[]` early unless
  the snapshot provenance classification is `llm_role_assessment`** (`question_pool_generation_service.py:830–832`).
  For LLM blueprints, interview rounds always require a complete pool (`_seeded_round_feasible` returns
  `False` for interview rounds, 917), which is correct.
- **Exact defect:** Evidence-derived (non-LLM) blueprints with an enabled interview round are **not** gated,
  so they can be published with no interview pool and then hit G1 at candidate time.
- **Smallest fix:** Extend `publish_blocking_errors` so an enabled **interview** round requires a complete
  pool regardless of provenance (keep the seeded-feasibility escape for aptitude/coding on evidence
  blueprints). Interview rounds have no seeded bank, so this is safe and backward compatible for
  non-interview rounds.
- **Focused tests:** Extend `tests/test_mock_drive_blueprint_integration.py`: evidence blueprint + enabled
  interview round + no pool → publish returns 422 listing the missing pool; with a complete pool → publish
  succeeds.
- **Dependencies:** pairs with G1; product confirmation that interview pools are always required (D1).

### G3 — No pool-readiness check at Mock-Drive start

- **Requirement:** A candidate must not start a round that cannot be served from the approved pool.
- **Current:** `start_mock_drive_session` (`app/services/mock_drive_service.py:575–726`) validates status,
  eligibility and duplicates, then clones the pinned snapshot and creates rounds; it never checks pool
  readiness.
- **Exact defect:** Defense-in-depth gap: even if publish is bypassed (e.g., legacy data, force, or a future
  regression), a candidate can start and only fail mid-round.
- **Smallest fix:** In `start_mock_drive_session`, for blueprint-backed enabled interview rounds, verify a
  complete pool exists (reuse `complete_pool_for_round`); otherwise return 409/422 with an actionable message.
- **Focused tests:** `tests/test_mock_drive_blueprint_integration.py`: blueprint drive, enabled interview
  round, no pool → `POST /mock-drives/{id}/start` returns 4xx (not a session).
- **Dependencies:** G1/G2.

### G3b — Aptitude/coding rounds depend on seeded-bank feasibility (defense-in-depth)

- **Requirement:** An enabled aptitude/coding round whose blueprint topics the seeded bank cannot satisfy
  must not silently serve a short/generic set.
- **Current:** `_seeded_round_feasible` (`question_pool_generation_service.py:867–919`) is used only at
  publish for LLM blueprints. These rounds fall back to the seeded bank selection when no pool exists.
- **Exact defect:** Low/medium — safe only because publish blocks infeasible LLM rounds; an evidence
  blueprint with role-specific topics is not gated.
- **Smallest fix:** Fold into G2 (apply feasibility check for all provenances) — no separate code path.
- **Focused tests:** Covered by G2 tests.
- **Dependencies:** G2.

### G3b — (see above)

### G4 — No candidate assignment record

- **Requirement:** The system should be able to show who was assigned/eligible for a Mock Drive and their
  state (TPO analytics prerequisite).
- **Current:** Assignment is implicit — eligibility is computed on read (`_student_is_eligible`,
  `mock_drive_service.py:399–413`; `list_eligible_mock_drives`, 416–435). There is no `MockDriveAssignment`
  table; no roster is persisted.
- **Exact defect:** No durable per-candidate assignment, so per-drive participation cannot be reconstructed
  reliably except from `AssessmentContext` rows.
- **Smallest fix:** Prefer no new table for the immediate journey: derive a roster from existing
  `AssessmentContext(mock_drive_id, student_id, status)` (+ `StudentProfile` eligibility) for TPO analytics
  (G7). Only introduce a table if a product decision requires explicit invitation/assignment.
- **Focused tests:** Analytics test asserting roster counts match contexts.
- **Dependencies:** product decision D3.

### G5 — Timeout recovery / finalization gaps

- **Requirement:** Server-authoritative timing must recover deterministically: refresh/resume (works today),
  duplicate prevention (works today), and timeout must finalize/advance rather than strand the candidate.
- **Current:** Expiry is **lazy only** — no background sweeper. Specific defects:
  - `InterviewSession.completion_reason` documents `TIME_EXPIRED` (`app/models/interview.py:45`) but code only
    sets `ALL_TURNS_COMPLETE` (`interview_router.py:1440`) and `USER_SUBMITTED` (:1652).
  - On expiry `advance_mock_drive_round` marks round/session expired and raises `410` without advancing or
    finalizing (`mock_drive_service.py:1181–1195`).
  - Expired aptitude round → `get_user_active_round` returns None → submit 404 / finish `no_active_round`;
    drive stays `in_progress` forever (observed by `tests/test_server_authoritative_time.py`).
  - Coding `/run` & `/submit` auto-finalize the round on expiry but do **not** call `try_advance_mock_drive`.
- **Exact defect:** A timed-out round does not advance the Mock Drive or produce a final attempt result;
  `TIME_EXPIRED` is unreachable.
- **Smallest fix:** On detected expiry, finalize the round with `completion_reason = TIME_EXPIRED`, score
  whatever evidence exists, and invoke the existing `try_advance_mock_drive` (and `_finalize_mock_drive` when
  no rounds remain). Reuse existing finalize helpers; no schema change.
- **Focused tests:** Extend `tests/test_server_authoritative_time.py`: aptitude timeout → drive advances /
  finalizes with `TIME_EXPIRED`; coding timeout → advance invoked; interview timeout → `TIME_EXPIRED`
  persisted; finalize is idempotent on repeated expiry.
- **Dependencies:** product decision D2 (timeout semantics).

### G6 — No consolidated Mock-Drive result endpoint

- **Requirement:** A candidate (and TPO) must be able to retrieve the final Mock-Drive attempt result.
- **Current:** Per-round persistence exists (aptitude result, coding submissions, interview report).
  The only student Mock-Drive endpoints are `start`, `status`, `advance` (`app/api/v1/mock_drive.py:160–184`).
  `get_mock_drive_status` returns only `completed_rounds`/`status` (`mock_drive_service.py:912–1043`).
- **Exact defect:** No aggregate per-attempt result (round scores, totals, completion reason) at the
  Mock-Drive level.
- **Smallest fix:** Add `GET /mock-drives/{id}/result` returning persisted round summaries + session
  `total_score` + `completion_reason`, reusing existing per-round readers; no schema change.
- **Focused tests:** New integration test: after full attempt, result endpoint returns per-round scores and
  a total; candidate isolation enforced (other candidate 403/404).
- **Dependencies:** product decision D4 (result shape).

### G7 — Competency scoring/normalization not defined or exposed

- **Requirement:** Competency scoring/normalization semantics must be defined and implemented.
- **Current:** **Deliberately absent.** `competency_mapping_service.py:11,203` and `competency.py:5–7` state
  no score is computed or stored. Blueprint `weight_pct` is validated to sum to 100
  (`app/schemas/company_data.py:401–420`) but never consumed. `raw_metric` holds untouched evidence
  (aptitude `{is_correct, response_time, difficulty, reward, attempt_number}`; coding
  `{status, score, language, execution_time, memory_used}`). No API/schema exposes mappings or scores.
- **Exact defect:** No scoring model → no competency analytics.
- **Smallest fix:** Blocked. Requires a product decision (D1) on scale, per-evidence normalization,
  weighting (`weight_pct`), missing-evidence handling, and ambiguous-topic policy. Implementation should be
  a new pure function over `competency_evidence_mappings` + blueprint weights, exposed read-only. No schema
  change if computed on read; a cached column/table only if required.
- **Focused tests:** Deterministic unit tests over fixed `raw_metric` fixtures for each formula branch
  (weights, missing evidence, ambiguous topic).
- **Dependencies:** D1.

### G8 — TPO analytics missing drive-scoped metrics

- **Requirement:** Required TPO analytics for Mock Drives.
- **Current:** Shared admin aggregates exist and are TPO-accessible (`check_admin` allows `tpo`;
  `app/modules/report/routers/report_router.py:25–30`, `GET /report/admin/cohort-stats` :32,
  `/skill-gaps` :105, `/all-candidates` :211). No per-drive participation, score distribution, or
  competency-coverage module; `TPODashboard.jsx` calls only `cohort-stats` and shows "Coming Soon"
  placeholders.
- **Exact defect:** Mock-Drive-scoped TPO analytics absent.
- **Smallest fix:** Add a read-only `/tpo/mock-drives/{id}/analytics` that aggregates existing
  `AssessmentContext` (+ derived roster per G4) and `AssessmentRound.score`/`AssessmentSession.total_score`
  (competency coverage pending G7). No schema change.
- **Focused tests:** New service/router test with seeded contexts; assert participation, per-round score
  distribution, completion counts; RBAC (student 403).
- **Dependencies:** G4 (roster source), G7 (competency coverage), D3 (metric list).

### G8b — Frontend analytics field-contract mismatch (student analytics)

- **Requirement:** The Student analytics UI must render the backend payload.
- **Current:** `frontend/src/pages/Analytics.jsx` + `reportService.js` expect fields the backend does not
  return (`overview.readiness_tier`, `summary.overall_accuracy`, `coding.best_score`,
  `interviews.avg_score`; different `subjects`/`rounds`/`recommendation` keys).
- **Exact defect:** UI reads undefined fields (blank/broken tiles) though the endpoint is correct.
- **Smallest fix:** Reconcile the frontend mapping to `candidate_report_router.get_detailed_student_analytics`
  (or add computed aliases server-side). Frontend-only or thin server alias.
- **Focused tests:** Frontend unit test for the mapping util; manual verification of `/report/student-analytics`.
- **Dependencies:** none.

### G9 — Hardening (lower priority, non-blocking)

- Finalize lacks a row lock (`_finalize_mock_drive`, `mock_drive_service.py:1329–1371`); concurrent
  finalize/reprocess could race (mapping uses `with_for_update`, finalize does not).
- `generated_question_pools.status` has no DB CHECK (app-enforced only) — Phase F territory, do not touch now.
- `MockDrive.status` DB allows `active`/`completed` but code never sets them (`active` is never assigned;
  start accepts `completed` only for legacy). Dead statuses.
- No pattern `DELETE` and no historical-record edit endpoint; `ReviewPatternRequest.status` is a free-form
  string (no enum validation).
- Competency mapping retry has no cap/backoff and only fires on specific read paths.

---

## D. Smallest execution sequence

Order chosen so the end-to-end Mock-Drive journey is correct before scoring/analytics.

1. **G0** — Test-harness isolation (force `EDI5_TESTING`, convert 3 DB-bound tests, fix multi-module
   pollution). No product code.
2. **G2 + G3b** — Extend the publish gate to require a complete pool for enabled **interview** rounds for
   all provenances; apply seeded-feasibility to aptitude/coding for all provenances.
3. **G1** — Remove the candidate-time LLM/generic fallback for blueprint-backed interview rounds (fail
   closed).
4. **G3** — Pool-readiness check at `start_mock_drive_session`.
5. **G5** — Timeout finalization: set `TIME_EXPIRED`, score available evidence, advance/finalize; make it
   idempotent.
6. **G6** — Consolidated `GET /mock-drives/{id}/result`.
7. **G4** — Derived roster (analytics input; no new table unless D3 requires).
8. **G7** — Competency scoring/normalization (after D1).
9. **G8** — TPO Mock-Drive analytics.
10. **G8b** — Frontend analytics contract reconciliation.
11. **G9** — Hardening items as capacity allows (explicitly not Phase F).

Steps 1–4 are the minimal set that guarantees "a published round serves its approved pool and candidates
cannot be stranded by a missing pool." Step 5 closes the timeout journey. Steps 6–10 complete results,
scoring, and analytics.

---

## E. Blocking product decisions

| ID | Decision | Blocks |
|---|---|---|
| D1 | Competency **scoring model**: scale (e.g., 0–100), evidence→competency aggregation, use of `weight_pct`, missing-evidence policy, and ambiguous-topic policy. | G7, G8 (competency coverage) |
| D2 | **Timeout semantics**: auto-submit vs. mark-expired-and-advance; whether `TIME_EXPIRED` counts as a completed attempt; whether unanswered rounds score zero. | G5 |
| D3 | **TPO analytics metric set** (drive participation, score distribution, completion/funnel, competency coverage) and whether explicit assignment/invitation is required. | G4, G8 |
| D4 | **Mock-Drive result shape** (per-round score, total, completion reason, competency summary) and visibility (candidate-only vs. TPO). | G6 |
| D5 | Confirm **interview pools are mandatory** for every enabled interview round regardless of blueprint provenance. | G1, G2 |

---

## F. Focused tests required for final sign-off

**Harness (G0):** each Phase 4 file must pass individually (table in §A) *and* the combined command below
must be green:
`pytest -q tests/test_company_historical_data.py tests/test_historical_pattern_configuration.py tests/test_historical_tpo_configuration_persistence.py tests/test_historical_blueprint_route.py tests/test_company_blueprint.py tests/test_role_assessment_generation.py tests/test_question_pool_generation.py tests/test_mock_drive.py tests/test_mock_drive_blueprint_integration.py`
(and the competency/lifecycle/security suites).

**Per-gap focused tests:**

- **G1:** blueprint-backed interview with no complete pool → 503/409 and `groq_service.generate_question_pool`
  not called; non-blueprint session still generates. (`tests/test_mock_drive_blueprint_integration.py`, spy.)
- **G2/G3b:** evidence blueprint + enabled interview round + no pool → publish 422; with pool → publish 200;
  infeasible aptitude/coding topics → publish 422.
- **G3:** start with missing interview pool → 4xx, no session created.
- **G5:** aptitude/coding/interview timeout → round finalized with `TIME_EXPIRED`, drive advances/finalizes,
  repeated expiry idempotent (`tests/test_server_authoritative_time.py`).
- **G6:** `GET /mock-drives/{id}/result` returns per-round + total after a full attempt; cross-candidate
  access denied.
- **G7:** once D1 resolved — normalization/weight/missing/ambiguous unit tests over fixed `raw_metric` inputs.
- **G8:** TPO analytics endpoint: participation, distributions, completion counts, RBAC (student 403).
- **G8b:** frontend analytics mapping unit test against the real `/report/student-analytics` payload.
- **Regression guards that must stay green:** `test_question_pool_generation.py` (canonicalization),
  `test_mock_drive_security_isolation.py`, `test_practice_independence.py`, `test_competency_mapping.py`,
  `test_db_isolation_guard.py`.

---

## G. Explicitly out of scope for this plan

- Phase F model↔DB schema-drift reconciliation (JSON vs JSONB, index names, missing
  `coding_problems.blueprint_id` FK, `generated_question_pools.status` CHECK) — only revisit if a concrete
  Phase 4 blocker requires it, with approval.
- Broad refactors, dependency upgrades, UI redesign, unrelated cleanup.
- Any change to the working question-pool topic-canonicalization fix unless a reproducible Phase 4
  regression proves it responsible (none found in this audit).

---

## H. Key files and endpoints

- Historical/pattern: `app/api/v1/company_data.py`, `app/services/company_data_service.py`
  (`generate_pattern` 1071–1240; `_restore_tpo_configuration` 938; `review_pattern` 1566).
- Blueprint: `app/services/company_blueprint_service.py` (generate 124; approve 715; version bump 260/292),
  `app/models/company_data.py` (`CompanyBlueprint.status` 170, `version` 171),
  `app/services/assessment_blueprint_service.py` (snapshot adapters 15–81).
- Mock Drive: `app/api/v1/mock_drive.py`; `app/services/mock_drive_service.py`
  (`publish_mock_drive` 317, `publish_blocking_errors` call 383, `start_mock_drive_session` 575,
  `_enabled_rounds_in_order` 494, `advance_mock_drive_round` ~1159, `_finalize_mock_drive` 1329).
- Pools: `app/services/question_pool_generation_service.py` (`publish_blocking_errors` 808–865,
  `_seeded_round_feasible` 867–919), `app/services/question_pool_validation.py`.
- Interview fallback path: `app/modules/interview/routers/interview_router.py:253–341`;
  `app/services/groq_service.py:398`.
- Mapping: `app/services/competency_mapping_service.py`, `app/models/competency.py`,
  `app/models/assessment_context.py:95–108`.
- Analytics: `app/modules/report/routers/candidate_report_router.py` (`/report/analytics` 59,
  `/report/student-analytics` 381), `app/modules/report/routers/report_router.py` (`/report/admin/*`),
  `frontend/src/pages/Analytics.jsx`, `frontend/src/pages/TPODashboard.jsx`.
- Test harness: `tests/conftest.py:14,135–148`, `app/database/db.py`.

---

## I. Audit limitations

- No application, frontend, DB, schema, migration, or config change was made; only this report was created.
- Test evidence is from isolated in-memory-SQLite suites; no Postgres test DB was configured or exercised,
  so real-schema behavior (JSONB operators, constraints, FKs) is not covered by these runs.
- Some classifications rely on reading code paths that were not all invoked at runtime; runtime-only
  hypotheses (e.g., exact polluting module pair behind G0) are labelled as hypotheses.
- Per constraint, Phase 4 tests were not combined with the known dev-DB-bound tests
  (`test_practice_independence_fix.py`, `test_practice_and_interview_modes.py`, `test_assessment_context.py`).

**Awaiting approval before implementing any fix. No code will change until then.**
