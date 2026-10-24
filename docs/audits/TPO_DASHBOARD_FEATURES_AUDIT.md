# EDI5 TPO Portal — Dashboard and Features Audit

**Audit date:** 2026-10-23  
**Scope:** Read-only source audit of the current TPO dashboard, candidate pool, Mock Drive, readiness, analytics/reporting, assessment, and competency flows.  
**Method:** Inspected the working tree, frontend routes/pages, API clients, backend routers/services/models, competency scoring, and relevant existing audit/design documents. No application code, API, configuration, schema, or data was changed. No tests, live API requests, or database queries were run for this audit.

## 1. Executive Summary

The TPO portal currently has five routed pages: Dashboard, Candidates, Drives, Readiness, and Analytics. There is no standalone TPO Assessments, Competency Insights, or Reports route. Assessment and competency information is distributed across the candidate roster/detail view, per-drive roster, Readiness, and Analytics. The phrase “Assessments page” therefore does not map to a separate TPO page in the current route tree.

The exact empty-state text in the request — “No scoped competency evidence available. Competency scores are available only for latest sessions with a valid pinned Mock Drive blueprint. The current authorized roster page has no such evaluated evidence.” — is rendered by **`frontend/src/pages/FacultyDashboard.jsx`**, not by a TPO page. TPO Analytics has different empty messages. This is a role/page mismatch in the report of the symptom, not evidence that the TPO route itself renders that message.

Source confirms a strict competency evidence pipeline. Scores are derived read-only from persisted aptitude/coding mappings and the attempt’s pinned approved blueprint; absent or non-countable evidence stays unavailable. Mapping happens best-effort at completed Mock Drive session finalization, and the existing mapper deliberately excludes interview turns and requires exact configured topic/tag matches. Thus an empty competency view can be correct when there are no eligible contexts, pinned snapshots, configured competencies, mappings, or matching evidence. Source alone cannot establish which condition currently affects the user's data.

The strongest dashboard issues confirmed in source are population/definition mismatches: the “Cohort Benchmark” is an institution-wide aggregate; the eligible-pool calculation treats missing CGPA/backlogs as zero; and placement activity checks only the six most recent non-draft drive rosters. Backend analytics also consistently gates TPO/admin but aggregates institution-wide data. An existing read-only database audit dated 2026-10-10 recorded zero competency evidence mapping rows at that time; this is historical evidence only and does not establish current database contents.

## 2. TPO Portal Routes and Component Map

| Route | Component | Current role/use |
|---|---|---|
| `/tpo/dashboard` | `frontend/src/pages/TPODashboard.jsx` | KPI cards, top-three drive pipeline, quick actions, six-drive operational intelligence. |
| `/tpo/students` | `frontend/src/pages/TPOStudentsPage.jsx` | Candidate pool, eligibility filters, paging, candidate details. It is not a standalone assessments page. |
| `/tpo/mock-drives` | `frontend/src/pages/TPOMockDrivesPage.jsx` | Drive creation/management and per-drive participant roster/results. |
| `/tpo/readiness` | `frontend/src/pages/TPOReadinessPage.jsx` | Filtered drive activity, assessment evidence coverage, score readiness, actions and charts. |
| `/tpo/analytics` | `frontend/src/pages/TPOAnalyticsPage.jsx` | Filtered analytics, competency aggregates, drive comparison, client-side CSV/JSON exports. |

Routes are guarded in `frontend/src/App.jsx` with `RoleRoute allowedRoles={['tpo', 'admin']}`. Shared navigation is in `frontend/src/components/TPOLayout.jsx`. No separate `/tpo/assessments`, `/tpo/competencies`, or `/tpo/reports` route was found. Reports are an export section inside TPO Analytics. Assessment results are accessible through the Drive roster and from fields in the candidate API, but the Candidate Pool table itself is a student eligibility directory.

Relevant backend surfaces:

- `app/api/v1/profile.py`: `/profile/me`, `/profile/cohort/students`.
- `app/api/v1/mock_drive.py`: TPO Mock Drive CRUD, roster, per-candidate result, and competency-mapping recovery; separate student participation routes use `/mock-drives`.
- `app/modules/report/routers/report_router.py`: `/report/admin/cohort-stats`, `/analytics/overview`, `/readiness/overview`, drive results/evidence coverage, and other reports.
- `app/services/mock_drive_service.py`, `assessment_blueprint_service.py`, `competency_mapping_service.py`, `competency_scoring_service.py`: drive roster/results, snapshot access, evidence mapping, and read-time scoring.

## 3. Dashboard Cards and KPI Audit

`TPODashboard.jsx` requests `/profile/me`, `/profile/cohort/students`, `/report/admin/cohort-stats`, and `/tpo/mock-drives`. The dashboard stores the first three data sets and drive list, then requests roster data for at most the six newest non-draft drives by ID.

