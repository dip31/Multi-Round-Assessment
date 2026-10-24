# TPO Dashboard and Feature Fix Report

## Summary

Implemented focused data accuracy and visibility fixes across the TPO dashboard, analytics, readiness, Mock Drive roster, and assessment-attempt workflow. Existing dashboard and backend authorization rules were retained. The new assessment view uses the existing TPO drive list and per-drive roster endpoints; it adds no API or schema.

## Changes

- **Dashboard metrics:** missing cohort/drive data is displayed as unavailable instead of zero. Candidate eligibility is tri-state (eligible, ineligible, unknown) so missing CGPA/backlog/department data is not treated as a failed or passed criterion. Institution-wide average is calculated using completed sessions and labeled with its global scope.
- **Drive activity:** dashboard roster coverage now reports the checked sample and failures instead of implying all drives were inspected. Empty activity and unavailable/partial results are distinguished.
- **Analytics diagnostics:** the existing analytics response now includes aggregate competency coverage diagnostics: eligible contexts, missing sessions/snapshots/configuration/evidence, mapping states, final/provisional scores, and scoring errors. The UI explains that missing countable evidence can include unmapped or non-countable evidence and is not a zero score. Analytics exports are described as browser-generated filtered downloads.
- **Readiness:** removed display-only demo score substitution from the drive table. The page now renders API values directly and describes missing score fields as unavailable/no scores.
- **Mock Drive roster:** round scores and score maxima are exposed only when the corresponding persisted evaluation evidence is present. This preserves legitimate zero scores while keeping lifecycle completion without an evaluated submission unavailable.
- **Completion reporting:** cohort stats now include completed session count and calculate round completion from distinct students and canonical round types, avoiding repeated sessions/round rows inflating student completion.
- **Failure states:** Mock Drive list and roster views distinguish API failure from a successful empty response.

## Data flow and authorization

- The assessment page calls existing `GET /api/v1/tpo/mock-drives` and `GET /api/v1/tpo/mock-drives/{id}/roster`; no new backend route or request contract was added.
- Existing `RoleRoute` limits the page to TPO/admin, and the roster endpoint's existing TPO/admin check remains authoritative.
- TPO analytics continue to use existing institution-wide report routes. Faculty-specific route and department authorization changes were not part of this implementation.
- No database schema, migration, scoring formula, or assessment-generation logic was changed.

## Files changed for this task

- `app/modules/report/routers/report_router.py`
- `app/modules/report/schemas/report_schema.py`
- `app/services/mock_drive_service.py`
- `frontend/package.json`
- `frontend/src/App.jsx`
- `frontend/src/components/TPOLayout.jsx`
- `frontend/src/pages/TPODashboard.jsx`
- `frontend/src/pages/TPOAnalyticsPage.jsx`
- `frontend/src/pages/TPOMockDrivesPage.jsx`
- `frontend/src/pages/TPOReadinessPage.jsx`
- `frontend/src/utils/candidateEligibility.js` (new)
- `frontend/src/utils/candidateEligibility.test.js` (new)
- `frontend/src/utils/readinessCharts.test.js`
- `tests/test_mock_drive_roster.py`
- `tests/test_report_router.py`

Other pre-existing modified and untracked work in the repository was preserved. `git diff --check` completed without whitespace errors; Git printed only line-ending conversion notices.

## Verification

- `python -m compileall -q app` — passed.
- `python -m pytest tests/test_report_router.py tests/test_mock_drive_roster.py -q` — **38 passed** using the tests' in-memory SQLite fixtures. Tests now assert that coding round lifecycle completion/expiry without an evaluated submission has null score and maximum, consistent with the persisted-submission scoring contract. The analytics test expects provisional scoring when configured competencies still lack evidence.
- `cd frontend && npm.cmd test` — **110 passed**. Added focused attempt filtering/zero-vs-unavailable and eligibility tests; adjusted the readiness source test to reflect the current scoring-summary copy and to ensure the page does not substitute demo values.
- `cd frontend && npm.cmd run build` — passed. Vite emitted its existing large-chunk advisory (about 1.58 MB minified JavaScript).
- The first `npm test` invocation was blocked by PowerShell's script execution policy. Retrying through `npm.cmd` succeeded.

## Not verified

- No authenticated browser session or live API environment was available in this run. The new page's rendered behavior against live drives/rosters, live API authorization outcomes, and live database contents remain unverified.
- Tests requiring `TEST_DATABASE_URL` / `EDI5_TEST_DATABASE_URL` were not run because neither variable is configured. No development or production database was used.
- The build and tests verify source and isolated fixtures; they do not establish that the configured runtime database has current records or that production data matches these aggregates.
