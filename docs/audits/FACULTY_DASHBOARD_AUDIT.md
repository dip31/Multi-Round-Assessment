# Faculty Dashboard Audit

**Scope:** Read-only audit of the current Faculty Dashboard and its related route, API, model, and reporting code. No application code, API, schema, or configuration was changed for this audit. Findings below are from source inspection; live authenticated API/database and browser checks were not performed.

## Implementation Follow-up — 2026-10-23

This document records the pre-redesign audit. The following source fixes and workspace changes have since been made based on those findings:

- Faculty cohort access is derived from the authenticated faculty profile department. A conflicting `department` query returns 403; department-scoped results exclude students without a matching profile/department. TPO/admin retain institution-wide scope and may narrow by department.
- Faculty roster responses omit contact and demographic fields, preserve absent profile values as `null`, and expose persisted latest-session round data. Round scores are returned only when matching evaluated aptitude attempts, scored coding submissions, or scored interview turns exist; evaluated zero remains zero. Search, status filtering, and pagination run server-side. Summary counts use the full authorized scope. Cross-department access to interview reports/question pools, coding submissions, and resume files is constrained by the shared faculty scope check.
- Faculty users are denied institution-wide `/report/admin/*` analytics. TPO/admin remain authorized.
- Faculty cannot change the department that defines their authorization scope through `/profile/faculty/me`; the profile field is read-only in the faculty profile editor. Department assignment still requires an authorized administrator process, which is not present in the inspected API.
- The Faculty Dashboard now has the six requested navigation items. Dashboard and roster/assessment sections use the authorized cohort API; competency insight values use the existing pinned-blueprint scoring service where evidence exists. Mock Drives remain a placeholder because existing drive routes are TPO/admin scoped. Reports export the currently filtered roster page only.
- Unavailable metrics are disclosed: score averages are withheld because scales are not verified comparable; improvement and review-task counts are unavailable; only latest-session assessment history is exposed.

Focused API tests for department isolation, faculty self-service department changes, missing department exclusion, zero-vs-null score evidence, global report roles, search/status filters, pagination, and existing TPO session timing passed (7 tests). `FacultyDashboard.jsx` ESLint and production build passed. Linting `Profile.jsx` reports seven existing unused-variable/empty-catch issues outside the department field change. The full `test_mock_drive_roster.py` run had 11 passing tests and one failure in `test_roster_derives_participants_and_counts_from_contexts`: that test completes a coding round without any evaluated coding submission, then expects a non-null overall score. The current result service leaves that score unavailable, which is consistent with the no-fabricated-score rule; no Mock Drive scoring code was changed here. `test_phase2_roles.py` could not be run successfully because no isolated PostgreSQL `TEST_DATABASE_URL` is configured; source compilation passed.

Live database/API and authenticated browser verification remain outstanding. The six navigation items and responsive behavior were validated by build/source inspection, not by browser automation. The department-based policy remains an assumption pending product-owner confirmation; existing model defaults may make some legacy department values indistinguishable from explicitly assigned values.

## 1. Executive Summary

The current Faculty Dashboard is a single page at `/faculty/dashboard`, implemented in `frontend/src/pages/FacultyDashboard.jsx`. It loads the logged-in user's profile, a department-filtered student roster, and a global cohort-statistics endpoint. It provides four KPI cards, a search/status filter, a horizontally scrollable student table, and an inline student scorecard modal.

The page is functional in the limited sense that it has a route, role guard, API calls, loading skeleton, toast on profile-load failure, roster display, filtering, refresh, and modal. It does **not** implement the six-section navigation or most of the intended faculty workflows. Several displayed values are demonstrably misleading: hardcoded fallbacks replace missing student data, zero scores are displayed as fabricated values or “Pending,” and “Institution Avg” is global data with a static fallback. Most significantly, the cohort endpoint permits a faculty caller to provide a different department query parameter, and its filtering also includes students without a profile/department. This is a confirmed authorization boundary defect in source; exploitation was not tested against a running server.

## 2. Project File Map

