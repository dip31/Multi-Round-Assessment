# Faculty Dashboard Functional Audit

**Date:** 2026-10-23  
**Mode:** Source audit only. No application code, API, database, schema, configuration, TPO page, or TPO-related file was changed for this audit. No live database/API or authenticated browser session was used.

## 1. Executive summary

The previous [Faculty Dashboard audit](FACULTY_DASHBOARD_AUDIT.md) described an earlier version of the faculty page and is no longer an accurate description of the current UI. `frontend/src/pages/FacultyDashboard.jsx` now implements six sections in one routed React page: Dashboard, My Students, Assessments, Competency Insights, Mock Drives, and Reports. It uses a department-scoped, paginated cohort endpoint, distinguishes request failures from a successful empty cohort, preserves null scores, and withholds incomparable aggregate scores.

The most important remaining findings are:

1. **Department defaults can silently become authorization assignments.** `FacultyProfile.department` and `StudentProfile.department` both default to `Computer Science`; `/profile/me` creates a missing faculty profile through `get_or_create_faculty_profile`. The scope service then treats that default as the authenticated faculty assignment. No admin assignment workflow was found. The code blocks a faculty user from changing their own department, but the default can still assign a new or legacy account to CS without an explicit assignment. Actual affected accounts were not inspected.
2. **Assessments is intentionally latest-session-only.** It displays rounds for students on the current 20-row roster page. It does not fetch attempt history, candidate-level detail endpoints, or drive context. The database models retain session/round/result relationships, but the faculty cohort response omits history and context identifiers. This explains the limited output; it is not evidence that historical records are absent.
3. **Competency Insights has strict data prerequisites and a false-empty path.** It only scores the latest session when the linked context is a Mock Drive, a valid pinned snapshot has configured competencies, and explicit mappings contain countable evidence. Mapping is topic-exact and supports aptitude and coding only; interview turns are deliberately unmapped. Separately, the UI gates all competency rows on the overall status being `final` or `provisional`. The scoring service can return assessed competency rows while the overall status is `unavailable` (for example, invalid blueprint weights), so the page can show “No scoped competency evidence available” even when per-competency evidence exists. Whether this situation occurs in stored data is unverified.
4. **Mock Drives is deliberately unavailable to faculty.** The displayed empty/disabled experience is a product authorization boundary, not a failed faculty API integration. Existing drive list, roster, and result routes require TPO/admin; student routes are student-only. There is no faculty-safe drive scope/API.
5. **Reports is only a current-page roster CSV export.** There is no faculty report aggregation page/API. Institution-wide `/report/admin/*` routes now reject faculty; reusing those routes would be incorrect.

The repo's current code handles some previous-audit issues correctly: faculty department query overrides are rejected, unassigned student profiles are excluded from a department-scoped roster, self-service faculty department changes are rejected, global reports are TPO/admin-only, profile values are returned as null when they are truly null, and scores are disclosed only when persisted evaluation evidence is present. These are source findings, not live verification.

## 2. Current implementation and changes since the previous audit

### Current route and workspace

- `frontend/src/App.jsx:226-233` mounts `FacultyDashboard` at `/faculty/dashboard` and applies `RoleRoute allowedRoles={['faculty', 'admin']}`.
- The six section IDs live in `NAV_ITEMS` in `FacultyDashboard.jsx:7-14`. `useSearchParams` switches sections using a `?section=` query value (`:117-121`). They are **sections in the same component**, not six independent routes or pages.
- `Navbar.jsx:31-35` sends a stored faculty role to `/faculty/dashboard`. `RoleRoute.jsx` is client-side navigation protection only; backend authorization is separately enforced.
- The page calls `GET /profile/me`, then `GET /profile/cohort/students` with `page`, `page_size=20`, `status`, and optional `search` (`FacultyDashboard.jsx:137-174`). It does not call global TPO analytics endpoints.

### Changes present in source after the old audit

The prior audit's follow-up section records the implementation history. Current source confirms:

