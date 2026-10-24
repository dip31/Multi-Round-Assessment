# Faculty-Assigned Assessment End-to-End Integration Audit

**Audit type:** Source and focused-test audit; no implementation changes.
**Repository state:** `feature/divesh`, Windows workspace, inspected 2026-10-24.
**Runtime status:** Authenticated browser and live-database verification were unavailable; see Verification.

## Executive summary

The current worktree contains a persisted faculty-assignment flow that connects ordered assessment definitions to the existing Aptitude, Coding, and Interview engines. Faculty creation persists the assessment, ordered rounds, authorized student assignments, and availability in one database transaction. A student sees only their own assignments. Starting a round checks ownership, publication/availability, sequence, and active-attempt state, then links the existing engine session and round to that assignment. Engine completion callbacks finalize the one-round assigned session/context; the next round becomes eligible only after that finalization. The current tests cover these API transitions and persisted links using in-memory SQLite.

This is **not yet verified as a full E2E workflow**. There was no running frontend/backend listener, no configured isolated PostgreSQL test database, and no authenticated browser session. The lifecycle test creates InterviewSession rows directly and completes a Coding round without exercising actual Coding problem provisioning/submission; therefore it does not prove question delivery, Judge0 execution, or a real interview interaction. The migration is present in the worktree but was not applied or checked against a database.

The code separates a completed attempt from an evaluated result, preserving `null` score for unavailable/pending evaluation in the faculty-assignment summary. Evaluation evidence is derived separately for each engine. The faculty UI shows persisted scores and evidence; it explicitly says interview turn-level feedback is not persisted by the current engine. The optional consolidated student report is broader practice history, not filtered to only the selected assignment.

## Scope and repository safety

`git status --short` was inspected before investigation. The checkout already had numerous modified and untracked files, including the faculty-assignment API, model, services, migration, frontend workspace, and tests. No staged changes were present. These files are part of the pre-existing worktree under review; this audit does not establish that they are committed or deployed. No existing file was edited. The only intended change from this audit is this report.

## Architecture and lifecycle

```text
Faculty Dashboard / Practice Assessment Workspace
  GET  /faculty/practice-assessments/roster
  POST /faculty/practice-assessments
       â”œâ”€ FacultyPracticeAssessment (published; availability)
       â”œâ”€ FacultyPracticeAssessmentRound (ordered sequence/configuration)
       â””â”€ FacultyPracticeAssignment (authorized recipient)
                         â”‚
Student Practice Mode   â”‚
  GET /student/practice-assignments
  POST /practice/start {assignment_id, assessment_round_id}
       â”œâ”€ authorization, time-window, ordering and active-attempt checks
       â”œâ”€ AssessmentContext purpose=faculty_assignment:<assignment_id>
       â”œâ”€ AssessmentSession + AssessmentRound (existing practice engine)
       â””â”€ FacultyPracticeRoundAttempt links assignment round â†” engine session/round
                         â”‚
       Aptitude finish / Coding finish or timer / Interview completion
                         â””â”€ finalize assigned round, session and context
                                      â”‚
Faculty review
  GET /faculty/practice-assessments
  GET /faculty/practice-assessments/{id}
       â””â”€ joins persisted assignment link to actual engine evaluation evidence
```

### Faculty creation and persistence

`frontend/src/components/FacultyPracticeAssessmentWorkspace.jsx` owns the create, assigned-assessments, and review-results tabs. It loads the faculty roster and assessment list, then posts the selected student IDs, ordered rounds, and availability to `/faculty/practice-assessments`. The request key is sent as `Idempotency-Key`.

`app/api/v1/faculty_practice_assessments.py` requires the faculty role, converts timezone-aware request datetimes to UTC-naive values, and exposes the faculty and student endpoints. `app/services/faculty_practice_assignment_service.py:create_assessment` validates a title, 1â€“10 rounds, supported round/practice types, and at least one recipient. It derives department scope from the faculty profile and rejects any selected student outside that department. Assessment, round definitions, and recipient rows are committed together. New assessments are created directly with status `published`; there is no separate draft/publish workflow in this implementation.