| Card/element | Source and calculation | Source-level assessment |
|---|---|---|
| Eligible Candidate Pool | Loaded cohort students filtered with `(cgpa || 0) >= 7.0 && (backlogs_count || 0) === 0`. | **Misleading for missing profile values.** Missing CGPA/backlogs are coerced to zero and participate as if known. The count is derived from `/profile/cohort/students`; it is not independently checked against database records here. Preserve unknown eligibility as unknown. |
| Total Registered Pool | `students.length` from the cohort endpoint, requested without page parameters. | Represents the returned authorized roster population if the call succeeds. The UI does not surface a distinct unavailable state for a caught cohort request on this card. Current returned count was not queried. |
| Placement Drives Completed | Count of loaded drive records with `status === 'completed'`. | Correctly counts drive lifecycle status, not candidate completion. It is all-time because no period filter is applied. Empty/failed drive fetch becomes `[]`, which can render as zero unless availability messaging elsewhere applies. |
| Cohort Benchmark | `cohortStats.avg_overall_score` from `/report/admin/cohort-stats`, formatted as percent. | **Population label mismatch confirmed.** The endpoint calculates a global average over completed assessment sessions and has no department/cohort filter; the card calls it a cohort benchmark. It also averages session totals, not the pinned-blueprint competency readiness score used by Readiness. No current aggregate was queried. |
| Pipeline | Non-completed drives sorted by status (active, published, draft), then descending ID; top three. Candidate eligibility per drive is computed client-side. | Drive stages reflect current status. Candidate estimate also coerces missing CGPA/backlogs to zero and compares against drive criteria. This can undercount/overstate eligibility when student values are unknown. |
| Most Active Drives | Uses the dashboard's fetched roster map, ranks by participant count then completed count, top five. | **Sampling limitation confirmed.** Only the six newest non-draft drives are roster-fetched; older drives cannot appear. If a roster request fails, its row is dropped and the dashboard may show “No candidate activity” even when unqueried/failed drive activity exists. |
| Placement Intelligence | `buildPlacementIntelligence` in `frontend/src/utils/placementIntelligence.js`; drive creation trend uses returned drives and unresolved deadline risk uses fetched roster rounds. | The risk check is limited to the same at-most-six rosters. The component has an unavailable notice when data/roster requests fail, but a subset of successful requests can still produce partial results. The trend is drive creation activity, not placement outcomes. |

The backend `/cohort-stats` returns zeros when there are no student users, and otherwise averages completed `AssessmentRound.score` and completed `AssessmentSession.total_score` across all records. Completion ratios divide counts of completed sessions/rounds by total student users; the “all three” calculation counts sessions with at least three completed rounds, not necessarily three distinct configured round types or unique students. These fields should not be interpreted as a scoped cohort or configured-drive completion measure.

## 4. Assessments Page Audit

**There is no routed TPO Assessments page.** `TPOStudentsPage.jsx` renders Candidate Pool columns for student, department, CGPA, backlog count, target role, eligibility, and a detail action. It is not primarily an assessment-attempt table. The detail view can use student data returned by `/profile/cohort/students`; assessment visibility is latest-session oriented. `TPOMockDrivesPage.jsx` is the current TPO UI for assessment attempts by drive, with status/round/result details from its roster endpoint.

The cohort endpoint does have persisted fields available for the latest session: session status/ID/timestamps, round type/status/score/timestamps, and associated context. It selects the max session ID per student, so it does not present candidate history or a drive-indexed attempt list. It also has no API pagination by default; pagination is only applied if `page` is sent. `TPOStudentsPage` requests no page and paginates the returned list locally.

The per-drive roster is a more appropriate assessment source: `get_mock_drive_roster` selects contexts for the specific drive in active/completed state, then each context's latest session and round records. It includes drive identity, blueprint ID/version, round status and timing, and derived competency status/coverage. `score_session_competencies` is read-only and returns null for unavailable scores. The page implementation can therefore display more assessment detail than the general Candidate Pool.

**Why the current information looks limited:** there is no assessment-specific route/table or attempt-history API surfaced in the TPO navigation; the directory is a roster/eligibility view, while round information is available only in drive-specific workflows or latest-session fields. This is a feature/layout gap, not proof that assessment data is absent.

**Practical table recommendation (using existing authoritative sources):** Drive, company/role, student/name+ID, configured round, round status, start/completion time, persisted result/score (show unavailable when absent), and pinned blueprint version. Provide drive, status, and date filters. Use a dedicated query over contexts/sessions/rounds rather than treating student roster rows as assessment attempts; expose historical attempts if product scope requires them. Tests should cover repeated sessions, drive isolation, all round states, null scores, and correct timestamps.