- The cohort endpoint derives faculty scope from the authenticated `FacultyProfile` and rejects a different requested department (`app/api/v1/profile.py:144-156`). Department-scoped queries join `StudentProfile` and require an exact case-insensitive department match, excluding missing profiles/departments (`:171-185`).
- Search/status/page filtering are server-side; the full-scope summary is returned separately (`:187-215`, `:382-447`).
- Faculty roster responses omit contact/demographic fields and keep student academic values nullable in the response. Faculty scores are derived only when matching evaluated persisted records exist (`:221-279`, `:287-379`).
- Faculty cannot change their own assigned department through `PUT /profile/faculty/me` (`:85-100`). Global `/report/admin/*` endpoints are now TPO/admin only (`report_router.py:31-40`).
- Faculty has six visible section choices, including explicitly unavailable Mock Drives and a limited roster-export Reports section.
- The competency service uses pinned blueprint configuration and persisted evidence mappings. It does not infer competency from a raw overall score or free-text similarity (`competency_mapping_service.py:1-15`, `competency_scoring_service.py:1-22`).

No live data check was made to determine whether the current authorized roster is empty, whether profiles have explicit assignments, or how many assessment records meet the scoring criteria.

## 3. Dashboard KPI and empty-card analysis

| Card/section | UI → API/source | Actual source behavior | Root cause / classification |
|---|---|---|---|
| Authorized students | `FacultyDashboard.jsx:203-209` reads `summary.authorized_students` from `/profile/cohort/students`. | Backend counts students in the faculty department scope before page/search/status filters (`profile.py:171-176`, `:382-447`). A returned `0` is a real empty matching scope; a missing summary renders an em dash. | Correctly data-backed. **Important data-assignment risk:** default department values can make the scope look assigned when it was defaulted; see Security. Actual count is **not verified**. |
| Assessed students | UI reads `summary.assessed_students` (`:176-179`, `:205-206`). | Backend counts each student's latest session only if the session is completed and has at least one completed round with matching evaluated evidence (`profile.py:386-429`). It is not a count of all historical assessment attempts, all rounds, or all students who ever scored. | A low/zero value can be genuine under this narrow definition. Historical attempts and the endpoint's evidence rules explain why older valid activity is not included. Actual count is **not verified**. |
| Students improving | Literal `Unavailable`; note says comparable attempt history is unavailable (`FacultyDashboard.jsx:207`). | No trend calculation is attempted. The API returns only the latest session per student and no comparable score series. | **Deliberate unavailable state**, not a failed API or zero. Requires history and a validated comparable scale before calculating. |
| Pending actions | Literal `Not configured`; no review-task source (`:208`). | No task/review queue endpoint or model was identified for faculty. | **Missing product/backend capability**, not an empty query. |
| Latest attempt completion | Reads `summary.latest_attempt_completion_rate` (`:211`). | Numerator is the count above; denominator is all authorized students; result is `null` when the authorized cohort denominator is zero (`profile.py:430-437`). This is latest completed-and-evaluated-session completion, not completion of all configured rounds. | Empty denominator is rendered “Insufficient data”; `0%` with eligible students and no qualifying completed sessions is a genuine zero. UI wording accurately disclaims equal required rounds. Actual result is **not verified**. |
| Average assessment score | Static unavailable explanation (`FacultyDashboard.jsx:212`). | The backend explicitly returns `average_score: null` and a reason because score scales across latest session types are not verified comparable (`profile.py:430-436`). It does not average missing scores as zero. | **Deliberate unavailable metric**. A verified per-assessment/round-specific metric could be designed later, but should not be replaced by an unvalidated cross-type average. |
| Students to check in with | Uses current `students` array (`FacultyDashboard.jsx:179`, `:213`). | The array is one server page of at most 20 rows and is affected by the current search/status/page state. It includes statuses `in_progress`, `not_started`, and `terminated`; the UI says this is the current roster page. | Correctly disclosed page limitation, but it is not a cohort-wide queue. A dashboard-wide count/list would require a server-side aggregate or a separate query with consistent scope. `terminated` is included here but not an option in `STATUS_OPTIONS` (`:15-20`), so it cannot be selected directly as a roster filter. |

### Error and empty-state distinction

`loadProfile` exposes a profile error (`FacultyDashboard.jsx:137-149`). `loadRoster` clears stale data, sets a typed user-facing error for 401/403/general failures, and avoids showing failure as an empty cohort (`:151-173`). My Students distinguishes filtered-empty from successful empty scope (`:218-227`). Assessments, Competency Insights, and Reports also have explicit error branches. This is a material improvement over the prior audit's “errors become empty lists” finding.

One caveat is that the shared Axios 401 interceptor redirects to login (`frontend/src/services/api.js`) before the page's 401 text necessarily remains visible. This is a normal session-expiry flow, not a false empty-cohort condition.