The migration `alembic/versions/add_faculty_practice_assignments.py` adds four tables: assessments, ordered assessment rounds, student assignments, and engine-attempt links. The database uses a uniqueness constraint for one assignment per recipient, one sequence number per assessment, one attempt link per assigned round, and one link per engine session/round. The association table points to the actual `assessment_sessions` and `assessment_rounds`; engine-specific result evidence remains in the existing engine tables.

### Student visibility and start authorization

`frontend/src/pages/PracticeOverview.jsx` fetches `/student/practice-assignments` and renders each assignment's title, dates, round sequence/status, and next eligible action. `get_student_assignment` scopes lookup by both assignment ID and authenticated student ID. The student start request passes both the assignment and configured round IDs to `/practice/start`.

Before starting, `validate_assigned_round_start` verifies the authenticated student owns the assignment; the assessment is published and within its availability window; the requested round belongs to that assessment; and earlier configured rounds have completed. Existing attempted rounds cannot be restarted, except that the same active linked round can be resumed. A student cannot choose an arbitrary engine type because the request type and practice type must match the stored round definition. Existing active-session protections prevent changing to a different active attempt.

Each assigned round is created as its own existing `AssessmentSession` and `AssessmentRound`, with an `AssessmentContext` purpose of `faculty_assignment:<id>`. The unique `FacultyPracticeRoundAttempt` association stores the link. A stable user-row lock in `create_session` serializes concurrent creation of a student's first active session; the unique association constraint and retry lookup protect duplicate links. The focused suite verifies repeated start returns the same active attempt, but it does not issue two simultaneous requests.

Availability is stored in the existing naive `DateTime` columns. The faculty builder serializes browser-local `datetime-local` values to ISO UTC; the API normalizes explicit offsets to UTC then removes timezone metadata, and start eligibility compares UTC-naive values to backend UTC time. The start and end comparisons reject before start and after end; exactly the end timestamp is accepted (inclusive boundary). This convention is supported by a focused round-trip test, but no actual database storage or runtime timezone was inspected. A separate frontend helper test covers UTC-naive and timezone-aware presentation.

### Existing engine execution and result linkage

| Configured round | Existing engine execution | Completion callback in current worktree | Evaluation evidence in assignment API | Audit result |
|---|---|---|---|---|
| Aptitude | `/practice/start` creates the round; the existing Aptitude UI loads and submits questions associated with its `AssessmentRound`. `/aptitude/finish` calculates and persists the engine round score and completes the round. | Calls `finalize_faculty_assigned_attempt`; the helper acts only when a `FacultyPracticeRoundAttempt` link exists and its context purpose matches the assigned assessment. | Reads `AptitudeAttempt` rows for the linked engine round. `is_correct` values determine evaluated count and number correct. Missing/incomplete evaluation yields no assignment score. | **PARTIAL** â€” source linkage and finish callback tests pass; no browser/question-bank attempt was run. |
| Coding | Existing `/coding/start` provisions problems for the active round; `/coding/submit` runs the existing evaluator and persists submissions against the round; `/coding/finish` and submit-time timeout finalization complete it. | Calls assigned-session finalization after explicit finish and timer/expiry finalization paths. | Reads round-linked `CodingSubmission` and `SessionProblem`. Running submissions yield pending; internal errors yield failed; all assigned problems need scored submissions before the API reports evaluated. Assignment score is the sum of each problem's best fractional score, with `score_max` equal to assigned problem count. This is distinct from the engine `AssessmentRound.score`, which is the average fraction. | **PARTIAL** â€” source linkage and callback test pass; no real problem loading, submission/Judge0 run, or timer expiration was executed. |
| Interview | The assigned Interview round routes through the existing resume/pool workflow, which associates an approved question pool and `InterviewSession` with the active assessment session. Student responses are processed by the existing interview endpoints. | Both natural final response and `/interview/session/{id}/complete` call assigned finalization after completing the linked interview round. The early-completion path uses the specific interview's session. | Reads candidate responses and `final_score` from `InterviewTurn` rows belonging to the linked engine session. No responses produce `attempt_completed`; responses without scores produce evaluation pending; scored turns are averaged. | **PARTIAL** â€” completion callback test passes, but it inserts an InterviewSession directly and does not exercise resume, question generation, response scoring, or browser interaction. |