| Area | Files | Role |
|---|---|---|
| Faculty page | `frontend/src/pages/FacultyDashboard.jsx` | Profile, roster and stats fetch; local metrics; filtering; table and modal. |
| Route and login | `frontend/src/App.jsx`, `frontend/src/components/RoleRoute.jsx`, `frontend/src/pages/Login.jsx` | `/faculty/dashboard` route restricted client-side to faculty/admin; role-based post-login redirect. |
| Navigation | `frontend/src/components/Navbar.jsx` | Faculty brand/dashboard link and profile/logout navigation; no six-section faculty nav. |
| API client | `frontend/src/services/api.js` | `/api/v1` base URL, JWT bearer attachment from local storage, 401 redirect behavior. |
| Faculty/cohort API | `app/api/v1/profile.py` | `/profile/me`, `/profile/faculty/me`, `/profile/cohort/students`. |
| Aggregate report API | `app/modules/report/routers/report_router.py`, `app/modules/report/schemas/report_schema.py` | `/report/admin/cohort-stats`; role gate permits admin, faculty, TPO. |
| Candidate report API | `app/modules/report/routers/candidate_report_router.py` | Student analytics and candidate reports; student analytics endpoint is scoped to the caller's own sessions. |
| Interview report access | `app/modules/interview/routers/interview_router.py` | Interview report endpoint uses `_get_interview_for_user`; staff access is broader than faculty-department scope. |
| Mock Drive API | `app/api/v1/mock_drive.py`, `app/services/mock_drive_service.py` | TPO/admin drive management, student drive participation/results; no faculty dashboard drive section. |
| Relevant models | `app/models/profile.py`, `app/models/user.py`, `app/models/assessment.py` | Student/faculty profile, user role, assessment session and round data. |

No dedicated faculty dashboard service, faculty-assignment join model, report page, or six-section faculty navigation was found in the inspected code.

## 3. Current Architecture and Data Flow

1. `App.jsx` maps `/faculty/dashboard` to `FacultyDashboard` inside `RoleRoute allowedRoles={['faculty', 'admin']}`. `Login.jsx` redirects faculty to this path. `RoleRoute` reads role/token from local storage; it is a client-side route guard, not server authorization.
2. `FacultyDashboard` calls `GET /api/v1/profile/me`. `api.js` attaches the stored bearer token. The page uses `user.faculty_profile.department`, but substitutes `Computer Science` if missing.
3. The page concurrently calls:
   - `GET /api/v1/profile/cohort/students?department=<profile department>`
   - `GET /api/v1/report/admin/cohort-stats`
4. Each call catches its own error and turns it into an empty roster or `null` stats, so only a profile request failure reaches the page toast.
5. `/profile/cohort/students` queries student users, loads each student's latest `AssessmentSession` and rounds, then assembles an in-memory response. `StudentProfile`, `AssessmentSession`, and `AssessmentRound` supply the fields.
6. `/report/admin/cohort-stats` queries all students, completed rounds, completed sessions, and interview/aptitude activity globally. It has no department or faculty scope parameter.
7. The UI calculates average score and completion rate from the returned roster, filters that array locally, and opens the selected row's data in a modal.

The department cohort query is N+1: it loads all student users and then queries the latest session separately for each user, with round relationships also read for each session. No pagination is present.

## 4. Section-by-Section Audit

### A. Dashboard

**Exists:** Yes, only as the KPI/roster page described above.

**Implemented:** Supervised Students, Batch Average Score, Completion Rate, Institution Avg; search by name/roll/target role; session-status filter; roster table; refresh; Review Card modal.

**Confirmed issues:**

- `FacultyDashboard.jsx:72-75` averages every roster row's `overall_score`, treating missing session scores as `0` and including students with no evaluated result in the denominator. The card says “Batch Average Score” and “Across all assessment rounds,” although the API supplies only the latest session's `total_score` per student. This is not an all-round, evaluated-only average.
- `FacultyDashboard.jsx:77-78` defines completion as `session_status === 'completed'` divided by all roster rows, then the card says those students “completed all 3 rounds.” The API supplies the latest session status and latest session's round records; neither proves all three round types were configured and completed. Practice sessions can be independent, so the displayed “all 3” claim is unsupported by this field.
- `FacultyDashboard.jsx:159` labels global `/report/admin/cohort-stats.avg_overall_score` as “Institution Avg,” despite the calculation querying all completed sessions in the database, with no institution or department filter. If the request fails, it displays a fixed `74.2%` as if it were a live benchmark.
- The search and status filter only affect the roster array. KPI calculations are from the unfiltered roster. There are no date, drive, or cohort-period filters.
- No charts, trends, activity summary, or pending-action queue exist on this page.

### B. My Students

**Exists:** Partially. The roster and a “Review Card” modal are embedded in Dashboard; there is no distinct My Students route/page, pagination, sort control, student profile navigation, or assessment-history view.

**Confirmed issues:**

- Search and status filtering are client-side and work only on the already-loaded array. There is no pagination or sorting.
- The modal shows contact and sensitive profile fields (email, mobile, date of birth, gender, nationality) alongside academic/assessment fields. This increases exposure without a documented mentoring need. The API returns those fields for the whole cohort.
- Missing profile values are substituted with defaults by the API and/or UI, e.g. CGPA 7.5, target role “Software Engineer,” and “Male” for missing gender. These appear as student facts although their source is absent.
- Access-control concerns for the roster endpoint are detailed in Security and Permissions.