## 4. Assessments root-cause analysis

The current Assessments section (`FacultyDashboard.jsx:229-232`) builds rows from `students.flatMap(student => student.round_records)`. Those `students` are the currently returned roster page. The heading explicitly identifies “Persisted rounds from the latest session” and the current page number.

### Why the output is limited

1. `GET /profile/cohort/students` selects one session per user using maximum `AssessmentSession.id` (`profile.py:161-169`, `:216-220`). It does not return a list of attempts.
2. The faculty JSON includes latest-session `round_records`, but intentionally omits `session_id`, context ID, drive ID, blueprint version, and older sessions (`profile.py:304-335`, faculty/non-faculty split at `:335-379`). The UI can show a person, raw round type, date, status, and nullable score, but cannot identify which drive/pinned blueprint/attempt produced it.
3. Pagination is 20 students. Assessments only shows those 20; changing the page changes its data. The active search and status filters also change the set.
4. No list endpoint for all faculty-scoped historical sessions/attempts was found. `GET /report/student-analytics` is authenticated user's own analytics (`candidate_report_router.py:381-400`), not a faculty cohort endpoint. `/coding/results` also queries the current user's session (`coding_router.py:290-315`). `GET /coding/submission/{id}` permits department-authorized faculty for a known submission ID (`:369-401`), but the cohort response does not provide submission IDs or a roster-wide submissions listing. Aptitude and interview evidence are likewise persisted in their own tables.
5. The UI shows `scoreDisplay` only for `status === 'completed'`; otherwise it says “No evaluated score” (`FacultyDashboard.jsx:231`). The backend returns a score only for completed rounds with persisted evaluated evidence (`profile.py:267-279`). For a completed round without evidence it displays “Unavailable,” as intended. For expired rounds the helper always returns null due its completed-only check, even if some partial evidence may exist. Whether expired-round partial scores should be visible is a scoring/product policy decision, not established by this audit.

### Existing data that can support a fuller view

The schema relates `AssessmentSession.user_id` to the student, `AssessmentRound.session_id` to a session, and evidence rows to round IDs. Aptitude records use `AptitudeAttempt.round_id`; coding records use `CodingSubmission.round_id`; interviews use `InterviewSession.session_id` and `InterviewTurn.interview_id`. Mock Drive contexts link through `AssessmentContext.mock_drive_id`, and sessions link back through `context_id` (`app/models/assessment.py`, `app/models/assessment_context.py`, `app/models/aptitude.py`, `app/models/coding.py`, `app/models/interview.py`).

Thus the page is limited by the faculty API contract and UI, not because the source model has no attempt/evidence entities. A useful extension needs a server-side faculty-authorized history endpoint or a carefully paged extension of the cohort contract, with student scope enforced before joining. It should return stable attempt/context identifiers, assessment kind/drive label where appropriate, timestamps, statuses, and results under each assessment type's own scale. Current live row counts and whether every historical result is complete were **not verified**.

## 5. Competency Insights evidence and scoring analysis

### Trigger and frontend behavior

- `FacultyDashboard.jsx:180-195` aggregates `competency_result.competencies` from the current roster page by **competency name**, collecting per-competency scores/evidence counts.
- `:234-237` defines a result-bearing student as one whose overall competency status is `final` or `provisional`. The data view renders only when `mappedStudents && competencyRows.length`; otherwise it displays the message “No scoped competency evidence available.”
- The API calls scoring for a faculty row only when the student's latest session has a linked context with `mode == "mock_drive"` (`profile.py:335-363`). Practice, legacy, and non-Mock-Drive contexts return unavailable with no competency rows.
- The faculty response omits mapping lifecycle status/error, scoring error, blueprint ID/version, and session/context IDs. The UI therefore cannot distinguish no snapshot, no configured competency, pending/failed mapping, no exact topic match, non-countable evidence, and invalid weights.

### Scoring and mapping requirements