## 5. Competency Insights Root-Cause Analysis

### Symptom location and exact supported causes

The quoted “No scoped competency evidence available” message is in `frontend/src/pages/FacultyDashboard.jsx` under its faculty Competencies section. That page derives rows from the currently loaded/paged faculty roster and only includes latest sessions for which `competency_result` is `final` or `provisional`. The profile endpoint attaches a competency result only when the latest session has a Mock Drive context; otherwise it returns unavailable. Its empty message explicitly describes latest sessions in the current roster page. It does **not** establish a TPO analytics failure.

In TPO Analytics, `TPOAnalyticsPage.jsx` calls `/report/admin/analytics/overview` and renders “No competency insights available” when the response's `competency_insights` array is empty. The backend only loops over published/active/completed drives, their Mock Drive contexts, and available latest sessions. It invokes the scorer only when the context already has `blueprint_snapshot`; scoring emits competency rows from the snapshot configuration, even when evidence is not assessed (score remains null). The analytics list can therefore be empty when the filters yield no relevant drive/session/snapshot or the snapshot has no configured competencies; a scoring exception is silently skipped by that aggregate loop. If a snapshot and configured competencies are present but mappings are absent, expected outcome is rows with unavailable/null averages, not necessarily an empty array.

### Data flow and eligibility funnel

1. `CompanyBlueprint.blueprint_data` stores configured rounds and optional competency names, weights, and explicit topics.
2. Approval and Mock Drive creation attach a deep-copied approved blueprint snapshot to the drive. The reader rejects mismatched ID/version/status and does not silently use a newer live blueprint (`assessment_blueprint_service.py`).
3. A student starts the drive; an `AssessmentContext` records `mock_drive_id`, `student_id`, and its pinned snapshot. An `AssessmentSession.context_id` links the attempt to that context; `AssessmentRound` rows link to the session.
4. Aptitude attempts and coding submissions persist under round IDs. Completed Mock Drive sessions call evidence mapping best-effort. Aptitude question topics and coding problem tags map only by exact normalized match to one explicitly configured competency. Ambiguous/unmatched topics are skipped. Interview rounds are intentionally unmapped because interview turns do not carry the required explicit topic association.
5. `competency_evidence_mappings` stores raw evidence values and IDs, not a competency score. The read-only scoring service joins mappings by `session_id`, reads the session's approved pinned snapshot, normalizes countable aptitude/coding evidence, and returns final/provisional/unavailable. Missing evidence is not a zero; valid all-zero evidence is a genuine zero. Invalid weights fail closed.
6. TPO roster and report pages derive aggregates from this service. TPO analytics filters drive status to published/active/completed, applies optional period/company/role/status filters, then examines context/session/snapshot records.

### Root-cause conclusion

**Confirmed source behavior:** competency display requires a Mock Drive context with a valid pinned snapshot containing competencies and usable mapped evidence to produce a scored result. Mapping only covers aptitude/coding and is best-effort; exact topic/tag alignment is required. The UI uses latest-session/current-page scope in the Faculty view and eligible drive/context scope in TPO analytics. These are plausible, code-supported reasons for an empty view.

**Not established:** which prerequisite is missing for the live user's current records. The 2026-10-10 Phase E database report recorded `competency_evidence_mappings` row count `0`, plus assessment-context mapping statuses `NULL=158`, `not_applicable=4` and no pending/completed/failed rows at that audit time. This supports a historical lack of mapped evidence in that database snapshot, but is not a current query and cannot prove present-day records or current UI output. No current runtime/database evidence was obtained.

**Recommendation:** keep evidence and pinned-snapshot requirements. Add explicit, role-appropriate status reasons for no matching drive, no latest completed session, no snapshot, no competency configuration, mapping pending/failed, no exact topic matches, and no countable evidence. Surface `competency_mapping_status` and `scoring_error` safely in operator-facing views. Recovery is already available for pending/failed mapping via the TPO/admin reprocess endpoint; use only after inspecting specific records. Tests should exercise each funnel branch and ensure no missing score becomes zero.

## 6. Mock Drives Audit

TPO drive management is implemented separately from student participation. `/api/v1/tpo/mock-drives` CRUD/list/roster/result endpoints require TPO or admin; `/api/v1/mock-drives/available` and start/progression endpoints are student-only. The drive list is based on `MockDrive` records and status; the roster is derived from `AssessmentContext` rows whose `mock_drive_id` matches the drive and whose context status is active/completed. Candidate participation is therefore not the same as drive existence or eligibility.

The frontend requests drive list and renders status sections, filters, creation/editing, and a roster modal. No current drive rows, statuses, eligible candidates, or participation rows were queried. Thus an empty visible list cannot be diagnosed as “no drives” versus a failed request/filter without browser/API/database evidence. Source has explicit load error toasts and an empty-state helper; user-supplied filters and removed-drive display state can further affect visibility.