### C. Assessments

**Exists:** Not as a faculty section. The embedded roster shows only the latest session's aptitude/coding/interview statuses and scores. It has no assessment listing, assessment-type filters, review queue, or per-attempt history.

The cohort API exposes only three fixed round keys and uses the latest session (`AssessmentSession.id DESC`). The response is not drive-specific and cannot represent arbitrary configured Mock Drive rounds. Status aggregation against live records was not verified.

### D. Competency Insights

**Exists:** Not in the Faculty Dashboard.

There is an admin/staff `GET /report/admin/skill-gaps` endpoint in `app/modules/report/routers/report_router.py`, but the faculty page does not call or link to it. The endpoint computes topic aggregates from completed interview turns, globally, using topic matching; it is not a faculty-department competency evidence view. No faculty-specific competency eligibility or evidence coverage was found in this page.

### E. Mock Drives

**Exists:** Not in the Faculty Dashboard.

Mock Drive management routes in `app/api/v1/mock_drive.py` are explicitly TPO/admin for management and student-only for participation endpoints. There is no faculty-facing drive listing, participation roster, or round-wise result view wired into `FacultyDashboard`. The service/model may contain data, but no authorized faculty workflow was found in the inspected route/UI.

### F. Reports

**Exists:** Partially at the API level; absent as a faculty UI section.

`/report/admin/cohort-stats`, `/report/admin/skill-gaps`, and `/report/admin/all-candidates` are grouped under an admin reporting prefix but the `check_admin` helper also permits faculty and TPO. These endpoints do not apply the faculty department restriction. No report navigation, filters, or export controls exist on `FacultyDashboard`.

## 5. Data Accuracy Findings

| Finding | Evidence and actual behavior | Expected behavior / impact | Status |
|---|---|---|---|
| Missing scores become invented values | `FacultyDashboard.jsx:273,285,297` uses `apt.score || 85`, `cod.score || 90`, `intv.score || 80`; a legitimate `0` is also replaced. | Preserve recorded zero; show unavailable only for null/missing. The roster can report a false score. | Confirmed UI bug |
| Zero score shown as Pending in modal | `FacultyDashboard.jsx:401,407,413` uses truthiness for score display. `0` renders “Pending.” | Distinguish evaluated zero from absent score/status. | Confirmed UI bug |
| Student academic and demographic defaults are shown as facts | `profile.py:167-179` and `StudentProfile` model defaults (`app/models/profile.py`) fill missing profile values; UI adds additional defaults including gender. | Missing records/fields should remain visibly unavailable. Students can appear to have invented CGPA, role, or demographic values. | Confirmed data presentation issue |
| Batch average has an unsupported denominator/label | UI averages `overall_score` for every roster row, including no-session default zero; endpoint returns latest session's score only. | Define eligible scored sessions/students and label the metric to match its denominator and scale. | Confirmed metric mismatch |
| Completion claim is unsupported | `session_status` is read from latest session; UI calls completed session “all 3 rounds.” Roster API exposes latest session's fixed keys, not proof of all three were required and completed. | Derive completion from configured required rounds for the relevant assessment/drive. | Confirmed unsupported label |
| Institution average is global and has a fixed fallback | Stats endpoint counts all students and averages all completed rounds/sessions without department/institution filter; UI presents `avg_overall_score` as Institution Avg and falls back to `74.2%`. | Use a validated scoped benchmark or say unavailable; do not present a hardcoded value as live. | Confirmed data/scope mismatch |
| Global completion calculations can mix sessions and students | `/cohort-stats` divides distinct completed **session IDs** by total **student users**. `all_three_count` counts sessions with at least three completed rounds, regardless of distinct round types. Repeated sessions can inflate ratios; duplicate same-type rounds can satisfy “all three.” | Count unique eligible students and required distinct round types under a consistent cohort/context. | Confirmed query-definition defect; runtime impact not measured |
| Failures are rendered like empty data | Roster/stats request failures are caught and converted to empty list/null (`FacultyDashboard.jsx:38-39`). Empty roster then says “No students found”; stats displays zero or fallback. | Surface endpoint-specific unavailable/error states so network/auth/server failures are not mistaken for a truly empty cohort. | Confirmed UI state bug |
| Latest-session logic hides historical attempts | `profile.py` uses `.order_by(AssessmentSession.id.desc()).first()`; no history is returned. | Assessment views should identify the selected drive/attempt or clearly label the latest practice attempt. | Confirmed limitation for history/reports |

