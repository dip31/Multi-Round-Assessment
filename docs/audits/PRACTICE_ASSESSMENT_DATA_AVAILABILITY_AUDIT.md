# Practice Assessment Data Availability Audit

**Audit date:** 2026-10-23  
**Scope:** Read-only inspection of the Faculty Assessments implementation, practice workflow, schema, and configured development database. No application or database changes were made.

## A. Executive summary

Genuine Practice Assessment data exists in the configured database. The database contains **36 distinct canonical students with at least one `practice` context-linked session** (59 sessions in total). This is not the same as having 36 students with answers or evaluated submissions: persisted response/evaluation details were found for **one** practice student, comprising four aptitude question attempts and five interview turns. There are no practice coding submissions in the inspected database.

The Faculty Assessments page can receive practice-mode rows through its current department-scoped activity API. The same API also receives Mock Drive, portfolio, and legacy sessions because its session query does not restrict `AssessmentContext.mode`. The page labels rows by mode and offers an assessment-type filter; by default, it displays all returned modes together. The API does not expose question-level practice review to faculty. Existing detailed practice result/review endpoints enforce session ownership by the authenticated user, so they do not provide faculty access to another student's detailed practice results.

There is no separate practice-assignment model/table in the inspected application. Practice is self-started: the workflow creates a student-owned `AssessmentContext` with mode `practice`, then an `AssessmentSession` and rounds. Thus a formal assigned-candidate count is not represented by this schema; the 36 participants below are session-linked students, not assignment recipients.

## B. Environment and verification scope

- Application configuration resolved to PostgreSQL on `localhost`, database `ai_placement_platform`. Credentials are intentionally omitted.
- The database was reachable. Aggregates were queried through the configured SQLAlchemy engine after setting the transaction to read-only (`SET TRANSACTION READ ONLY`). No rows or personal details were dumped.
- Database counts below reflect the configured local development database at audit time; they are not claims about another deployment.
- Code/schema inspection covered the FastAPI route, ORM models, service functions, frontend component, and existing tests. No service was started, no migration or test was run, and no database writes were made.

## C. Schema and data flow

### Faculty page

- Route: `/faculty/dashboard`, in `frontend/src/App.jsx`; the Assessment Monitoring section is rendered by `frontend/src/pages/FacultyDashboard.jsx`.
- Table, filters, pagination, CSV export, and modal report/details are in `frontend/src/components/FacultyAssessmentsSection.jsx`.
- Main request: `GET /profile/cohort/assessment-activity`, with filters/pagination built in `frontend/src/utils/facultyAssessmentActivity.js`.
- Backend handler: `get_cohort_assessment_activity` in `app/api/v1/profile.py`.
- The handler queries `AssessmentSession` joined to student `User` and `StudentProfile`, scoped by a case-insensitive match to the authenticated faculty member's `FacultyProfile.department` via `get_faculty_department` in `app/services/faculty_access_service.py`. It eager-loads context and rounds, then aggregates aptitude attempts, coding submissions, and interview turns.
- Faculty student profile access uses the existing department authorization helper. The practice result/review endpoints in `app/modules/practice/routers/practice_router.py` call `get_owned_session` and require the authenticated user to own the session.

### Practice workflow and persisted relationships

`POST /practice/start` (`start_practice` in `app/modules/practice/routers/practice_router.py`) invokes `get_or_create_practice_context` in `app/services/assessment_context_service.py`. The service creates an `AssessmentContext` with `mode="practice"`, `purpose="practice"`, and `student_id`. The router then creates the associated `AssessmentSession`; rounds attach to that session.

The authoritative mode relationship is:

`assessment_sessions.context_id -> assessment_contexts.id -> assessment_contexts.mode`

For practice records, `AssessmentContext.student_id` records the context owner and `AssessmentSession.user_id` is the session participant. The inspected practice sessions had no owner/session mismatches. Mock Drive sessions share the same session/round and response tables but use `assessment_contexts.mode="mock_drive"` and link to `mock_drive_id`; the practice count queries below filtered explicitly on `mode="practice"`.

Relevant models/tables:

| Data | Model/table | Relationship or persisted fields |
| --- | --- | --- |
| Canonical identity | `User` / `users`; `StudentProfile` / `student_profiles` | Profile `user_id` references student `users.id`; stable identity is `User.id`. |
| Faculty scope | `FacultyProfile` / `faculty_profiles` | Department compared to the student's `StudentProfile.department`. |
| Practice/drive classification | `AssessmentContext` / `assessment_contexts` | `mode`, `student_id`, `mock_drive_id`, `purpose`, timestamps and status. |
| Shared assessment attempt | `AssessmentSession` / `assessment_sessions` | `user_id`, nullable `context_id`, status and session timestamps. |
| Round | `AssessmentRound` / `assessment_rounds` | `session_id`, `round_type`, optional `practice_type`, status, numeric `score`, timestamps. |
| Aptitude answers | `AptitudeAttempt` / `aptitude_attempts` | `round_id`, question, attempt number, selected option, correctness, timestamp. |
| Coding submissions | `CodingSubmission` / `coding_submissions` | `round_id`, code, status, score, submitted timestamp. |
| Interview answers/evaluations | `InterviewSession` / `interview_sessions`; `InterviewTurn` / `interview_turns` | Interview session links to assessment session; turns persist response, content/final scores, follow-up flag and timestamp. |

No dedicated practice assignment/recipient ORM model or table was found. There is also no separate assessment evaluation or rubric-result table in the inspected path: aptitude correctness is persisted on attempts, coding evaluation status/score on submissions, and interview scores on turns. Interview turn fields include response and score data but not a separate rubric/comments record.

## D. Verified record counts

All practice-specific figures use `AssessmentContext.mode = 'practice'` and follow persisted foreign-key relationships. Distinct student counts use `User.id`, not display names. The assignment concept is reported separately because no assignment entity exists.

| Measure | Verified count | Scope / interpretation |
| --- | ---: | --- |
| Canonical student users | **474** | `users.role='student'` joined to `student_profiles`. |
| Formal practice assignments | **Not represented** | No assignment model/table or practice assignment query found; this is not a database zero for an existing assignment table. |
| Practice contexts | **72** | Context mode is `practice`; 71 have an owner that resolves to a student user, one has an unresolved/missing student owner. |
| Contexts without a session | **13** | Practice contexts not linked to an assessment session. |
| Practice assessment sessions | **59** | Session linked to a `practice` context. |
| Distinct practice session participants | **36** | Distinct `AssessmentSession.user_id`; all 36 resolve to student profiles. |
| Session owner/context owner mismatches | **0** | Among the 59 practice sessions, no populated context owner disagreed with the session user. |
| Practice rounds | **99** | 49 aptitude, 34 coding, 16 interview rounds. |
| Session-linked participants with any answer/evaluation detail | **1** | Distinct student with at least one aptitude attempt, coding submission, or interview response turn. |
| Aptitude attempts / distinct students | **4 / 1** | Four `AptitudeAttempt` rows; all have persisted `is_correct`; one is correct. |
| Aptitude rounds with attempt evidence | **2** | Distinct practice rounds with at least one non-null correctness result. |
| Coding submissions / distinct students | **0 / 0** | No practice-linked `CodingSubmission` rows; therefore no pending or failed coding evaluations and no coding submission scores. |
| Interview turns / response-bearing / scored | **5 / 5 / 5** | All five practice-linked turns have candidate responses and `final_score`; one distinct student. Two are primary turns and three are follow-ups. |
| Interview sessions / interview rounds with scored turns | **1 / 2** | One distinct `InterviewSession`; its five turns are associated at the assessment-session level with two completed interview rounds. |
| Practice round/session statuses | **Round:** 71 completed, 23 active, 5 expired. **Session:** 30 completed, 25 in progress, 4 expired. | Persisted statuses; status is not itself proof of submitted/evaluated answers. |
| Practice session date range | **2026-09-27 to 2026-10-10** | Minimum and maximum `AssessmentSession.started_at` for practice-linked sessions. |