The per-drive roster is assessment-context based and reports participants, context status, latest session, and rounds. It does not create a separate assignment record. A published/active drive can legitimately have no participants; a completed drive is a lifecycle state and does not imply every candidate completed. Eligibility is checked by the student available-drive endpoint using profile criteria. No placement/hiring outcome is persisted as an authoritative result in EDI5.

Minimum useful presentation improvements: distinguish no drives from no matching filters, no eligible candidates, no participants, and request failure; preserve the separation between drive configuration, student participation, and evaluated result. Verify with TPO/admin and student accounts, including a drive with no participants, active participation, incomplete rounds, and a completed result.

## 7. Reports Audit

There is no standalone TPO Reports route. `TPOAnalyticsPage.jsx` has “Reports & Exports” controls and builds CSV/JSON client-side from the currently loaded, filter-specific `/report/admin/analytics/overview` response. It does not call a report-generation job or create a persisted report artifact. `TPOReadinessPage.jsx` exports its current readiness response as JSON.

The Analytics backend returns KPI values, drive comparison, activity trend, round performance, candidate funnel, competency-by-department, and competency insight aggregates. Its drive base excludes drafts, accepts period/company/role/status filters, and scopes competency scores to contexts with pinned snapshots. It always marks `passed_candidates` unavailable because no authoritative pass/hire outcome is persisted. “No competency insights available” occurs for an empty aggregate response, not as evidence that the report route itself failed. The page has a separate request error state and empty response state.

The Readiness endpoint also excludes draft drives and scopes activity/evidence to selected drives and reporting period. It returns aggregate data without candidate names/IDs and intentionally leaves unsupported institutional readiness/placement outcomes unavailable. Completion rate is null when its denominator has no participants. Report values should not be described as cohort-wide student outcomes without noting drive filters and their denominators.

No API response, export file, live report, or current filters were inspected. The current causes of an empty report remain unverified. A successful empty aggregate and a failed request are distinguishable in the Analytics source, but current live state is unknown.

## 8. End-to-End Assessment and Competency Data Flow

```text
Historical pattern / TPO configuration
        ↓
CompanyBlueprint (approved, versioned rounds + optional competencies)
        ↓ snapshot at Mock Drive attachment
MockDrive.blueprint_snapshot + derived round configurations
        ↓ student starts
AssessmentContext (drive ID, student, pinned snapshot)
        ↓
AssessmentSession.context_id → AssessmentRound rows
        ↓ evaluation writes
AptitudeAttempt / CodingSubmission / InterviewTurn (round-linked evidence)
        ↓ completed-session best-effort mapper
CompetencyEvidenceMapping (aptitude + coding; exact configured topic/tag only)
        ↓ read-only scorer + same pinned snapshot
TPO Drive roster / Analytics / Readiness aggregates
```

The links above are implemented in source. Assessment results are persisted by their respective assessment services; competency mappings are an additive best-effort finalization step, not a scoring job. On mapping failure, the context stores a failed state and an operator can reprocess without rerunning the assessment. No background scoring worker was found in the inspected competency path. The scorer itself is read-time and deterministic.

Important constraints/risks:

- Historical practice sessions without `AssessmentContext.mock_drive_id` cannot safely be interpreted against a Mock Drive blueprint.
- A context's snapshot is authoritative; current live blueprint changes do not rewrite that pinned configuration.
- Assessment reports commonly select latest session per student or per context. Historical attempts can be omitted from those views.
- Required rounds are drive configuration (`selected_rounds`/enabled order), but generic cohort roster is not a drive-specific record and cannot prove which arbitrary rounds were required for each attempt.
- Competency mapping does not map interview turns and does not infer topic from free-text answers.
- Repeated attempts are represented by contexts/sessions; report definitions must state whether counts mean candidates, contexts, or sessions.

## 9. Database Tables, Models, and Relationships