- `score_session_competencies` reads the pinned snapshot and configured competencies (`app/services/competency_scoring_service.py:143-168`). Missing/invalid snapshot, no configured competencies, invalid weight totals, or no assessed competency can leave the overall status unavailable (`:203-228`). Missing competencies make a partial score provisional, rather than redistributing missing weight; all assessed competencies with valid configuration can be final.
- Aptitude is countable only with persisted `is_correct`; incorrect answers become a legitimate normalized 0. Coding uses persisted submission score in a 0..1 scale converted to 0..100; `running` and `internal_error` are excluded (`competency_scoring_service.py:57-95`). No score is inferred from a round's default score.
- Mapping uses topics explicitly configured on the pinned blueprint. Topic matching is trimmed, case-insensitive exact equality. Ambiguous topic ownership is unmapped (`app/services/competency_mapping_service.py:1-15`, `:83-119`). Only aptitude and coding are mapped; interview evidence has no explicit topic and is deliberately skipped (`:221-242`).
- `CompetencyEvidenceMapping` records session/context/round, evidence type/ID, competency ID, blueprint version, and raw metric; `evidence_id` is polymorphic and has no direct foreign key (`app/models/competency.py`). Scores are computed at read time and not persisted.

### Classification of reasons for the empty message

| Potential cause | Code evidence / classification | Live status |
|---|---|---|
| No assessment data / no latest sessions on this roster page | UI aggregates only current page records. If there are no returned `round_records`, no competency rows can exist. **Supported source path.** | Not queried. |
| Assessment exists but is not evaluated | Scoring ignores missing metrics and non-final coding statuses; no assessed items results in unavailable. **Supported source path.** | Not queried. |
| Competencies or mappings are not configured | Missing competency list yields `no_configured_competencies`; no exact topic match or ambiguous topics produce no mapping. **Supported source path.** | Not queried. |
| Pinned Mock Drive blueprint snapshot missing/invalid | Faculty competency scoring is only attempted for a Mock Drive context, and snapshot validation fails closed. **Required condition and supported cause.** | Snapshot records not queried. |
| Evidence excluded by authorization/filtering | Faculty is limited to department and current page/search/status. A valid record outside that scope/page is excluded by design. **Supported source path.** | Distribution not queried. |
| Interview evidence unavailable to competency scoring | Mapping service intentionally maps only aptitude/coding; it explicitly skips interview because turns lack explicit topics. **Confirmed limitation by design.** | Does not depend on live data. |
| Backend query/scoring incorrect | No evidence of a general empty query from source. **Not established.** However, profile endpoint has no per-row exception isolation around scorer calls; an unexpected DB/runtime error can fail the entire roster request, which becomes a roster error rather than the empty competency state. | Runtime behavior not tested. |
| Frontend hides data because overall status unavailable | UI gate requires final/provisional, while scoring service can return assessed per-competency rows plus unavailable overall status (e.g. invalid weight configuration). **Confirmed false-empty path in source.** | Whether any current row meets it is not queried. |
| Frontend groups distinct competencies by name | Backend scoring has IDs, but profile response strips IDs and UI groups by name. Different competency IDs/namespaces with the same display name across blueprint versions can be merged. **Confirmed design risk; impact depends on data.** | Blueprint data not queried. |

**Conclusion:** The message is a generic state, not a diagnosis. Source establishes several legitimate prerequisites and at least one UI condition that can mislabel existing per-competency evidence as no evidence. The actual triggering category for the current user's screen cannot be identified without an authenticated API response and read-only database evidence. Do not remove the message or loosen scoring rules; improve diagnostics and preserve valid per-competency results independently from overall score validity.

## 6. Mock Drives functionality and authorization

`renderDrives` in `FacultyDashboard.jsx:240` intentionally renders “Faculty Mock Drive view is not available.” The faculty page does not issue a drive API request, so there is no hidden 403 converted to an empty list here.

`app/api/v1/mock_drive.py` separates TPO/admin routes under `/tpo/mock-drives` from student routes under `/mock-drives`. `_require_tpo_or_admin` protects list/detail/publish, roster, and candidate result routes (`:56-64`, `:84-95`, `:127-170`, `:173-196`); student endpoints explicitly require student role (`:201-219`, and following student status/result routes). No faculty drive list, roster, or result API was found. The service's derived roster is based on `AssessmentContext` for a particular drive and latest session (`mock_drive_service.py:1853-1919`), but exposing it by simply changing the role guard would expose a drive's candidate roster without a faculty scope policy.

**Status:** Missing faculty capability by design/authorization, distinct from lack of Mock Drive records. Whether drive data exists, how many sessions/results are persisted, and which faculty may access which drive are **not verified**. Do not broaden TPO permissions. A product owner must define department assignment vs explicit drive/student assignment and minimum fields before adding a faculty-safe source.