The 36 session participants are genuine canonical student records, but only one has answer/evaluation detail in these practice response tables. The practice submission/attempt footprint is therefore sparse relative to session/round counts. The numeric `AssessmentRound.score` column has a database default of `0`; its non-null presence alone cannot establish a meaningful evaluated score. The response-level evidence found is four aptitude correctness values and five interview turn scores.

## E. Genuine student data availability

Existing canonical student records can be displayed without synthetic candidates: 36 distinct students are linked to practice-mode sessions and all resolve to student profiles. A practice student list can be derived from those persisted sessions under the existing department authorization rule.

There is no assigned practice roster to derive from an assignment table. The implementation creates practice contexts when students start an assessment. Also, 35 of the 36 session-linked students had no persisted aptitude/coding/interview response detail in the inspected response tables. The existence of a session or round should not be presented as an evaluated submission.

## F. Mock Drive contamination

The current Faculty Assessments API is a mixed-mode source. Its base query at `app/api/v1/profile.py` (`get_cohort_assessment_activity`) scopes sessions to student role and faculty department but does not filter `AssessmentContext.mode`. It maps `context.mode` into `assessment_type` and labels rows as practice, mock drive, portfolio, or unknown. The page calls this endpoint without an assessment-type filter initially, so rows from multiple modes can appear together; a mode/type filter is available.

This audit did not count Mock Drive sessions as practice. Database contexts included both `practice` and `mock_drive`; practice metrics were isolated by the explicit `mode='practice'` predicate. Therefore, the page can access practice rows through this API, but its default table is not practice-only.

## G. Student identity findings

The named labels in the brief (`History Student`, `Combined Student`, `Score Student`, `Interview Student`, `Tech Student`, `MCQ Student`, and `Aksha`) exist as canonical `users.name` values and have student profiles in the configured database. The six generic `* Student` labels also appear as names created by test helpers in `tests/test_phase3_dashboard.py` and `tests/test_practice_and_interview_modes.py`. `Aksha` is not shown as a hardcoded frontend fallback in the inspected Faculty Assessments component.

The exact source/provenance of the existing database rows cannot be proven from their display name alone. The six generic names are used by tests, but this does not prove that the particular persisted user rows were created by those tests. Among the named users, only `Aksha` appeared linked to context-mode sessions in the practice/mock mode aggregate; generic names also occur with legacy sessions having no assessment context. The activity API labels a missing context as `unknown`/`Assessment`, so those legacy rows are not verified practice data.

## H. Submission and report integrity

- The faculty API uses different persisted entities per round. Aptitude `attempt_count` is the number of `AptitudeAttempt` rows with non-null `is_correct`; coding `attempt_count` is the number of `CodingSubmission` rows; interview attempt count/evaluated count is the number of non-follow-up `InterviewTurn` rows, with `InterviewTurn.final_score` determining evaluated turns. These are not interchangeable definitions of an attempt.
- The detailed practice interview review includes follow-up turns. In this database, all five persisted interview turns have responses and scores, while the faculty activity aggregation excludes follow-ups and therefore counts two primary turns. This explains why a detail view can show more interview turns than the activity row's count without implying missing submissions.
- The faculty API's activity `score` is `AssessmentRound.score` whenever its evidence count is nonzero. It does not use its separately aggregated interview average, nor does it call the practice result service. The two aptitude rounds with answer evidence and two interview rounds associated with scored turns had stored round scores of `0.0`, while aptitude correctness and interview per-turn scores existed. Because `AssessmentRound.score` defaults to zero, this is a verified mapping/data integrity concern: the faculty row can display a zero score even when separately persisted item-level evaluation exists. It is not safe to interpret every zero as a confirmed zero-performance score.
- Interview response/evaluation records are attached to `InterviewSession`, which links to `AssessmentSession`, not to a particular `AssessmentRound`. The faculty API aggregates turns by assessment session and phase, then applies that same aggregate to each interview-type round in that session. In the inspected data, the same five turns are therefore associated with two interview round rows; the round-level attempt/evaluation count is not a round-specific submission count.
- The practice result service derives aptitude counts from all `AptitudeAttempt` rows and includes question-level response details; the faculty activity aggregation filters aptitude rows with null correctness out. For this database all four persisted aptitude attempts had correctness values, so no observed count discrepancy resulted from that filter.
- Coding submission details are built from `CodingSubmission` rows and only coding scores are returned in that detail list. No practice coding rows were present. The faculty report/modal uses the activity row payload; it does not fetch the practice round result or question-by-question review endpoint.
- Last activity in the faculty endpoint is the maximum among selected attempt/submission/interview timestamps and round/session lifecycle timestamps. The timestamps refer to different source events depending on round type, so a displayed timestamp does not uniformly mean “last answer submitted.”