| Model/table | Role in TPO flow | Key joins/notes |
|---|---|---|
| `User` / `StudentProfile` | TPO candidate identity and academic/profile criteria. | `StudentProfile.user_id → User.id`; cohort endpoint filters users by role and optional department. |
| `MockDrive` | Company/role, lifecycle status, eligibility rules, selected rounds, blueprint ID/version/snapshot. | `AssessmentContext.mock_drive_id → MockDrive.id`. |
| `CompanyBlueprint` | Versioned approved specification with rounds and optional competency configuration in JSON. | Snapshot copied to drive/context; live row is not the runtime scoring source after pinning. |
| `AssessmentContext` | Attempt purpose/mode, drive and student association, pinned snapshot, completion and mapping lifecycle. | `AssessmentSession.context_id → AssessmentContext.id`; `student_id → User.id`. |
| `AssessmentSession` | Candidate attempt status, timing and total score. | Has many rounds; nullable context supports legacy/practice sessions. `total_score` has a database default, so result eligibility must rely on status/evidence, not default presence alone. |
| `AssessmentRound` | Round type/status/timestamps/score within a session. | `session_id → AssessmentSession.id`; schema has default score 0, so absence of a graded result needs evidence checks. |
| `AptitudeAttempt` | Persisted aptitude response/correctness. | Linked by round ID; question topic supplies explicit competency topic. |
| `CodingSubmission` | Persisted coding result/status/score. | Linked by round ID; problem tags provide potential explicit competency topics. |
| `InterviewSession` / `InterviewTurn` | Interview record and turn-level response/final scores. | Interview report paths exist; current competency mapper excludes these because no explicit competency topic is stored per turn. |
| `CompetencyEvidenceMapping` | Raw evidence-to-configured-competency link. | Candidate/context/session/round/evidence IDs, blueprint version, raw metric. No computed competency score is stored. |

No schema changes or database operations were performed. Existing Phase E audit (2026-10-10) confirmed then-present tables/columns for pinned snapshots, round configs, competency evidence mappings, and mapping lifecycle fields, but its schema/data verification is historical, not a current DB check.

## 10. API and Authorization Audit

| API family | Role enforcement and scope | Notes |
|---|---|---|
| `/profile/cohort/students` | Backend permits faculty/TPO/admin. TPO/admin may request a department or omit it for global scope; faculty is forced to its authenticated profile department and cannot select a different one. | Latest session per student; optional server pagination only if `page` is provided. TPO frontend generally requests without it and paginates locally. |
| `/tpo/mock-drives/**` | `_require_tpo_or_admin` on list/CRUD/publish/roster/result/reprocess routes. | No per-TPO ownership restriction is visible; staff users can access institution-wide drives. Student routes are separate and student-only. |
| `/report/admin/**` | `check_admin` permits `admin` and `tpo`; rejects faculty. | Docstring and queries describe institution-wide aggregates. “admin” in path is not the complete permission policy. |
| `/report/admin/analytics/overview` | TPO/admin; optional drive/period filters, no department/faculty scope. | Drive filters govern analytics but not TPO's general identity. |
| `/report/admin/readiness/overview` | TPO/admin; selected published/active/completed drives and period filters. | Aggregate-only response, no candidate identifiers. |

Frontend filters improve display but do not enforce authorization. The inspected TPO endpoints use backend role gates. No unauthorized request was attempted, and no live tokens were used. The institution-wide TPO/admin assumption should be confirmed as product policy, especially for multi-institution deployments; current source does not show TPO-to-department/drive assignment scoping.

## 11. Verified Bugs and Data-Quality Issues

Each item below is verified in source; effects on current production/development rows require runtime verification.

### F-1 — Cohort Benchmark is a global aggregate mislabeled as a cohort measure

- **Severity:** High (metric scope/interpretation).
- **Affected:** TPO Dashboard KPI.
- **Evidence:** `TPODashboard.jsx` uses `/report/admin/cohort-stats.avg_overall_score`; `get_cohort_stats` averages every completed `AssessmentSession.total_score` without department/drive/time filter.
- **Actual vs expected:** UI says “Cohort Benchmark,” but source is institution-wide and includes completed sessions, not necessarily one cohort or drive. Label/scope should match the metric or use a scoped endpoint.
- **Root cause:** Global endpoint reused for a local-sounding KPI.
- **Correction:** Rename to an institution-wide metric with source/denominator, or supply a truly scoped aggregate after product scope is defined.
- **Tests:** Endpoint tests for scope and denominator; dashboard mapping test asserting the label only matches the returned population.

### F-2 — Missing profile criteria are treated as known zero in eligibility counts

- **Severity:** High (candidate eligibility correctness).
- **Affected:** Eligible Candidate Pool and per-drive eligible counts.
- **Evidence:** `TPODashboard.jsx` uses `s.cgpa || 0` and `s.backlogs_count || 0`; same pattern appears in `isEligibleForDrive`.
- **Actual vs expected:** Missing CGPA/backlogs silently become zero. Unknown profile data should not be asserted to be eligible/ineligible without an explicit policy.
- **Root cause:** Falsy fallback used for numeric missing values.
- **Correction:** Preserve null/unknown and separate known eligible, known ineligible, and unknown counts; do not change eligibility policy silently.
- **Tests:** null, zero, numeric-string, and fully populated profile cases against the current policy.

### F-3 — Dashboard operational activity checks only six newest non-draft rosters