## 7. Reports functionality and data-scope analysis

The Reports section (`FacultyDashboard.jsx:239`) is a CSV export of `students`, which is only the current filtered roster page (at most 20 rows). It does not call a reporting API, and the text explicitly says that historical periods, comparable trends, and Mock Drive reports are unavailable.

- `/report/admin/cohort-stats`, `/report/admin/skill-gaps`, and `/report/admin/all-candidates` call `check_admin`, which now permits only `admin` and `tpo` (`app/modules/report/routers/report_router.py:31-40`, then route functions around `:42`, `:141`, `:247`). Their global aggregates are not an authorized faculty data source.
- The candidate analytics routes are for the authenticated student's own sessions (`candidate_report_router.py:59-73`, `:381-400`). They cannot be reused to report an entire faculty cohort.
- Interview reports are available for one known interview ID. `_get_interview_for_user` permits faculty only after `require_faculty_student_access` verifies the owner (`interview_router.py:114-145`; report route `:1731-1739`). The faculty roster does not include an interview ID/history list, so this route is not wired into the page.
- Coding submission detail can be read by the owner or department-authorized faculty for a known submission ID (`coding_router.py:369-401`), but there is no faculty cohort report/list source in this route. `/coding/results` is the authenticated user's latest round (`:290-315`).
- The report export quotes CSV fields but does not prefix spreadsheet formula-leading characters (`FacultyDashboard.jsx:61-71`). If user-controlled values are exported into Excel-compatible software, formula injection is a **confirmed export-hardening risk**. The intended export fields are mentoring-relevant and no private contact/demographic fields are included.

**Status:** No faculty analytics report is implemented. Current roster export works from already authorized rows but is page-sized and not a period/history report. The route permission constraints are correctly not bypassed.

## 8. Cross-module data flow and schema findings

The core relationships are present:

```text
User (student) → StudentProfile
User → AssessmentSession → AssessmentRound → aptitude/coding evidence
                          └→ InterviewSession → InterviewTurn
AssessmentSession → AssessmentContext → MockDrive + pinned blueprint_snapshot
AssessmentSession / Context / Round → CompetencyEvidenceMapping
```

- `AssessmentSession` belongs to a user and optionally a context; rounds belong to sessions (`app/models/assessment.py`).
- `AssessmentContext` optionally references a Mock Drive and stores a JSON pinned blueprint snapshot, mapping lifecycle state, and timestamps (`app/models/assessment_context.py`).
- Aptitude attempts and coding submissions point to round IDs; interviews link to assessment session and their turns (`app/models/aptitude.py`, `coding.py`, `interview.py`).
- Competency mappings preserve candidate/session/context/round and blueprint version (`app/models/competency.py`). Their polymorphic `evidence_id` deliberately has no single evidence-table foreign key.
- The faculty endpoint loads `User.assessment_sessions` and each session's rounds/context with `selectinload`, then chooses the highest session ID (`profile.py:206-220`). This avoids a per-user query just to find sessions, but loads all sessions/rounds for each paginated user to return only one latest session. Historical volume can make this unbounded per student; query cost was not measured.
- Competency scoring queries mappings for each eligible latest Mock Drive session (`competency_scoring_service.py:151-168`), so competency-enabled pages add per-session scoring queries. Runtime/query count was not profiled.
- The same “latest by ID” rule appears in latest-session selection; timestamp-vs-ID ordering behavior in live data was not checked.

### Defaults that can disguise missing source data

`app/models/profile.py:23-58` sets StudentProfile defaults including department `Computer Science`, CGPA `7.50`, graduation year `2026`, zero backlogs, target role, and nationality. `FacultyProfile` also defaults department to `Computer Science` (`:61-80`). `ProfileService.get_or_create_faculty_profile` inserts a profile without an explicit department (`profile_service.py:35-43`), causing the ORM default to be used. The response may show these values as actual persisted values; the current cohort response's null preservation does not undo model defaults already materialized in the database. The audit cannot determine how many rows were explicitly entered vs defaulted.

This is especially relevant because the faculty profile department is the authorization scope. It is not safe to infer that `Computer Science` was an administrator-approved assignment merely because it is stored.

## 9. API and frontend integration findings

