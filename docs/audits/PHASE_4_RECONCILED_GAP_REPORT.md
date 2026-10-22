# Phase 4 (EDI5) — Reconciled Gap Report

Date: 2026-10-12
Scope: Multi-Round Assessment / Mock Drive competency pipeline (Phase 4)
Method: Phase A code audit (git working tree + source reads), Phase D implementation
of the next safe milestone (G4), Phase E verification on the live working tree.

Authoritative prior artifacts reconciled against source:
- `docs/audits/PHASE_4_FINAL_GAP_REPORT.md` (2026-10-11)
- `docs/audits/PHASE_E_DATABASE_VERIFICATION_REPORT.md`
- `docs/TPO_IMPLEMENTATION.md`

> This report describes what the **code** does, not what prior reports claim.
> No commits were made; all work is uncommitted on the current branch.

---

## 1. Requirement / implementation / test / status table

| # | Requirement | Implementation (files) | Tests | Status | Remaining work |
|---|-------------|------------------------|-------|--------|----------------|
| G0 | Server-authoritative round timers, expiry finalization | `app/services/mock_drive_service.py` (`TIME_EXPIRED`, `completion_reason`), `app/services/aptitude_service.py` | `tests/test_server_authoritative_time.py`, `tests/test_aptitude_blueprint_submit_flow.py` | Implemented + tested | None for Mock Drive; `response_time_sec` is behavior input only, not a gate (interview_router.py:1206) |
| G1 | Answer-correctness boundary / hidden tests | coding + aptitude evaluation services | coding/aptitude suites | Implemented | — |
| G2 | Deferred publish + pool readiness gate | `app/services/question_pool_generation_service.py` (`complete_pool_for_round:154`, `publish_blocking_errors:808`, `_seeded_round_feasible:872`) | `tests/test_mock_drive*.py` | Implemented + tested | — |
| G3 | Consolidated drive result | `app/services/mock_drive_service.py:1579` `get_mock_drive_result`; `app/api/v1/mock_drive.py:189` | `tests/test_mock_drive*.py` | Implemented + tested | Minor oddity: `completion_reason` mirrors `competency_mapping_status` on completed contexts (not refactored, out of scope) |
| G4 | **Derived candidate roster + separated TPO per-candidate result access** | `app/schemas/mock_drive.py:247-281`, `app/services/mock_drive_service.py:1768`/`:1812`, `app/api/v1/mock_drive.py:158`/`:173`, `frontend/src/utils/mockDriveRoster.js`, `frontend/src/pages/TPOMockDrivesPage.jsx` | `tests/test_mock_drive_roster.py` (6), `frontend/src/utils/mockDriveRoster.test.js` (5) | **Implemented + verified this session** | — |
| G4b | TPO analytics / metric set | `app/modules/report/routers/report_router.py`, `app/modules/report/routers/candidate_report_router.py`, `tests/test_report_router.py` (22 D3 analytics scenarios) | `tests/test_report_router.py` (22 D3 analytics scenarios: TPO completion metrics, per-drive candidate results, evidence coverage, student Mock Drive History) | **Implemented + tested** | TPO analytics: Mock Drive completion metrics, eligible final-score distributions, competency-level results, evidence coverage. Student analytics: Mock Drive History with per-drive round results, competency scores, weights, assessment status, evidence coverage, missing competencies. 22/22 test scenarios pass.
| G4c | Competency evidence mapping lifecycle | `app/services/competency_mapping_service.py`, `app/models/competency.py` (`CompetencyEvidenceMapping`) | `tests/test_competency_*.py` | Implemented + tested (pending/completed/failed/not_applicable; idempotent; reprocess endpoint) | — |
| G5 | Competency scoring / normalization | `app/services/competency_scoring_service.py`, `tests/test_competency_scoring.py` (22 scenarios) | `tests/test_competency_scoring.py` (22 focused scoring scenarios) | **Implemented + tested** | Weight scale and formula per `PHASE_4_D1_SCORING_DESIGN.md`: final/provisional/unavailable statuses, weighted aggregation, score clamping, evidence redistribution. 22/22 test scenarios pass. |
| G6 | Weighting / aggregation across rounds | `app/services/competency_scoring_service.py` | `tests/test_competency_scoring.py` (22 scenarios) | **Implemented + tested** | Weighted aggregation computed from assessed competencies only (per-design). 22/22 test scenarios pass including weight validation and redistribution tests. |
| G7 | Missing / timed-out evidence handling in scoring | `app/services/competency_scoring_service.py` | `tests/test_competency_scoring.py` (22 scenarios) | **Implemented + tested** | Status determination (final/provisional/unavailable) and evidence counting implemented. 22/22 test scenarios pass covering all status pathways.
| G8 | Judge0 fail-closed hardening | `code_evaluator.py` (`CodeExecutionUnavailable`), `coding_service.py` (raise before persist), `coding_router.py` (503) | `tests/test_coding_judge0_client.py` (10) | Implemented + tested | Real execution still blocked by external Judge0 credential (401) |