- **Severity:** Medium (partial reporting).
- **Affected:** Most Active Drives and unresolved deadline intelligence.
- **Evidence:** `loadTPOData` filters non-draft drives, sorts descending ID, `.slice(0, 6)`, then fetches rosters; `activityRows` and `buildPlacementIntelligence` consume only that map.
- **Actual vs expected:** Older drives cannot appear in the “Most Active” ranking or deadline risk check. A failed roster is omitted, and partial results can look like an empty state.
- **Root cause:** Sampling imposed by frontend request selection and one map used for both partial and complete results.
- **Correction:** Either scope/label it as “among the six most recent checked drives” or use a paginated/batched authoritative aggregate. Surface incomplete sampling/fetches.
- **Tests:** More than six drives, old drive with higher activity, one roster failure, no rosters, and complete empty result.

### F-4 — Cohort stats completion ratios mix session counts with student denominator

- **Severity:** Medium (aggregate definition).
- **Affected:** `/report/admin/cohort-stats` consumers.
- **Evidence:** `get_cohort_stats` counts distinct completed `AssessmentRound.session_id` but divides by total student users; all-three counts sessions with at least 3 completed rows, not distinct configured round types.
- **Actual vs expected:** Repeated sessions/rounds can make rates incomparable to unique-student completion or configured assessment completion.
- **Root cause:** Session-level numerators share a student-level denominator and arbitrary row-count threshold.
- **Correction:** Define cohort and drive/time scope, count distinct eligible students and required distinct round types consistently, or label explicitly as session/round activity.
- **Tests:** Repeated sessions, duplicate round types, configured subset, students without sessions, and zero denominator.

### F-5 — TPO candidate directory is not an assessment-attempt listing

- **Severity:** Medium (feature gap, not confirmed backend data loss).
- **Affected:** User expectation of an Assessments page.
- **Evidence:** No `/tpo/assessments` route; Candidate Pool columns are demographic/eligibility fields. `/profile/cohort/students` emits latest session/round data only. Drive-specific roster is separate.
- **Actual vs expected:** Assessment names/statuses/history are not organized as a TPO assessment index. The data may exist in round/session tables and be visible in Drive roster.
- **Root cause:** No dedicated assessment-attempt page/API view; roster endpoint is per drive and cohort endpoint selects latest session per student.
- **Correction:** Add an attempt-oriented view only after defining history, drive and round filters and ensuring session/context joins are authoritative.
- **Tests:** Student-to-session/context/drive/round joins, repeated attempts, null scores, and attempt pagination.

### F-6 — Competency mapping intentionally covers only exact aptitude/coding topics

- **Severity:** High for coverage expectations; design restriction is confirmed, not itself a bug.
- **Affected:** Competency Insights and scoring coverage.
- **Evidence:** `competency_mapping_service.py` maps aptitude question topic and coding problem tags only when exactly one configured competency lists the normalized topic. Interview turns are left unmapped; ambiguous matches are skipped.
- **Actual vs expected:** A configured competency with no exact topic/tag match has no mapped evidence; interview performance cannot contribute. This can produce null scores despite a completed session.
- **Root cause:** Deliberate conservative mapping contract and absent explicit interview topic mapping.
- **Correction:** Do not weaken matching or fabricate scores. If broader coverage is required, define explicit persisted mappings, including interview evidence policy, and migrate/add tests only with product approval.
- **Tests:** Exact match, no match, ambiguous match, case/whitespace normalization, interview exclusion, and 0-score evidence.

### F-7 — Competency mapping is best-effort and scoring depends on its persisted output

- **Severity:** Medium (operational reliability/diagnostics).
- **Affected:** Competency reports after completed drives.
- **Evidence:** `finalize_session_competency_mapping` is called at completion, catches failures, stores mapping status/error, and does not block assessment completion. Recovery route reprocesses pending/failed mappings.
- **Actual vs expected:** A completed session can have no mappings if finalization failed or no matchable evidence existed. Empty UI needs to distinguish the two.
- **Root cause:** Mapping is intentionally non-blocking; current TPO Analytics collapses some aggregation/scoring exceptions into skipped rows.
- **Correction:** Expose safe aggregate counts for not-applicable, pending, failed, no mappings, and scored; preserve error logs and reprocess only failed/pending candidates after record-level review.
- **Tests:** Finalization success/failure, retry/idempotency, no competencies, exact-match absence, and aggregate classification.

### F-8 — Historical database audit reported zero mappings, but current state is unknown