Score units were not treated as confirmed incorrect: round scores are averaged by `_finalize_session_score` in `app/modules/practice/routers/practice_router.py`, but this audit did not establish a single guaranteed scale across all relevant assessment contexts.

## 6. UI and Usability Findings

- The page has a clear greeting and simple KPI/roster hierarchy, but it is one long page and has no six-item faculty navigation.
- The table uses a small text size and a horizontal overflow container; no mobile browser/device check was performed.
- The filter buttons do not expose `aria-pressed`; the search input has a placeholder but no associated visible label.
- The scorecard overlay lacks dialog semantics (`role="dialog"`, `aria-modal`), Escape handling, focus trapping/return, and an accessible name on its close icon button.
- Empty roster text is also used after roster API failure, so a user cannot distinguish an empty department from a service problem.
- No chart/drill-down or pending review action is present.
- There is no explicit loading state for a manual refresh beyond the full-page skeleton, and the initial load skeleton does not preserve the page shell.
- Icons/emojis in the source show encoding corruption in this checkout (`ðŸ...`, `â†»`), which may render incorrectly in the UI. Browser rendering was not verified.

These are source-level observations; visual quality and responsiveness need browser verification.

## 7. Security and Permissions

### Confirmed high-priority department boundary defect

`app/api/v1/profile.py:get_cohort_students` authorizes `faculty`, `tpo`, and `admin`, but sets `target_dept = department` from the caller-supplied query parameter and only falls back to the faculty profile department when no parameter is supplied. The dashboard always supplies the profile department, but an authenticated faculty caller can change the request parameter to another department. The query then returns students from that requested department. Additionally, the row filter includes students with no profile or no department in every requested department because it excludes only `sp and sp.department` mismatches.

**Impact:** source permits a faculty account to retrieve other department students' profile and assessment fields. No request was sent to a running server; the finding is confirmed by endpoint logic, not a live exploit test.

### Broad staff report access

`report_router.py:check_admin` allows faculty, TPO, and admin. `/report/admin/cohort-stats` and `/report/admin/skill-gaps` aggregate across all students/interview data without a faculty department constraint. `/report/admin/all-candidates` is similarly behind this shared role check. These endpoints can expose global aggregate or candidate information to faculty; whether intended institution-wide access is policy-approved is **not verified**. The Faculty Dashboard currently calls only global cohort stats.

### Other access controls

- Frontend `RoleRoute` checks local-storage role and token; backend endpoints independently use `get_current_user` and role checks. Client guards must not be treated as the security boundary.
- Student-specific `/report/student-analytics` uses `current_user.id` for session queries, as documented in its code.
- Interview report route calls `_get_interview_for_user`; its staff-access policy is broader than department scoping and should be assessed alongside any future faculty report UI.
- Mock Drive management endpoints require TPO/admin; student participation routes require student. No faculty drive route was found.
- No faculty-to-student assignment relation was identified in the inspected models; current apparent scope is department-based, not assigned students.

## 8. Feature Status Table

| Intended section | Status | Current implementation |
|---|---|---|
| Dashboard | Partially implemented | One page with four KPIs, roster, search/status filter and scorecard. Several KPI/score defects above. |
| My Students | Partially implemented | Roster and inline modal only; no independent page, pagination, sorting, or history. |
| Assessments | Missing as a faculty section | Latest session's three fixed round statuses appear in roster only. |
| Competency Insights | Missing in faculty UI | Global staff skill-gap endpoint exists, not wired or department-scoped. |
| Mock Drives | Missing in faculty UI | TPO/admin drive management exists; no faculty page/workflow. |
| Reports | Partially implemented at API level | Global staff report endpoints exist; no faculty report UI, filters, or export. |

The six labels are not currently implemented as navigation. No duplicate Faculty Dashboard page/route was found; there are separate TPO and Admin dashboards for other roles.

## 9. Prioritized Issues

1. **Critical — Faculty can request a different department's roster.** `get_cohort_students` trusts the faculty-supplied `department` query. This can disclose student profile and assessment fields across departments.
2. **High — Scores are fabricated or misrepresented.** Zero scores become fallback scores in the roster and “Pending” in the modal; missing CGPA/role/demographic values can also be filled with defaults.
3. **High — Global statistics are presented as a department/institution benchmark.** The endpoint is global; the UI has a fixed `74.2%` fallback and inconsistent roster/global scopes.
4. **High — Completion and average metrics have unsupported semantics.** “Completed all 3 rounds” is derived from session status; the batch average treats unscored/no-session students as zero and is based on latest session values.
5. **Medium — API failures appear as empty/zero data.** Roster and stats errors are silently collapsed to empty/null and the UI's empty/fallback states obscure them.
6. **Medium — The six requested destination sections are not implemented.** Assessments, competency insights, Mock Drives, Reports, and standalone My Students are absent or API-only.
7. **Medium — Cohort APIs have unbounded/N+1 loading and expose more profile fields than the roster needs.** This can affect latency and needlessly increases the data returned to faculty.
8. **Low — Accessibility and responsive details need work.** Filter state labels, dialog semantics/focus behavior, and small table text need browser review.

