# Aptitude Assessment Insights — Status Audit

**Audit date:** 2026-10-22
**Scope:** Determine what OpenCode implemented when replacing the Aptitude Topic
Performance table on the TPO Readiness dashboard with a compact Aptitude
Assessment Insights panel. Establish the precise current state of the
implementation before making any further changes.
**Auditor:** Kiro (post-interruption verification pass)
**Data policy:** No source files were modified during this audit phase. All
findings are read-only observations of the repository working tree and test
suite.

---

## 1. Reports and Audit Files Inspected

| File | Relevance |
|---|---|
| `edi5_department_readiness_audit_report.md` | EDI5 Phase 1 — Department Readiness single-bar investigation. Covers competency pipeline, not aptitude insights. |
| `edi5_phase2_final_report.md` | EDI5 Phase 2 — Section 2 UI cleanup and competency-readiness end-to-end validation. Covers readiness KPIs and blueprint configuration. |
| `docs/audits/PHASE_4_RECONCILED_GAP_REPORT.md` | Phase 4 scoring design. Not related to aptitude insights UI. |
| `docs/audits/PHASE_E_DATABASE_VERIFICATION_REPORT.md` | Database verification. Not related to aptitude insights UI. |
| `docs/TPO_IMPLEMENTATION.md` | TPO implementation notes. Reviewed; no aptitude insights status. |

**Finding:** No prior report specifically documents the Aptitude Assessment
Insights implementation. The two EDI5 reports confirm the Section 2 UI cleanup
(competency readiness) was completed, but neither mentions the aptitude topic
table replacement.

---

## 2. Git Working-Tree Status

`git log --oneline -1`: `6c870ed (HEAD -> feature/divesh)` — last committed
change predates the TPO Readiness page entirely.

`git status --short` shows:
- `TPOReadinessPage.jsx` — **untracked (`??`)**: created entirely by the
  previous OpenCode session; never committed.
- `frontend/src/utils/` — **untracked (`??`)**: all utility files
  (`readinessCharts.js`, `readinessCharts.test.js`, `readinessFormatting.js`,
  `readinessFormatting.test.js`, and others) were created by previous OpenCode
  sessions; never committed.
- All other working-tree modifications (`M`) are unrelated to this task and
  must not be disturbed.

**No aptitude-insights–specific commits exist.** All relevant code lives only
in the untracked working tree.

---

## 3. Files Already Modified or Created by OpenCode

| File | Change type | Relevance |
|---|---|---|
| `frontend/src/pages/TPOReadinessPage.jsx` | Created (untracked) | Contains the Aptitude Assessment Insights panel (section C) |
| `frontend/src/utils/readinessCharts.js` | Created (untracked) | Contains `toAptitudePerformance`, `toTopicPerformance`, `toTopicBars`, and all chart helpers |
| `frontend/src/utils/readinessCharts.test.js` | Created (untracked) | 40 tests — 39 pass, **1 fails** |
| `frontend/src/utils/readinessFormatting.js` | Created (untracked) | KPI derivation helpers — 20/20 tests pass |
| `frontend/src/utils/readinessFormatting.test.js` | Created (untracked) | 20 tests — all pass |
| `app/modules/report/routers/report_router.py` | Modified (untracked) | `get_readiness_overview` — contains full assessment-performance block including aptitude component |

---

## 4. Current Implementation Status

### 4.1 Aptitude Assessment Insights panel

Section C in `TPOReadinessPage.jsx` (line 864):

```jsx
{/* C. Aptitude Assessment Insights */}
<section className="glass-card rounded-2xl p-5"
         data-testid="aptitude-assessment-insights">
```

**Present and rendering all five required metrics:**

| Metric label | Source field | Verified present |
|---|---|---|
| Completed Eligible Assessments | `assessment?.components?.aptitude?.completed_rounds` | ✓ line 877 |
| Assessments With Results | `aptComp?.rounds_with_results` | ✓ line 878 |
| Assessments With Valid Scores | `aptComp?.rounds_with_valid_scores` | ✓ line 879 |
| Score Coverage | computed: `valid / completed × 100` (from `aptRow.coveragePct` or derived) | ✓ line 880 |
| Distinct Candidates With Valid Scores | `aptComp?.candidates` | ✓ line 881 |