## I. Future report readiness

| Planned capability | Availability | Evidence and limitation |
| --- | --- | --- |
| Genuine practice student list | **Partially available** | 36 session-linked students with canonical profiles; no separate assignment roster; faculty results remain department-scoped. |
| Practice history per student | **Partially available** | 59 context-linked sessions and 99 rounds exist, but most do not have response detail. |
| Round-wise results | **Partially available** | Round types/statuses exist; only two aptitude rounds have answer evidence and one interview session has scored turns; coding has none. |
| Attempt and submission history | **Partially available** | Four aptitude attempts and five interview turns for one student; no coding submissions. |
| Evaluation status | **Partially available** | Aptitude correctness and interview final scores are persisted; coding statuses absent. The faculty API derives status from round state and response aggregates. |
| Scores and score scales | **Partially available** | Four aptitude correctness values and five interview turn scores exist, but activity uses `AssessmentRound.score`, which was `0.0` on evidence-linked practice rounds. Round score scales are not uniform across round families. |
| Question-level attempted/correct counts | **Partially available** | Four aptitude attempt rows, one correct; practice result service can form these from persisted attempts. |
| Feedback and rubric results | **Partially available** | Interview turn scores/responses exist, but there is no separate rubric/comments record in the inspected practice storage; aptitude question model has no explanation field. |
| Comparable-attempt performance comparisons | **Unavailable** | Evaluation evidence is concentrated in one student and scale/round score semantics differ; the current evidence is insufficient for reliable cohort comparisons. |
| Consolidated student practice progress report | **Partially available** | Session and round history exists, but sparse result evidence, absent assignment records, and score mapping concerns constrain a reliable report. |
| Submission-specific detail view | **Partially available** | Practice result/review services support persisted detail, but their router enforces student session ownership and is not a faculty-access path. The faculty modal currently shows only aggregate row data. |

## J. Recommended next steps

1. Decide whether the product needs assigned practice assessments. If yes, define an explicit assignment/recipient relationship; current practice is student-started and cannot provide assignment status.
2. Keep the page's source mode explicit in the user experience and default/filter behavior; if the goal is Practice Assessment monitoring, constrain or separately request practice-mode activity rather than treating Mock Drive rows as practice.
3. Add a faculty-authorized, department-scoped practice detail read path before exposing question answers, coding, or interview feedback. The existing detailed practice endpoints are ownership-only.
4. Define consistent attempt/submission/evaluation counts by round type, including whether follow-up interview turns count, and align activity rows with the detailed practice report semantics.
5. Reconcile `AssessmentRound.score` with persisted aptitude/interview evaluation evidence and expose score scale/source; do not treat schema-default zero as an evaluated result.
6. Use development-only fixtures in an isolated test database if UI evaluation needs representative complete histories. Do not use Mock Drive candidates as substitutes for practice candidates.

## K. Limitations

- Findings describe only the configured local database; no remote/staging/production connection was inspected.
- The database was available, but no database-level provenance exists in the inspected rows to determine whether a specific generic-named account was created by tests, manual setup, or another seed path. Test files do create several of the same labels.
- The faculty API's actual returned student set depends on the authenticated faculty member's department. The code authorization rule was inspected, but no authenticated faculty request was made as part of this database-only audit.
- No practice assignment entity exists in the inspected model/schema. Accordingly, an assigned-student count and assignment-level completion/evaluation status cannot be verified.
- Score fields are stored on both round and response-level records with different semantics. The report records both the observed values and the mapping limitation instead of treating a default `0.0` as proof of a scored result.