“Critical” here refers to authorization/data isolation risk from source inspection. There was no live penetration test.

## 10. Recommended Redesign Plan

Keep the proposed six labels as simple navigation, while making only the data-backed capabilities visible initially:

1. **Dashboard:** scoped student count, result coverage, and a small progress summary; omit metrics when the denominator or source is unavailable. Separate cohort-scoped values from institution-wide benchmarks.
2. **My Students:** searchable, paginated roster limited server-side to authorized students; use a compact list and a least-privilege student detail view with explicit attempt/drive selection.
3. **Assessments:** list actual assessment attempts and required/configured rounds with pending/completed/evaluated states sourced from persisted context.
4. **Competency Insights:** expose only measured competencies with evidence counts and valid-score rules; show unavailable when evidence is insufficient.
5. **Mock Drives:** defer until an approved faculty authorization scope and faculty-safe drive/candidate result source are defined. Existing TPO endpoints are not suitable for faculty reuse as-is.
6. **Reports:** use existing report calculations only after defining faculty scope, time period, cohort, and denominators. Do not label global stats as department values.

Recommended sequence: close the backend department authorization gap first; then correct score/null semantics and metric definitions; define faculty access scope for global reports; improve error/unavailable handling; only then build navigation and additional sections. Reuse the current profile API/client and existing assessment/report tables after establishing the authority and scope for each metric.

## 11. Files Likely to Require Changes Later

List only; no changes made to these files in this audit:

- `frontend/src/pages/FacultyDashboard.jsx`
- `frontend/src/App.jsx`
- `frontend/src/components/RoleRoute.jsx`
- `frontend/src/components/Navbar.jsx`
- `app/api/v1/profile.py`
- `app/modules/report/routers/report_router.py`
- `app/modules/report/schemas/report_schema.py`
- `app/modules/report/routers/candidate_report_router.py`
- `app/api/v1/mock_drive.py` and a future faculty-scoped service/router if approved
- `app/models/profile.py`, `app/models/assessment.py`, and potentially a faculty assignment model only if product policy requires assignment-level authorization
- Focused backend authorization/aggregation tests and frontend metric/state tests

## 12. Verification Gaps

- No database was queried; actual student counts, department distribution, repeated attempts, null-profile cases, score distributions, and data leakage were not measured.
- No authenticated API call was made, so endpoint response shapes/status codes and server runtime behavior were not verified.
- No browser was opened. Responsive layout, visual encoding, keyboard behavior, and role redirects need manual browser verification.
- No tests were run because this was a source audit; no code was changed.
- The intended scope policy (department vs assigned students vs whole institution) is not documented in the inspected code. Confirm policy with the product owner before design/integration.
- Whether faculty should access `/report/admin/all-candidates`, global skill gaps, or cross-department aggregates requires an authorization decision.
- Exact score units across historic and Mock Drive contexts were not established; verify scale and valid-result eligibility before reusing score averages.

## 13. Source References

Line numbers are approximate anchors in the audited checkout:

- `frontend/src/pages/FacultyDashboard.jsx`: data loads (~21–45), filters (~51–68), metrics (~72–78), KPI fallbacks (~159), roster score fallbacks (~273–297), modal score truthiness (~401–413).
- `app/api/v1/profile.py:get_cohort_students`: role gate and query-scope selection (~114–140), latest-session and round assembly (~142–197).
- `app/modules/report/routers/report_router.py:get_cohort_stats`: global candidate/score queries and completion denominators (~38–103).
- `app/modules/report/routers/report_router.py:check_admin`: shared staff permission gate (~31–35).
- `app/modules/report/routers/candidate_report_router.py:get_detailed_student_analytics`: current-user session scope (~381 onward).
- `app/modules/practice/routers/practice_router.py:_finalize_session_score`: session total is the mean of completed round scores (~671–683).
- `app/models/profile.py`: StudentProfile and FacultyProfile fields/defaults (~20–80).
- `app/api/v1/mock_drive.py`: TPO/admin and student role gates (~48–65).