The Coding timer callback is source-visible in the expiration branch of `/coding/submit`; no wall-clock timer was allowed to expire during testing. Aptitude's finish callback is directly exercised by the focused test, but automatic browser countdown behavior is not.

One conditional linkage concern exists in Interview's natural â€œlast responseâ€ completion path: after completing the `InterviewSession` from the request, the handler locates an assessment session by the user's latest `in_progress` session rather than using that interview's `InterviewSession.session_id`. The early `/complete` path does use the specific interview session. Under the normal one-active-session invariant these identify the same row, but a legacy/parallel active session could cause the natural completion callback to finalize a different interview round. This should be checked or narrowly scoped to `interview.session_id` before supporting multiple active sessions; it was not reproduced at runtime.

### Session/context finalization and progression

`finalize_faculty_assigned_attempt` first resolves a link for the engine round, checks that the linked session belongs to the current user and the round is completed, and verifies the context purpose matches the assignment. It refuses to close a session if any engine round remains active. It completes an in-progress enclosing session and then its context. The helper returns without changing independent practice or Mock Drive sessions because neither has the assignment link/purpose.

The serializer exposes the first in-progress round or first not-started round. A later round is eligible only if all previous rounds have a recognized completed attempt state (`evaluated`, `evaluation_pending`, or `attempt_completed`) **and** the previous engine session and context are both completed. Thus evaluation pending does not block the next round, while failed finalization does. The start endpoint repeats the sequencing and finalization checks server-side; a UI refresh is not the authority.

The legacy `/coding/start-after-aptitude` operation returns without creating a Coding round when the latest session is a faculty assignment. This prevents a stray Coding round/session from bypassing the configured assessment-round sequence.

### Faculty monitoring and review

The faculty list and detail endpoints are restricted to the owning faculty member. The roster and assignment creation use department scope from `FacultyProfile`; detail serialization filters recipient visibility against the owner's current department. Student assignment endpoints are limited to the authenticated student's own rows. These are source-level access checks; no cross-account live API test was possible.

The Assigned Assessments and Review Results tabs call the faculty list/detail endpoints. The review table shows ordered round, status, persisted score, and engine-specific evidence. It preserves unavailable scores as unavailable instead of substituting zero. Aptitude score is correct answers over evaluated questions; Coding evidence reports evaluated submissions and problem-point total; Interview evidence reports evaluated turn count. The UI explicitly says interview turn-level feedback is not persisted in the current engine. The â€œOpen consolidated student practice reportâ€ action fetches the separate student practice-history report, which covers that student's authorized practice records rather than only the selected assignment. Therefore, assignment-specific score/evidence is available, but detailed assignment-scoped answer/submission/feedback review is not established by this table.

## Round-specific integration matrix

| Requirement | Aptitude | Coding | Interview |
|---|---|---|---|
| Definition persisted in requested order | **PASS** â€” sequence unique and ordered | **PASS** | **PASS** |
| Student assignment and round access checked on backend | **PASS** â€” linked assignment and configured type validated | **PASS** | **PASS** |
| Existing engine round linked to assignment | **PASS** â€” link stores `session_id`/`round_id` | **PASS** | **PASS** |
| Engine-specific persisted evidence associated to link | **PASS** â€” `AptitudeAttempt.round_id` | **PASS** â€” `CodingSubmission.round_id` and `SessionProblem.round_id` | **PARTIAL** â€” turns are linked through `InterviewSession.session_id`; evidence is session-level, not round-level |
| Finish callback finalizes assigned session/context | **PASS** in tested callback | **PASS** in tested explicit finish; timer path source-inspected only | **PASS** in tested early completion; natural completion source-inspected only |
| Evaluation/pending score state | **PASS** at assignment serialization | **PASS** at assignment serialization | **PASS** at assignment serialization |
| Full engine/browser verification | **NOT VERIFIED** | **NOT VERIFIED** | **NOT VERIFIED** |