| UI area | Request/route | Contract and integration result |
|---|---|---|
| Workspace profile/header | `GET /api/v1/profile/me` | `UserProfileResponse` carries `name`, `role`, `faculty_profile.department`. The page uses actual name, department, and displays “DEPARTMENT UNAVAILABLE” only if missing. However profile GET can create a missing FacultyProfile and its default is Computer Science, so missing assignment may not reach that UI state. |
| Dashboard/My Students/Assessments/Competencies/Reports | `GET /api/v1/profile/cohort/students` | Page uses `students`, `total`, `summary`; request params match backend names `page`, `page_size`, `status`, `search`. Response round property `round_records` matches component use. Scores remain nullable. Competencies are embedded per student only for a latest Mock Drive context. |
| Global TPO reports | `/api/v1/report/admin/*` | Faculty page does not call them; backend now correctly returns 403 for faculty because these are institution-wide. |
| Interview detail | `GET /api/v1/interview/session/{id}/report` | Can permit faculty only for a department-authorized student; no ID/history connection from the faculty page. |
| Coding detail | `GET /api/v1/coding/submission/{id}` | Department-scoped faculty access exists for a known submission ID; current faculty response does not supply the IDs or a faculty-wide list. |
| Mock Drive section | None from faculty page | Static “not available” state. Current existing APIs do not support faculty role. |

No mismatch was found between the current faculty page's principal cohort field names and the backend response. The more significant limitation is missing history/context/detail identifiers and the dependency on one latest session.

## 10. Security and authorization findings

### Confirmed protections

- `/profile/cohort/students` authorizes faculty/TPO/admin at the server; faculty department is taken from their authenticated profile. A different `department` query returns 403. Department queries require a matching StudentProfile and do not include profile-less students across all departments (`profile.py:138-185`).
- Faculty cannot change their own department via `PUT /profile/faculty/me` (`profile.py:85-100`).
- `/report/admin/*` checks role server-side and is TPO/admin-only (`report_router.py:31-40`). The frontend RoleRoute is not the only control.
- Interview report access enforces faculty scope through `faculty_access_service` (`interview_router.py:114-145`). Coding submission details and resume-file access also call the department access helper for faculty (`coding_router.py:369-401`; `profile.py:571-583`).
- The shared policy in `faculty_access_service.py` compares the student's department with the authenticated faculty profile department and uses a 404 for an out-of-scope known student.

### Confirmed policy/data risk and open decision

- **No explicit department-assignment model/workflow was found.** The current scope is department-wide by string equality, not assigned-student scope. The code's policy assumption is documented in `faculty_access_service.py`.
- **Default department can grant a broad scope without an explicit assignment.** New/missing faculty profiles default to CS; `get_or_create_faculty_profile` materializes the default. Student profiles also default to CS. This can produce a populated but incorrectly assigned CS scope. Whether real users are affected is unverified.
- `PUT /profile/faculty/me` has no explicit role gate at function entry. For role `faculty`, changing department is blocked. A different authenticated role can call it to update/create its own faculty-profile row; this does not change that user's role and does not directly grant faculty access, but is an unnecessary endpoint-policy ambiguity. No target faculty assignment endpoint is present.
- The product owner must decide whether faculty access is department-wide or based on explicit faculty-student/drive assignments, who may make assignments, and how legacy/default profiles are migrated/validated. Do not guess or add a reassignment workflow as part of a UI fix.

## 11. Feature-by-feature status

| Faculty section | Status | Current behavior and limitation |
|---|---|---|
| Dashboard | Partial, honest unavailable states | Department-wide student/assessed counts and latest-attempt completion; no average/trend/review queue. Follow-up list uses current page. |
| My Students | Implemented roster | Server-side scope, search/status/page controls, limited profile fields, latest-session details only. No full history/student detail endpoint. |
| Assessments | Partial | Latest-session round feed for current roster page; no attempt selection/history/context labels or assessment-specific drilldown. |
| Competency Insights | Partial, evidence-gated | Pinned Mock Drive snapshots and explicit mapped aptitude/coding evidence only. Generic empty message conflates multiple causes and can hide rows when overall score is unavailable. Interview evidence excluded by design. |
| Mock Drives | Not available to faculty | Correctly no data is shown because all relevant existing management/roster APIs are TPO/admin-only and no approved faculty scope exists. |
| Reports | Partial export only | CSV of current filtered roster page; no faculty-scoped aggregates, periods, trends, or drive reports. CSV formula hardening risk. |

## 12. Prioritized verified defects and risks