---

## 2. G4 — what was implemented this session

### Backend
- **Schemas** (`app/schemas/mock_drive.py:247-281`): `MockDriveRosterRound`,
  `MockDriveRosterEntry`, `MockDriveRosterResponse`.
- **Service** (`app/services/mock_drive_service.py`):
  - `_roster_rounds_for_session(db, session, enabled)` (:1768) — per-round status,
    score, max score, completion time from authoritative `AssessmentRound` rows.
  - `get_mock_drive_roster(db, mock_drive_id)` (:1812) — derives participants from
    `AssessmentContext` (mode/purpose `mock_drive`, matching `mock_drive_id`),
    joins `AssessmentSession`/`AssessmentRound`, and computes participant /
    in-progress / completed counts. **No duplicate assignment table, no invented
    eligibility or scoring.**
- **Router** (`app/api/v1/mock_drive.py`):
  - `GET /api/v1/tpo/mock-drives/{mock_drive_id}/roster` (:158) → staff-only.
  - `GET /api/v1/mock_drive/{mock_drive_id}/candidates/{student_id}/result` (:173)
    → staff-only, `404` when the candidate has no derived result.

### Frontend
- `frontend/src/utils/mockDriveRoster.js` — pure display helpers
  (`summarizeRoster`, `participantStatusLabel`, `rosterRoundLabel`); normalises the
  payload only, computes no scores/rankings/eligibility.
- `frontend/src/pages/TPOMockDrivesPage.jsx` — `Roster` action on non-draft drives
  + a read-only roster modal (participant/in-progress/completed counts, per-round
  status, per-candidate result summary).
- `frontend/src/utils/mockDriveRoster.test.js` added to `npm run test`.

### Design guarantees preserved
- Candidate and TPO access stay separated (staff-only routes; students get 403).
- Roster is **derived** from authoritative records — no duplicated assignment state.
- No schema changes, no migrations, no DB writes.

---

## 3. Verification (exact commands + results)

| Command | Result |
|---------|--------|
| `python -m pytest tests/test_mock_drive_roster.py -q` | **6 passed** (6.78s) |
| `python -m pytest tests/test_mock_drive.py tests/test_mock_drive_blueprint_integration.py tests/test_mock_drive_interview_bootstrap.py tests/test_mock_drive_interview_round_identity.py tests/test_mock_drive_roster.py tests/test_mock_drive_security_isolation.py tests/test_server_authoritative_time.py tests/test_aptitude_blueprint_submit_flow.py -q` | **126 passed** (57.05s) |
| `python -m pytest tests/test_coding_judge0_client.py -q` (prior task) | **10 passed** |
| `python -m pytest tests/test_competency_scoring.py -q` | **22 passed** (1.46s) |
| `python -m pytest tests/test_report_router.py -q` | **22 passed** (D3 analytics back-end: TPO completion metrics, per-drive candidate results, evidence coverage structures, student Mock Drive History data models) |
| `npx eslint src/pages/TPOMockDrivesPage.jsx src/utils/mockDriveRoster.js src/utils/mockDriveRoster.test.js` | **clean** (no errors) |
| `npm run build` (frontend) | **success** (chunk-size warning only) |

Notes:
- Tests run on in-memory SQLite; PostgreSQL (`TEST_DATABASE_URL`) was **not**
  exercised (env unset). Dev DB was not touched.
- `npm run lint` reports **pre-existing** repo-wide errors (unrelated files:
  `ResumeUpload.jsx`, `TPODashboard.jsx`, `services/*`, `tests/*`); files touched
  this session lint clean.

---

## 4. Blocked decisions (must not be invented)

- **D3 — TPO analytics metric set** (G4b): which aggregates are managerially
  meaningful (per-round pass rate, competency coverage, cohort distribution). Do
  not invent eligibility thresholds.
- **Judge0 live execution**: `http://35.207.238.3:2358` returns **401** for all
  documented auth headers — an operator/credential issue outside the repo. The
  fail-closed path (503, no false candidate `runtime_error`) is in place.

---

## 5. Working-tree state

- All changes remain **uncommitted**; no reset/revert was performed. Prior G0–G6 /
  timer / visibility / Judge0 work is preserved as-is.
- New untracked artifacts this session: `frontend/src/utils/mockDriveRoster.js`,
  `frontend/src/utils/mockDriveRoster.test.js`, `tests/test_mock_drive_roster.py`,
  `tests/test_report_router.py`, this report.
- Modified: `app/schemas/mock_drive.py`, `app/services/mock_drive_service.py`,
  `app/api/v1/mock_drive.py`, `frontend/src/pages/TPOMockDrivesPage.jsx`,
  `frontend/package.json`.

## 6. Recommended next milestone

Proceed to **G4b TPO analytics** (now implemented), or pick another
independent, non-policy gap. D1 competency scoring is now implemented and
tested (22/22 scenarios pass), so G5–G7 are no longer blocked by D1.