Seeing Round 1 results is **not proof** that all rounds are integrated. Each round has its own engine lifecycle and evidence model, so completion and results must be established independently. The current focused tests include all three completion paths and detail serialization, but use fixtures and do not exercise the complete user-facing engines.

## Findings and remaining risks

### A1 â€” End-to-end engine execution has not been demonstrated (High verification gap)

**Evidence:** The test `test_engine_finish_callbacks_release_each_assigned_round` starts linked rounds and invokes Aptitude finish, Coding finish, and Interview early-complete endpoints, but it does not answer actual Aptitude questions, does not provision/submit a Coding problem, and directly inserts an InterviewSession instead of running the resume/pool/question/response flow. No browser/server was running.
**Impact:** Passing callbacks prove association and lifecycle behavior under test fixtures, not that all three student journeys reach those callbacks with real generated/persisted evidence.
**Recommended next check:** In an isolated environment, perform one assigned multi-round assessment with real Aptitude answer submission, Coding problem provisioning and a Judge0-scored submission (or documented Judge0 unavailable result), and Interview resume/pool/turn response. Verify after each refresh using student assignment detail and faculty assessment detail.

### A2 â€” Interview evidence is associated at session level (Medium data-granularity limitation)

**Evidence:** `InterviewTurn` references `InterviewSession`; that session references `AssessmentSession`, while the assignment link references an `AssessmentRound`. The assignment evaluation gathers interview sessions by `session_id`, not by a round foreign key. The current workflow makes one assigned engine round/session per configured round, which supplies a practical indirect link.
**Impact:** The association is unambiguous under the one-round-per-assigned-session invariant, but the database does not directly associate a turn with an `AssessmentRound`. Any legacy or future multi-interview-round session could make round-level evidence ambiguous.
**Recommended direction:** Preserve the one-interview-round-per-linked-session invariant or add a direct association only if future workflows allow multiple interview rounds within one session. No schema change is recommended for this audit alone.

### A3 â€” Review is summary-level, and the consolidated report is broader than one assignment (Medium product gap)

**Evidence:** The assignment-specific view provides status, scalar score, and counts/evidence. It does not display detailed aptitude answer review, coding submissions/test-case breakdown, or interview turn feedback. Interview feedback is explicitly described as not persisted by the current engine. The additional student report endpoint is selected by student ID, not assessment/assignment ID.
**Impact:** Faculty can see whether an assigned round produced an evaluated result and its summary, but cannot review all detailed evidence scoped to that assignment from this screen.
**Recommended direction:** Decide whether summary evidence meets the faculty review requirement. If detailed review is required, define a faculty-authorized assignment-round detail contract using existing persisted records; do not infer feedback that the engine does not persist.

### A4 â€” Availability and migration state are source-verified, not database-verified (Verification gap)

**Evidence:** Migration and ORM declare naive `DateTime` availability fields; current request path converts aware values to UTC-naive, while backend comparisons use UTC-naive current time. Focused tests confirm the serialized instant and before/within/after start outcomes. No `TEST_DATABASE_URL`/`EDI5_TEST_DATABASE_URL` was configured, and no runtime DB was queried.
**Impact:** Existing deployed columns, migration state, and historical timestamp meaning are unknown. The source convention alone does not establish that the migration is applied or old rows use the same UTC-naive convention.
**Recommended direction:** Check migration head and a non-sensitive test record in the approved test environment before release; do not reinterpret historical values without evidence.

### A5 â€” Assessment creation is immediately published (Product/workflow decision)