1. **High — Implicit/default department assignment.** `FacultyProfile.department` defaults to CS, and profile retrieval creates that row. Because the value is then trusted as the faculty authorization scope, a missing explicit assignment can become CS access. Student profile defaults can also make missing department data look assigned. **Evidence:** `app/models/profile.py:23-80`, `app/services/profile_service.py:35-43`, `app/services/faculty_access_service.py:16-27`, `app/api/v1/profile.py:144-156`. **User impact:** empty or misleading counts, or an authorization scope broader/different than intended. **Fix direction:** obtain product decision and implement explicit trusted assignment semantics; do not populate by UI guess.
2. **High — No faculty-scoped assessment history.** Endpoint returns only highest-ID session and round records; no attempt list or context IDs. **Evidence:** `profile.py:161-220`, `:287-379`; `FacultyDashboard.jsx:229-232`. **Impact:** page cannot show prior valid results, identify drive/attempt, or support trend analytics. **Fix direction:** design a paginated faculty-scoped attempt API with stable IDs and tested authorization before adding UI detail.
3. **High — Competency false-empty condition and insufficient diagnostics.** UI only renders rows if final/provisional overall status exists, but service can have assessed component rows while overall is unavailable due bad weights; response also omits mapping/configuration errors/lifecycle. **Evidence:** `FacultyDashboard.jsx:180-195`, `:234-237`; `competency_scoring_service.py:170-240`; `profile.py:335-363`. **Impact:** valid evidence can be hidden and the message can imply no evidence. **Fix direction:** display per-competency evidence independent of overall status; expose safe reason/status metadata and stable competency IDs, preserving score validity rules.
4. **High — No approved faculty Mock Drive data source.** Existing roster/result routes are TPO/admin-only and no faculty assignment model exists. **Evidence:** `mock_drive.py:56-64`, `:84-95`, `:158-196`; faculty page `:240`. **Impact:** this section cannot show any drive participation. **Fix direction:** product decision on drive/candidate scope and safe fields, then a server-enforced faculty endpoint; do not loosen current role checks.
5. **Medium — No faculty report API and export is page-limited.** Report UI exports at most 20 current filtered rows. Global report routes deny faculty, and the current page has no pagination-wide export behavior. **Evidence:** `FacultyDashboard.jsx:21`, `:157-163`, `:239`; `report_router.py:31-40`. **Impact:** users may expect historical/cohort reports but only receive one page. **Fix direction:** specify the report cohort, period, denominators, and server-side scope before adding report endpoints.
6. **Medium — CSV formula injection guard absent.** CSV values are quoted but formula-leading content is not neutralized (`FacultyDashboard.jsx:61-71`). **Impact:** spreadsheet software may execute formulas from user-entered field values. **Fix direction:** use a formula-safe CSV serialization helper and focused tests; retain current field minimization.
7. **Medium — Competency summary keys by display name and loses identity.** The API discards `competency_id`; the frontend merges by name. **Evidence:** `profile.py:343-357`; `FacultyDashboard.jsx:180-195`. **Impact:** similarly named competencies across blueprint versions can merge. **Fix direction:** preserve stable IDs and either filter to a coherent blueprint/version or group by ID plus version.
8. **Low/medium — Check-in section is page/filter scoped while dashboard KPI is whole-scope.** The note discloses current-page scope, but page and filters persist across section navigation. Terminated status appears in check-in but has no status filter option. **Evidence:** `FacultyDashboard.jsx:15-20`, `:117-174`, `:179`, `:213`. **Impact:** some users needing follow-up are not visible from Dashboard. **Fix direction:** decide whether the card is a page preview or cohort-level alert; make scope and filters explicit.

## 13. Recommended remediation order

1. **Resolve department scope policy:** explicitly decide department vs assigned-student scope, trusted assignment authority, and handling of defaulted/legacy CS profiles. Inspect existing records read-only before changing defaults or access.
2. **Verify actual data causes:** using an authorized test account and read-only database query, count faculty profiles by department/default indicators; count matching student profiles; latest session statuses; completed/evaluated rounds; Mock Drive contexts; snapshots; competency configs; mapping states; countable mapping rows. Do not expose candidate PII in the report.
3. **Correct competency empty diagnostics:** preserve individual valid competency scores even where overall weighting is invalid/unavailable; return/display a safe reason category and mapping lifecycle, and group by stable ID/version. Add focused service/API/UI tests.
4. **Design a faculty-safe attempt-history data contract:** server-side authorize before querying; include attempt/context/drive identity only when allowed; support pagination and assessment-specific results/status. Do not make global staff endpoints faculty-accessible.
5. **Define faculty Mock Drive and Reports product policies:** no UI-only workaround can establish data permission. Implement server scope first, then page states and filters.
6. **Harden CSV export** against spreadsheet formula injection while retaining the authorized-field allowlist and clearly explaining page vs whole-cohort scope.
7. **Measure and optimize queries** after representative data size is known. Avoid eager-loading every historical session when only the latest is returned; batch competency computation if profiler confirms query growth.