**Status badge** — three-state: `Available` (emerald) / `Needs Review` (amber)
/ `Unavailable` (slate). Derived from `valid > 0` and `completed > 0 && valid === 0`.

**Dynamic summary sentence** (line 924):
```
Aptitude scores are available for {valid} of {completed} completed eligible
assessments. Coverage is {coveragePct.toFixed(1)}%. {candidates} distinct
candidate(s) have valid scores.
```

**Empty-state sentences** — three variants:
1. Zero completed: "No completed eligible aptitude assessments in scope."
2. Completed but no valid scores: mentions `withResults` to guide follow-up.
3. Completed with valid scores: the dynamic summary above.

**Reason line** — shown only when `aptComp.reason` is set and the panel is
unavailable.

### 4.2 Old aptitude topic table

The previous long topic-performance table (`data-testid="topic-performance"`)
has been **removed** from the dashboard section. Only a code comment remains:

```js
// topics removed - replaced by Aptitude Assessment Insights
```

`toTopicPerformance` remains exported from `readinessCharts.js` but is no
longer imported or called in `TPOReadinessPage.jsx`.

### 4.3 Coding and Interview Assessment Insights

Preserved in section D (`data-testid="assessment-type-status"`). The aptitude
row is filtered out (`evidenceRows.filter(row => row.type !== 'aptitude')`) so
aptitude no longer appears in this section — it appears only in section C.

### 4.4 Backend data flow

`GET /report/admin/readiness/overview` → `get_readiness_overview` →
`_assessment_component('aptitude')` returns:

```
assessment_performance.components.aptitude = {
  completed_rounds,    // AssessmentRound.status='completed', round_type='aptitude'
  rounds_with_results, // rounds with ≥1 graded AptitudeAttempt (is_correct IS NOT NULL)
  rounds_with_valid_scores, // rounds where correct/responses×100 could be computed
  candidates,          // len({e["student_id"] for e in scored_by_type["aptitude"]})
  avg_score,           // mean of per-round accuracy scores
  available,           // bool: any valid scores exist
  reason,              // why unavailable, if so
}
```

Coverage row also available at
`assessment_performance.summary.evidence_coverage.by_type[type=aptitude]`
(used by `toEvidenceCoverageRows`). The panel reads from both sources with
fallback logic.

---

## 5. Backend Schema — Aptitude Data Model

| Question | Answer | Evidence |
|---|---|---|
| What entity represents a completed aptitude assessment? | `AssessmentRound` with `round_type='aptitude'` and `status='completed'` | `app/models/assessment.py:100,103` |
| How is completed distinguished from incomplete? | `AssessmentRound.status = 'completed'` (lifecycle: pending→active→completed\|terminated) | `app/models/assessment.py:88` |
| Where are results and scores persisted? | `AptitudeAttempt.is_correct` (per question); no round-level score column used — score computed from graded attempts | `app/models/aptitude.py:115`, `report_router.py:1408–1420` |
| What makes a score valid and countable? | Round has ≥1 `AptitudeAttempt` with `is_correct IS NOT NULL`; score = correct/responses×100 | `report_router.py:1410–1420` |
| Can one assessment have multiple topic rows? | Yes — topic rows are per `AptitudeTopic.name` in `topic_performance`; the assessment component counts rounds not topics | `report_router.py:1882–1913` |
| How are candidates deduplicated? | `len({e["student_id"] for e in scored_by_type["aptitude"]})` — Python set | `report_router.py:1440–1443` |
| Are ungraded questions excluded from accuracy? | Yes — `.filter(AptitudeAttempt.is_correct.isnot(None))` excludes NULL | `report_router.py:1340` |
| Can results be associated with reporting period? | Yes — period filter on `round.completed_at` with fallback to session/context timestamps | `report_router.py:1315–1326` |
| Are duplicate/retaken assessments handled? | Each round counted once; candidates deduped by set; no double-counting possible | `report_router.py:1408` |
| Does existing API provide assessment-level metrics? | Yes — `assessment_performance.components.aptitude` provides all five | Verified above |