- **Severity:** Verification gap.
- **Affected:** Reported competency empty state.
- **Evidence:** `PHASE_E_DATABASE_VERIFICATION_REPORT.md` recorded zero `competency_evidence_mappings` rows on 2026-10-10; this audit performed no DB query.
- **Actual vs expected:** Historical evidence makes absent mappings a plausible explanation then, but it cannot establish whether data has since been created or whether current UI filters exclude it.
- **Root cause:** Not determinable for current records without read-only queries/API response.
- **Correction:** During the next authorized verification, count only non-sensitive funnel aggregates by drive status, context, snapshot/configuration, mapping status, mapping count, latest session, and scoring status. Do not export candidate personal details.
- **Tests:** Existing isolated tests can verify funnel behavior; live data validation must be separate and read-only.

### F-9 — Analytics exports are client-side extracts, not generated report artifacts

- **Severity:** Low/medium (expectation mismatch).
- **Affected:** Reports & Exports section.
- **Evidence:** `TPOAnalyticsPage.jsx` creates CSV/JSON in browser from the already-filtered API payload.
- **Actual vs expected:** No asynchronous report job, stored report, or separate export API exists in this page.
- **Root cause:** Export implemented as a presentation-layer download.
- **Correction:** Label as filtered data export; introduce generated reports only if audit trail/scheduled reports are explicitly required.
- **Tests:** Export fields match API response and current filters; unavailable pass outcome remains unavailable.

## 12. Feature Status Matrix

| Feature | Status | Current behavior and evidence |
|---|---|---|
| Dashboard KPI cards | Partially working | Cards consume live APIs, but cohort benchmark scope and missing eligibility fallbacks are misleading; actual current data not queried. |
| Drive pipeline | Working (source) | Shows up to three non-completed drives using lifecycle status and ID ordering; current rows not verified. |
| Most Active Drives / deadline intelligence | Partially working | Real roster data is used but only for six newest non-draft drives. |
| Candidate Pool | Working (source) | Candidate profile/eligibility directory with search, filters and local pagination; not an assessment-attempt list. Runtime roster not verified. |
| TPO Assessments page | Missing | No dedicated TPO route. Latest-session data is in generic cohort API; drive rounds are in per-drive roster. |
| Drive roster/results | Working (source) | TPO/admin endpoint derives candidates from AssessmentContext and links latest session/rounds for one drive. Current records not verified. |
| Competency mapping | Partially working | Exact topic/tag mapper for aptitude/coding is best-effort; interview evidence deliberately excluded. |
| Competency scoring | Working (source) | Read-only pinned-snapshot scoring; null/unavailable for no countable evidence and fail-closed on bad configuration. Runtime response not verified. |
| Competency Insights in Analytics | Blocked by configuration or data / Not verified live | API returns rows only from eligible snapshot/configured contexts. Empty array may be valid. Current filters/records unavailable. |
| TPO Readiness | Working (source), not verified live | Filtered read-only drive/context aggregates and explicit unsupported-value states; no live API/browser verification. |
| Reports | Partially working | Analytics/Readiness pages expose aggregates and client-side downloads; no standalone Reports route or server-generated artifact. |
| TPO authorization | Working (source) | Role guards exist for TPO/admin data endpoints; no live auth test. Fine-grained TPO assignment scope is not present in inspected source. |

## 13. Prioritized Fix Plan (Recommendations Only)

1. **Fix metric scope and unknown-data semantics:** rename/scope Cohort Benchmark; prevent null CGPA/backlogs from being treated as numeric zero; state the populations and denominators on KPI cards.
2. **Make operational sampling visible or complete:** label the six-drive sample and partial roster status, or add an aggregate endpoint/query that returns complete activity without N+1 page requests.
3. **Create an assessment-attempt view if required:** define candidate/history/drive scope and use `AssessmentContext → AssessmentSession → AssessmentRound` as the source; keep missing scores unavailable.
4. **Improve competency funnel diagnostics:** show whether a drive/session lacked snapshot/configuration, mappings are pending/failed/not applicable, no topics matched, or evidence is not countable. Preserve exact-match and pinned-snapshot controls until a mapping policy is approved.
5. **Validate current data before changing features:** read-only counts and sampled IDs/foreign-key joins for eligible drive contexts, snapshots, sessions, round evidence, mapping statuses/mapping rows, scoring result status, and API response/filter metadata.
6. **Document report guarantees:** distinguish global cohort stats from filtered Mock Drive analytics; label CSV/JSON as filtered client-side export and keep pass/hire outcome unavailable until an authoritative outcome model exists.

No fixes were implemented in this audit.

## 14. Files Likely to Require Changes

Only if implementation is approved after reviewing this audit:

