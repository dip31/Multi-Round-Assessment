# EDI5 DATABASE & API DEEP TRACE AUDIT

## 1. Table Inventory

The EDI5 system relies on a relational database (PostgreSQL) managed by SQLAlchemy and Alembic. The core tables include:
- `users`: Core identity table (student, faculty, tpo, admin).
- `assessment_sessions`: Tracks the overall assessment lifecycle for a user.
- `assessment_rounds`: Links to sessions; tracks individual round types (aptitude, coding, interview).
- `aptitude_topics` / `aptitude_questions` / `aptitude_attempts`: Powers the MCQ aptitude round.
- `coding_problems` / `coding_test_cases` / `coding_submissions`: Powers the coding round and Judge0 integration.
- `interview_sessions` / `interview_turns` / `approved_question_pools`: Manages the AI-driven behavioral/technical interview phase.
- `proctoring_violations`: Tracks tab-switches and facial recognition warnings.
- `rl_sessions`: Stores reinforcement learning state (Q-values) for adaptive difficulty.

## 2. Relationship Map

- **User → Sessions**: 1-to-many. (`users.id` -> `assessment_sessions.user_id`)
- **Session → Rounds**: 1-to-many. (`assessment_sessions.id` -> `assessment_rounds.session_id`)
- **Round → Aptitude/Coding/Interview**: Each round type creates specific records linked via `round_id`.
  - `aptitude_attempts.round_id` -> `assessment_rounds.id`
  - `coding_submissions.round_id` -> `assessment_rounds.id`
  - `interview_sessions.session_id` -> `assessment_sessions.id` (Note: Interview models link directly to the parent `session_id`, bypassing the generic `round_id` for some legacy reasons, but maintains a conceptual link).

## 3. Auth & Registration Flow

**Registration**:
- Endpoint: `POST /api/v1/auth/register` (in `auth_router.py`).
- Flow: Validates email uniqueness -> Hashes password -> Inserts `User` record via `auth_service.create_user()`.
- Role assignment: Controlled by the payload (default: "student"). No sessions or rounds are created at registration.

**Login**:
- Endpoint: `POST /api/v1/auth/login`.
- Flow: Validates password hash -> Returns JWT containing `{"sub": user_id}`.

## 4. Assessment Models

- **AssessmentSession**: Represents a continuous block of time a student spends on the platform. Fields: `id`, `user_id`, `status` (`in_progress`, `completed`, `expired`), `started_at`, `completed_at`, `total_score`.
- **AssessmentRound**: Sub-division of a session. Fields: `id`, `session_id`, `round_type` (`aptitude`, `coding`, `interview`), `status`, `score`.

## 5. Session & Round State Machine

**Session States**:
1. `in_progress`: Active session.
2. `completed`: User finished all rounds or manually submitted.
3. `expired`: Background task or `/session/status` cleanup marked it stale (older than 30 mins).

**Round States**:
1. `active`: User is currently answering questions.
2. `completed`: Round finished, score calculated.
3. `expired`: Cleaned up alongside stale sessions.

## 6. Result Generation

Results are calculated lazily or at the end of each round:
- **Aptitude**: Derived from `aptitude_attempts` where `is_correct = True`.
- **Coding**: Evaluated via Judge0 test case passes in `coding_submissions`.
- **Interview**: Scored via NLP/LLM on `candidate_response` in `interview_turns`.

## 7. Dashboard API & Payloads

The primary active dashboard is driven by `GET /api/v1/dashboard/{role}` (in `dashboard_router.py`).
For a student, `_student_dashboard(db, user)` executes:
1. Fetches all `AssessmentSession` records for `user.id`.
2. Flattens `session.rounds` into a single list.
3. Calculates `completed` rounds count and average `score`.
4. Returns a heavily structured JSON payload matching the UI components in `StudentDashboard.jsx`.

## 8. Missing Links / Disconnects

- **Legacy Dashboard**: `Dashboard.jsx` uses a different API (`/session/status`) and computes completion entirely on the frontend via `getRoundStatusMap`. This file is completely orphaned in `App.jsx` (the route points to `StudentDashboard` instead).
- **Interview Relational Link**: `interview_sessions` ties back to `assessment_sessions.id`, whereas `aptitude_attempts` and `coding_submissions` tie back to `assessment_rounds.id`. This mismatch indicates the interview module was developed separately or refactored asynchronously.

## 9. Unknowns

- **Seed Scripts**: The exact contents of the database seed scripts (e.g., `seed_coding_questions.py`) are not fully verified for user ID collision, though evidence strongly points to them as the source of mock data.
- **Judge0 Webhooks**: The exact async callback mechanism for `coding_submissions` is not traced in this scope.

## 10. Critical Bug Investigation: "New Student Sees Completed Rounds"

**The Bug**: A newly registered student logs into the platform and immediately sees assessment rounds marked as "completed", despite having never taken a test.

**Root Cause Analysis**:
I have investigated all API routes (`/api/v1/dashboard/student`, `/api/v1/auth/register`), frontend hooks (`useDashboardData`), and legacy components. 

1. **Frontend Rendering**: `StudentDashboard.jsx` maps `data.rounds` strictly from the API response. If `data.rounds` is empty, it correctly displays "No assessment rounds yet."
2. **Backend Query**: `_student_dashboard` filters sessions explicitly via `.filter(AssessmentSession.user_id == user.id)`. 
3. **Registration Isolation**: `auth_router.py` does not create any sessions upon user creation.

**Conclusion**: The code logic itself is **sound**. The bug is an **Infrastructure/Seed Data Artifact**.
When a new user registers, PostgreSQL assigns them the next available `user_id` from the sequence. If the development database was seeded using explicit `INSERT` statements with hardcoded `user_id`s (e.g., `user_id=1, 2, 3`) and associated `AssessmentSession` records were also seeded, the database sequence `users_id_seq` was likely *not* advanced. 

When a new student registers via the UI, the sequence naturally generates `id=1`. The new student inherits the `user_id` that is already linked to the seeded, fully-completed `AssessmentSession` records. The dashboard accurately queries `user_id=1`, retrieving the mock data.

**Evidence**: 
- No frontend hardcoding exists for completion.
- No auto-session creation exists in the auth flow.
- The `user_id` filter is strictly enforced in the dashboard router.

---
**END OF AUDIT**