---

## 6. Requirement-by-Requirement Status Table

| Requirement | Status | Evidence | Remaining Work |
|---|---|---|---|
| Audit reports and existing work | COMPLETE | All available reports inspected; no prior aptitude-insights–specific report found | None |
| Inspect Git changes | COMPLETE | `git status` inspected; `TPOReadinessPage.jsx` and utils are untracked | None |
| Verify aptitude data model | COMPLETE | `AptitudeAttempt`, `AssessmentRound`, `AssessmentSession`, `AssessmentContext` models read; `_assessment_component('aptitude')` traced | None |
| Verify assessment-level metric definitions | COMPLETE | All five metrics directly supportable from existing `assessment_performance.components.aptitude` block | None |
| Replace aptitude topic table | COMPLETE | `data-testid="topic-performance"` removed; comment confirms intentional replacement | None |
| Match coding/interview panel styling | COMPLETE | Section C uses identical glass-card, metric-card grid, badge, and summary-sentence pattern as section D | None |
| Display availability status badge | COMPLETE | Three-state badge: Available / Needs Review / Unavailable — derived from `valid > 0` and `completed > 0 && valid === 0` | None |
| Display five metrics | COMPLETE | All five metric cards present and wired to `aptComp` / `aptRow` fields | None |
| Calculate coverage correctly | COMPLETE | `valid / completed × 100`; uses `aptRow.coveragePct` when available, falls back to inline calculation; zero-denominator yields `null` (renders as `—`) | None |
| Deduplicate candidates and assessments | COMPLETE | Backend deduplicates in `_assessment_component`; frontend reads the resulting `candidates` count | None |
| Dynamic summary sentence | COMPLETE | Populates from `valid`, `completed`, `coveragePct`, `candidates`; three distinct empty/partial/full variants | None |
| Loading, empty, unavailable and error states | COMPLETE | Page-level loading skeleton, error banner, empty-data guard, panel-level three-state output all present | None |
| Preserve coding and interview panels | COMPLETE | Section D filters out aptitude row (`row.type !== 'aptitude'`); coding and interview panels unaffected | None |
| Backend and frontend tests | **PARTIAL** | `readinessFormatting.test.js`: 20/20 pass. `readinessCharts.test.js`: **39/40 pass, 1 FAIL**. Failing test: `'the page renders the assessment evidence sections and exports them'` — asserts `data-testid="topic-performance"` and `toTopicPerformance(assessment)` still exist in the page (they were intentionally removed). Test was not updated when the table was replaced. | **Fix the stale test assertion** |
| Authenticated UI verification | NOT VERIFIED | No automated browser test; server not started during audit. Manual verification steps provided below. | Run server and check the page in a browser |

---

## 7. Tests Executed and Results

| Suite | Command | Result |
|---|---|---|
| readinessFormatting.test.js | `node --test frontend/src/utils/readinessFormatting.test.js` | **20 passed, 0 failed** |
| readinessCharts.test.js | `node --test frontend/src/utils/readinessCharts.test.js` | **39 passed, 1 failed** |

### Failing test details

**Test name:** `the page renders the assessment evidence sections and exports them`
**File:** `frontend/src/utils/readinessCharts.test.js`, line 462
**Root cause:** Two stale assertions check for content that was **intentionally
removed** when OpenCode replaced the aptitude topic table with the Aptitude
Assessment Insights panel:

```js
assert.match(pageSource, /data-testid="topic-performance"/);   // line 466 — FAILS
assert.match(pageSource, /toTopicPerformance\(assessment\)/);  // line 474 — FAILS
```

`toTopicPerformance` is still exported from `readinessCharts.js` and remains
used by the backend's `topic_performance` block, but the page no longer renders
it as a visible table — the aptitude insights panel replaced it. The test was
written before the replacement and was not updated.

**Required fix:** Update the two stale assertions to verify the new panel instead:
- Replace the `topic-performance` testid check with `aptitude-assessment-insights`
- Replace the `toTopicPerformance` call check with either `toAptitudePerformance`
  (already asserted) or remove the stale line.