- `frontend/src/pages/TPODashboard.jsx` — scope/labels for KPI cards; missing-value handling and activity sampling messaging.
- `frontend/src/utils/placementIntelligence.js` and focused tests — sample coverage state if dashboard risks remain based on bounded fetch.
- `frontend/src/pages/TPOStudentsPage.jsx` — assessment-oriented navigation/table only if required; avoid misrepresenting latest-session rows as attempt history.
- `frontend/src/pages/TPOMockDrivesPage.jsx` — clearer no-participant/empty/filter/load states if runtime evidence demonstrates confusion.
- `frontend/src/pages/TPOAnalyticsPage.jsx` and `frontend/src/pages/TPOReadinessPage.jsx` — reason-specific empty states/metric labels after identifying current API branch.
- `app/modules/report/routers/report_router.py` and report schemas — only for explicitly approved aggregate scope/definition changes.
- `app/services/competency_mapping_service.py` plus models/migrations — only if product approves new evidence types or explicit mapping data; not required to make unsupported evidence appear.
- Focused backend and frontend tests for scope, query joins, zero/null handling, and empty/error states.

No database/schema change is justified by source inspection alone.

## 15. Runtime Verification Checklist

Run only with an approved read-only account/environment and a non-destructive test database where applicable:

1. Capture authenticated TPO calls and response status/body metadata for `/profile/cohort/students`, `/report/admin/cohort-stats`, `/tpo/mock-drives`, each sampled drive roster, `/report/admin/analytics/overview`, and `/report/admin/readiness/overview`. Compare loading/error/empty UI branches to those responses.
2. Query aggregate counts without exporting personal data: drive status counts; contexts grouped by drive and status; contexts with/without pinned snapshots and competency configs; latest sessions per context; mapping lifecycle statuses; mapping row counts by evidence type; score statuses (final/provisional/unavailable); unmatched/no-evidence counts if safely derivable.
3. For one existing non-sensitive test drive, verify company/role/status, configured enabled rounds, drive snapshot ID/version, context snapshot ID/version, context/session IDs, round rows and result evidence foreign keys. Avoid student names/emails in the report.
4. Compare one TPO drive roster response against its source context/session/round records, including a completed round without a result and a true zero-valued result.
5. Verify role gates: TPO/admin allowed; student/faculty denied for TPO management and report endpoints; student-only participation endpoints deny staff. Do not attempt cross-user access outside a controlled test account.
6. Check UI separately for API failure vs successful empty response, no drives, no participants, no snapshot, no competency configuration, pending/failed mapping, no matched/countable evidence, and filter-excluded data.
7. Verify no server-side report asserts “passed/hired” without an authoritative result; confirm exports preserve unavailable values and active filters.
8. Use existing tests only after confirming their DB fixture is isolated. Existing project docs say DB-touching tests require a separate `TEST_DATABASE_URL`; never point it to the development DB.

## 16. Open Questions and Verification Gaps

- Does the reported message appear on `/faculty/dashboard` or on a TPO account/page? Source says it is Faculty Dashboard copy; a screenshot or URL is needed to reconcile the reported symptom.
- What is the intended TPO scope: institution-wide data for every TPO, or TPO-to-department/drive assignment? Current backend gives TPO/admin institution-wide roster/report/drive access.
- Should “Cohort Benchmark” be institution-wide, department-scoped, or selected-drive scoped, and what exactly is its denominator/score scale?
- Should assessments be a standalone page, a tab in Candidate Pool, or remain drive-roster based? Is latest attempt sufficient or is full history required?
- Should interview evidence contribute to competency scores? Current model has no explicit topic mapping and current service intentionally excludes it.
- Does current DB have eligible completed Mock Drive contexts, valid pinned snapshots with competency definitions, mapped aptitude/coding evidence, or failed mappings? The last available database audit is dated 2026-10-10 and reported zero mapping rows; current state is unverified.
- Which Analytics and Readiness filters were active when the empty view was observed? Are API failures present in browser Network/backend logs?
- Current row counts, drive names/statuses, scores, UI rendering, API authorization, and actual data/response shape were not verified live. No browser, authenticated API, database, logs, or tests were used in this audit.

## Existing Documentation Reviewed

- `docs/audits/PHASE_4_RECONCILED_GAP_REPORT.md` — prior Phase 4 implementation and test report (dated 2026-10-12); used as historical documentation, not rerun evidence.
- `docs/audits/PHASE_E_DATABASE_VERIFICATION_REPORT.md` — read-only schema/data snapshot (dated 2026-10-10); its mapping row count is historical.
- `docs/audits/HISTORICAL_ASSESSMENT_CONFIGURATION_AUDIT.md` — blueprint, round configuration and pinned-drive snapshot behavior.
- `docs/audits/PHASE_4_D1_SCORING_DESIGN.md` — competency scoring contract.
- `docs/DATABASE_WORKFLOW.md` — development/test database safety and isolation rules.

## Files Changed

- `docs/audits/TPO_DASHBOARD_FEATURES_AUDIT.md` — this audit report only.

No application source, test, schema, migration, dependency, or configuration file was changed. Pre-existing working-tree modifications and untracked files were preserved.