## 14. Existing components, APIs, and services to reuse

- `FacultyDashboard.jsx` already provides route-level section navigation, server-side roster filters/pages, loading/error/empty states, and scoped cohort summary.
- `GET /profile/cohort/students` is the existing faculty-scoped roster API. Keep its faculty auth/scope behavior; extend only after designing history fields and access tests.
- `faculty_access_service.py` is the shared server-side student-department access check for individual records.
- `score_session_competencies` is the authority for pinned-snapshot competency scoring; `competency_mapping_service.py` is the explicit topic-mapping lifecycle. Do not replace it with raw-score guesses.
- Existing persisted records provide the join path: `AssessmentSession`/`AssessmentRound`, `AptitudeAttempt`, `CodingSubmission`, `InterviewSession`/`InterviewTurn`, `AssessmentContext`, `MockDrive`, and `CompetencyEvidenceMapping`.
- `GET /interview/session/{id}/report` and `GET /coding/submission/{id}` already enforce faculty department access for a known student/item. They need a safe roster/history source to identify records; they are not cohort listing APIs.

## 15. Missing backend/product capabilities

- Trusted faculty department or student assignment workflow and a safe way to identify defaulted legacy assignments.
- Faculty-scoped all-attempt history with context/assessment identity and result drill-down.
- Competency result diagnostics in faculty response: snapshot/config status, mapping state/reason, valid per-competency values, stable competency ID and version.
- A policy-approved faculty Mock Drive query/API. Current TPO/admin roster access cannot simply be reused.
- Faculty report aggregation endpoints with defined cohort scope, date periods, stable denominators, and authorization.
- Optional review-task/pending-actions source and comparable historical-score policy for “Students improving.”

## 16. Verification gaps and required runtime tests

No live database query, authenticated API request, browser session, or role-switch test was performed. Current data cannot establish which specific cause triggered an observed empty card. The following remain required:

- In a read-only authorized DB session, verify faculty assignment provenance/defaults, student department distribution, session/round/result counts, contexts, pinned snapshot validity, competency configuration, mapping statuses, and evidence coverage.
- Authenticated API checks with at least two faculty scopes: correct department roster; cross-department query returns 403; missing profiles do not leak; department PUT cannot self-change; profile-created default scope behavior is reviewed.
- Per-status roster API checks for zero-result vs unavailable/error, pagination/search consistency, and latest-session selection against persisted records.
- Seeded isolated test cases for competency states: no context, missing snapshot, no competencies, pending/failed mapping, unmatched/ambiguous topic, non-countable coding result, valid zero, partial/provisional evidence, invalid weights with assessed component rows, and separate same-name competency IDs.
- Faculty API checks for interview/coding/resume direct object access outside the department and for authorized in-scope access. Confirm TPO/admin-only Mock Drive and global report routes remain inaccessible to faculty.
- Browser checks of all six sections, their loading/error/empty states, page/filter persistence, assessment detail limitations, responsive sidebar, CSV download, and spreadsheet-safe export behavior.
- Test-only DB settings are not evidence about production/dev row counts. Any database tests must use the isolated test database specified by `docs/DATABASE_WORKFLOW.md`, never the development DB.

Existing source-level test coverage was inspected but tests were **not run as part of this audit**. The previous audit records focused role/scope tests and a prior TPO report records isolated report/roster tests; those results do not replace live verification. The current environment's actual live DB/API availability was not probed.

## 17. Scope confirmation

This audit added only `docs/audits/FACULTY_DASHBOARD_FUNCTIONAL_AUDIT.md`. No TPO dashboard, TPO page, TPO component, TPO API, backend application source, schema, migration, or test file was edited for this task. All pre-existing modified/untracked work was preserved.