---

## 8. Specific Blockers and Risks

| Item | Severity | Description |
|---|---|---|
| Stale test assertions | **Medium** | 1 test fails due to outdated expectations about removed content. Blocks a clean test run. Fix is small and contained to `readinessCharts.test.js`. |
| `toTopicPerformance` unused in page | Low | Exported but not called in the JSX. Not a runtime error. Could be removed from the page import or left as a library export. No action required for the panel. |
| Authenticated UI verification | Low | Cannot verify browser rendering without a running dev server. Manual steps provided below. |
| `safeAssessmentKey` export order | Info | `export { safeAssessmentLabel, safeAssessmentKey }` appears before the function declarations. Valid in ES modules (function declarations are hoisted). Not a bug. |

---

## 9. Manual Authenticated UI Verification Steps

Since automated browser testing was not available during this audit:

1. Start the backend: `uvicorn app.main:app --reload` (or the project's normal start command).
2. Start the frontend: `npm run dev` from `frontend/`.
3. Sign in with a TPO or admin account.
4. Navigate to `/tpo/readiness`.
5. Verify:
   - Section 2 → "Assessment Completion & Scoring" contains subsection C titled **"Aptitude Assessment Insights"**.
   - The old aptitude topic table (rows of Topic / Questions / Correct / Accuracy) is **not** present.
   - The five metric cards display: Completed Eligible Assessments, Assessments With Results, Assessments With Valid Scores, Score Coverage, Distinct Candidates With Valid Scores.
   - The status badge shows Available / Needs Review / Unavailable based on real data.
   - The dynamic summary sentence at the bottom of section C matches the metric card values.
   - Coding Assessment Insights and Interview Assessment Insights (section D) are still present and unchanged.

---

## 10. Prioritised Implementation Plan (Remaining Work Only)

Only one item is genuinely unfinished:

### Priority 1 — Fix the stale test (REQUIRED for clean test run)

**File:** `frontend/src/utils/readinessCharts.test.js`
**Change:** In the test `'the page renders the assessment evidence sections and exports them'`:
- Remove or replace `assert.match(pageSource, /data-testid="topic-performance"/)` — the topic-performance section was intentionally removed.
- Remove or replace `assert.match(pageSource, /toTopicPerformance\(assessment\)/)` — the call was intentionally removed.
- Add a replacement assertion that verifies `data-testid="aptitude-assessment-insights"` is present (the new panel that replaced the topic table).

**Why:** The test documents page structure. It should reflect the current intended state (Aptitude Assessment Insights panel) not the superseded state (topic table).

### Priority 2 — Authenticated browser verification (RECOMMENDED)

Follow the manual steps in section 9 to confirm the panel renders correctly against live backend data.

### Nothing else is missing

- Backend aggregation: complete and correct.
- Frontend panel: complete with all five metrics, badge, summary, and states.
- Old topic table: removed.
- Coding/interview panels: preserved and unaffected.
- No schema changes needed.
- No new API contract changes needed.

---

*This report was produced by read-only inspection of the repository working tree and test suite. No source files were modified during the audit.*

---

## POST-IMPLEMENTATION ADDENDUM

**Completed by:** Kiro
**Date:** 2026-10-22
**Basis:** Audit findings above; all changes made after Phase 1 was fully documented.

---

### What OpenCode Had Already Completed (verified in source)

| Item | Status at audit time |
|---|---|
| Aptitude Assessment Insights panel (section C, `data-testid="aptitude-assessment-insights"`) | COMPLETE — all five metric cards, status badge, and dynamic summary sentence present |
| Old aptitude topic table removed | COMPLETE — `data-testid="topic-performance"` absent; comment documents the replacement |
| Aptitude row filtered from section D (coding/interview) | COMPLETE — `evidenceRows.filter(row => row.type !== 'aptitude')` |
| Backend `_assessment_component('aptitude')` aggregation | COMPLETE — `completed_rounds`, `rounds_with_results`, `rounds_with_valid_scores`, `candidates`, `avg_score` all present in API response |
| `readinessFormatting.test.js` | COMPLETE — 20/20 tests passing |
| `readinessCharts.test.js` | **PARTIAL** — 39/40 passing; 1 stale test not updated after topic table removal |

### What Remained Incomplete

Exactly one item:

`readinessCharts.test.js` — test `'the page renders the assessment evidence sections and exports them'` contained two stale assertions that checked for content intentionally removed by OpenCode:
- `assert.match(pageSource, /data-testid="topic-performance"/)` — the topic table was removed
- `assert.match(pageSource, /toTopicPerformance\(assessment\)/)` — the call was removed from the page

### What Kiro Changed

**File:** `frontend/src/utils/readinessCharts.test.js`
**Change:** Replaced the two stale assertions with accurate assertions for the new panel:
- `assert.match(pageSource, /data-testid="aptitude-assessment-insights"/)` — verifies the new panel is present
- `assert.match(pageSource, /Aptitude Assessment Insights/)` — verifies the panel heading

Added a comment explaining why the original assertions were replaced (intentional removal of the topic table in EDI5).

No other files were changed.

### Metric Sources and Definitions (post-verification)

All five displayed metrics read from `assessment_performance.components.aptitude` in the readiness overview API response, with fallback to `assessment_performance.summary.evidence_coverage.by_type[aptitude]`:

| Metric | API field | Definition |
|---|---|---|
| Completed Eligible Assessments | `components.aptitude.completed_rounds` | `AssessmentRound.status='completed', round_type='aptitude'` within reporting period |
| Assessments With Results | `components.aptitude.rounds_with_results` | Completed rounds with ≥1 graded `AptitudeAttempt` (`is_correct IS NOT NULL`) |
| Assessments With Valid Scores | `components.aptitude.rounds_with_valid_scores` | Rounds where `correct / responses × 100` was computable |
| Score Coverage | Derived: `valid / completed × 100` | Uses `aptRow.coveragePct` if present; zero denominator → `—` (never NaN) |
| Distinct Candidates With Valid Scores | `components.aptitude.candidates` | `len({e["student_id"] for e in scored_by_type["aptitude"]})` — Python set deduplication |

### Tests Executed and Results (post-implementation)

| Suite | Command | Result |
|---|---|---|
| readinessCharts.test.js | `node --test frontend/src/utils/readinessCharts.test.js` | **40/40 passed** (was 39/40) |
| readinessFormatting.test.js | `node --test frontend/src/utils/readinessFormatting.test.js` | **20/20 passed** (unchanged) |
| All frontend util tests | `node --test frontend/src/utils/*.test.js` | **94/94 passed** |
| Frontend build | `npm run build` (vite) | **Build succeeded** — 2566 modules, no errors (pre-existing chunk-size warning unrelated) |
| test_competency_scoring.py | `.venv pytest tests/test_competency_scoring.py` | **22/22 passed** |
| test_db_isolation_guard.py | `.venv pytest tests/test_db_isolation_guard.py` | **4/4 passed** |
| test_readiness_overview.py | `.venv pytest tests/test_readiness_overview.py` | **Did not complete** — hangs on DB fixture setup (pre-existing environment constraint, documented in `edi5_department_readiness_audit_report.md`; not caused by this change) |

### Authenticated UI Verification

Not performed — dev server was not started during this session. Manual verification steps remain as documented in section 9 of this report.

### Remaining Blockers and Known Limitations

| Item | Severity | Notes |
|---|---|---|
| `test_readiness_overview.py` hangs in this environment | Low | Pre-existing constraint; suite passed 49/49 in the EDI5 Phase 1 report when DB fixtures resolved. Not a regression from this change. |
| Authenticated browser verification not performed | Low | Manual steps provided in section 9. |
| `toTopicPerformance` exported but unused in page | Info | Remains available as a library export for any future consumer. Not a runtime issue. |

### Final Git Working-Tree Summary

Files modified by this session (both untracked — created by prior OpenCode sessions, not yet committed):

- `docs/audits/APTITUDE_ASSESSMENT_INSIGHTS_STATUS_AUDIT.md` — created (this report)
- `frontend/src/utils/readinessCharts.test.js` — two stale assertions replaced with correct ones

No committed files were modified. No unrelated working-tree changes were disturbed.

## Final Verification Addendum — 2026-10-22

This addendum records the final narrow verification pass. It supersedes earlier
statements in this report that the readiness suite was hanging or that its
stale assertions remained unfixed. No application source was changed during
this pass.

### Verified in source

- `frontend/src/pages/TPOReadinessPage.jsx` contains the Aptitude Assessment
  Insights section with all five requested cards: completed assessments,
  assessments with results, assessments with valid scores, coverage, and
  distinct candidates with valid scores. Its summary sentence uses those same
  API-derived values and has separate empty, no-valid-score, and scored states.
- Coverage is read from the per-type API coverage row, with a local
  `valid / completed` fallback guarded for `completed === 0`. The formatting
  helper `formatCoveragePercent` returns `null` for a zero denominator, and
  the page renders an em dash for unavailable coverage.
- The old topic performance table is absent from the page: no
  `data-testid="topic-performance"` or `toTopicPerformance(assessment)` call
  exists there. The retained topic-performance data remains an API/helper
  capability, not this page's aptitude panel.
- The coding/interview status section remains present and consumes rows filtered
  to exclude aptitude; it still labels the coding and interview panels
  separately.
- `app/modules/report/routers/report_router.py` builds the aptitude component
  from completed aptitude rounds and graded `AptitudeAttempt` rows. It reports
  completed rounds, rounds with results, valid scores, distinct candidate count,
  average score, availability, and a reason when evidence is unavailable.
  Null `is_correct` responses are excluded from the scoring aggregate.

### Verified by tests

- `node --test frontend/src/utils/readinessCharts.test.js frontend/src/utils/readinessFormatting.test.js`:
  **60 passed, 0 failed**.
- `npm.cmd test` from `frontend/` (all configured frontend utility tests):
  **94 passed, 0 failed**.
- `.venv\\Scripts\\python.exe -m pytest tests/test_readiness_overview.py -q -x`:
  **58 passed, 0 failed in 140.47 seconds**. This includes authenticated
  TestClient coverage for the empty/unavailable response and a scored aptitude
  response (one completed round, one with results, one valid score, one
  candidate, 100% coverage).
- Repeated with `--durations=10 -p no:cacheprovider`:
  **58 passed, 0 failed in 145.13 seconds**. The slowest reported individual
  test took 4.93 seconds; the next nine took 2.81–4.51 seconds. The module's
  autouse `_fresh_schema` fixture drops and recreates its in-memory SQLite
  schema for every test. This run completed; available evidence points to
  cumulative suite/fixture cost rather than a single test hanging during
  fixture setup. No pytest timeout configuration was found in the inspected
  repository configuration. A Starlette/httpx deprecation warning was emitted;
  the first run also reported that pytest's cache could not write in this
  environment. Neither warning failed the tests.
- Frontend tests exercise zero-denominator formatting (`null`/em dash) and
  empty evidence rows; backend empty-database coverage asserts zero completed
  rounds, zero valid scores, and an explicit unavailable reason.

### Live API and authenticated UI

- **Not verified against the live development API.** No backend port was
  listening during inspection. The passing API checks above use the test
  module's authenticated FastAPI `TestClient` and in-memory SQLite database;
  they are not live-development-database results.
- **Authenticated browser UI not verified.** No frontend/backend development
  server was running; the repository's `test:e2e` script explicitly reports
  that no E2E tests are configured, and Playwright/Puppeteer packages and
  browser executables were unavailable in this environment. The project's
  documented dev-server commands exist, but no authorized browser session or
  existing authenticated test mechanism is available here. Therefore the
  visual comparison of the five cards and dynamic summary against a real live
  API response remains outstanding.

### Working tree preservation

The working tree contains many pre-existing modified and untracked files,
including the readiness page, utility files, backend report router, tests, and
unrelated Phase work. They were inspected and left in place. This verification
changed only this audit report; it did not reset, clean, stash, or discard any
working-tree content.