**Evidence:** The ORM/migration default status is `published`; the create service does not create a draft or provide a separate publish operation. Cancellation blocks future starts while preserving existing records.
**Impact:** The current flow is create-and-assign/publish in one action. If product requirements expect a draft/review/publish stage, that workflow is absent.
**Recommended decision:** Confirm that immediate publication on faculty assignment is intended. No implementation change was made.

### A6 â€” Natural Interview completion resolves the candidate's latest active session (Conditional linkage risk)

**Evidence:** In `/interview/session/{id}/respond`, the completion branch marks the requested InterviewSession complete, then queries the authenticated user's latest `AssessmentSession` with `status="in_progress"` to find an active Interview `AssessmentRound`. It does not scope that lookup to the requested InterviewSession's `session_id`. The separate early `/complete` route does scope by `interview.session_id`.
**Impact:** With the normal one-active-session invariant, the lookup should resolve to the intended assigned session. If legacy data or another entry path leaves multiple in-progress sessions, finalization could close the wrong session/context and leave the assigned round stuck.
**Recommended direction:** Use the requested interview's session ID in the natural-completion lookup and verify ownership/status there. This is a narrowly justified backend correction if multiple active rows are possible; it was not implemented as part of this read-only audit.

## Test and runtime verification

| Check | Result |
|---|---|
| `python -m pytest -q tests/test_faculty_practice_assessments.py --disable-warnings --maxfail=1` | **PASS** â€” 12 passed, 93 warnings, 8.71 seconds. Assignment test fixtures use in-memory SQLite; no external test database was used. |
| `node --test src/utils/assignedAssessmentAvailability.test.js src/utils/facultyAssessmentActivity.test.js` (from `frontend`) | **PASS** â€” 14 passed. These tests cover availability formatting and Activity/report UI utility behavior, not a rendered browser assignment journey. |
| Authenticated browser smoke test | **NOT RUN** â€” ports 5173, 8000, and 8001 were not listening; no test credentials/browser session were available. |
| Live API/database or migration check | **NOT RUN** â€” no isolated PostgreSQL test URL was configured. Migration was not applied. |
| Full frontend suite/build | **NOT RUN** â€” this read-only integration audit used focused tests; it does not claim a complete frontend build or suite result. |
| Real Judge0 and interview AI service execution | **NOT RUN** â€” no live service configuration or authenticated runtime was available. |

## Conclusion

The current worktree shows a coherent server-authorized persistence and sequential lifecycle design, and the focused isolated tests pass. Source review supports that Aptitude, Coding, and Interview completion callbacks close only linked faculty-assignment attempts and that result serialization distinguishes evaluated scores from unavailable/pending scores. However, the full E2E claim remains **PARTIAL / NOT VERIFIED** until an authenticated browser flow exercises actual question delivery, coding submissions/timer behavior, interview interactions, refresh persistence, and faculty review against the approved isolated environment. No application code or tests were changed during this audit.

## Source map

- Faculty assignment API: `app/api/v1/faculty_practice_assessments.py`
- Assignment model and constraints: `app/models/faculty_practice_assessment.py`
- Persistence, sequencing, result evaluation, and finalization: `app/services/faculty_practice_assignment_service.py`
- Department scope helper: `app/services/faculty_access_service.py`
- Migration: `alembic/versions/add_faculty_practice_assignments.py`
- Student assignment/start endpoints: `app/modules/practice/routers/practice_router.py`
- Existing session/round locking and completion: `app/services/session_service.py`
- Aptitude completion: `app/modules/aptitude/routers/aptitude_router.py`
- Coding provisioning, submission, timer and finish: `app/modules/coding/services/coding_service.py`, `app/modules/coding/routers/coding_router.py`
- Interview resume/pool and completion: `app/modules/interview/routers/interview_router.py`
- Faculty workspace: `frontend/src/components/FacultyPracticeAssessmentWorkspace.jsx`, embedded by `frontend/src/pages/FacultyDashboard.jsx`
- Student assigned assessment UI: `frontend/src/pages/PracticeOverview.jsx`
- Focused integration tests: `tests/test_faculty_practice_assessments.py`
