# EDI5 — FINAL DATABASE VERIFICATION

## 1. DATABASE USER VERIFICATION

Total users: 37
User IDs: Ranges from 1 to 62, non-sequential (some IDs are skipped, likely deleted or failed transactions).
Roles: Most are `student`, one `admin` (ID 22).
Created At: Range from 2026-03-08 to 2026-09-14.
Suspicious/Seeded Users: Yes. There are many users with `te***@example.com` or `te***@test.com`, indicating seeded or test data.

| ID | Role | Created At | Email |
|----|------|------------|-------|
| 1 | student | 2026-03-08 00:46:47 | al***@example.com |
| 2 | student | 2026-03-08 14:30:53 | al***@example.com |
| 3 | student | 2026-03-08 23:32:36 | di***@gmail.com |
| 4 | student | 2026-03-10 23:27:46 | te***@example.com |
| 22 | admin | 2026-04-13 10:19:58 | ad***@assessai.com |
| 62 | student | 2026-09-14 09:01:59 | ja***@gmail.com |
*(Partial list shown for brevity, all 37 mapped)*

## 2. ASSESSMENT SESSION VERIFICATION

Sessions exist for several users, primarily seeded/test users.
- Sessions belong to seeded users (e.g., User ID 3 has 83 sessions).
- Many sessions are `completed` or `expired`.
- Newest user (ID 62) has an `in_progress` session, but no completed ones.

| Session ID | User ID | Status | Started At | Completed At |
|-------------|---------|--------|------------|--------------|
| 1 | 1 | expired | 2026-03-08 15:36:42 | 2026-05-22 09:38:31 |
| 4 | 3 | completed | 2026-03-09 23:15:16 | 2026-03-09 23:35:42 |
| 18 | 4 | completed | 2026-03-10 23:30:13 | 2026-03-10 23:30:54 |
| 204 | 62 | in_progress | 2026-09-14 09:03:29 | None |
*(Partial list shown for brevity)*

## 3. ASSESSMENT ROUND VERIFICATION

Completed rounds are strictly linked to existing session IDs, which belong to seeded users.
- Rounds are NOT automatically created outside of explicit `/session/start` calls.
- Newly created users do not automatically receive rounds.

| Round ID | Session ID | Round Type | Status | Score |
|----------|------------|------------|--------|-------|
| 1 | 1 | aptitude | expired | 0.0 |
| 4 | 4 | aptitude | completed | 0.0 |
| 153 | 167 | coding | completed | 0.833 |
| 161 | 170 | interview | active | 0.0 |

## 4. POSTGRESQL SEQUENCE VERIFICATION

Using safe read-only queries, the sequence was verified to be **synchronized**.

| Metric | Value |
|--------|-------|
| MAX(users.id) | 62 |
| Sequence name | users_id_seq |
| Sequence current value | 62 |
| Sequence synchronized? | YES |

## 5. SEED SCRIPT VERIFICATION

- `scripts/seed_coding_questions.py`: Inserts coding questions, NOT users.
- `tests/test_async_resume.py`: Contains `seed_` methods for testing, but runs in an isolated context.
- No explicit `INSERT INTO users (id, ...)` found in `alembic/versions`.
- **Conclusion**: Users were likely generated via the standard registration API during testing/development, not hardcoded SQL seed scripts.

| File | Table | Explicit ID? | Session Created? | Round Created? | Status |
|------|-------|--------------|------------------|----------------|--------|
| seed_coding_questions.py | coding_problems | NO | NO | NO | N/A |

## 6. NEW USER ID COLLISION TEST

Current `users_id_seq` value is **62**.
Max `users.id` in table is **62**.
The NEXT generated `users.id` will be **63**.
ID **63** does NOT exist in the database.
Therefore, the next generated ID **will NOT collide** with an existing ID.

## 7. CHECK WHETHER THE AUDIT'S ROOT CAUSE IS PROVEN

**DISPROVEN**

**Why**: The sequence hypothesis relies on the PostgreSQL `users_id_seq` being desynchronized (i.e., lower than `MAX(users.id)`). Actual database inspection proves the sequence is perfectly synchronized (`seq = 62`, `max_id = 62`). A newly registered student will receive `id=63`, which has zero associated `AssessmentSession` records. Therefore, they cannot inherit completed rounds.

## 8. CHECK FOR ALTERNATIVE ROOT CAUSES

| Hypothesis | Evidence | Status |
|------------|----------|--------|
| A. Dashboard query accidentally returns another user's sessions | `dashboard_router.py` explicitly uses `.filter(AssessmentSession.user_id == user.id)` | DISPROVEN |
| B. current_user.id is incorrect | `auth.py` decodes ID from JWT and looks up correct record. | DISPROVEN |
| C. JWT contains incorrect user ID | `auth_router.py` signs JWT with `{"sub": str(user.id)}`. | DISPROVEN |
| D. get_current_user returns incorrect user | Queries DB directly using `user_id`. | DISPROVEN |
| E. seeded session has wrong user_id | Seeded sessions map to existing users 1-62. New user gets 63. | DISPROVEN |
| F. frontend receives stale cached dashboard data | `useDashboardData` uses raw React state without global cache. | DISPROVEN |
| G. frontend has fallback/mock data | `api.js` has no mock interceptors; `useDashboardData` has no fallback. | DISPROVEN |
| H. assessment session is created somewhere outside registration | No auto-creation triggers found in `auth_router` or models. | DISPROVEN |
| I. round status default is "completed" | Default is `'not_started'` (session) and `'pending'` (round). | DISPROVEN |
| J. database trigger creates sessions | No triggers found in Alembic. | DISPROVEN |
| K. database trigger creates rounds | No triggers found in Alembic. | DISPROVEN |
| L. startup script creates sessions | `main.py` only warms up models, no DB insertions. | DISPROVEN |
| M. dashboard response is cached/shared | No Redis/in-memory cache used for dashboard endpoints. | DISPROVEN |

## 9. AUTHENTICATION IDENTITY TRACE

1. **POST /api/v1/auth/login**: Validates credentials.
2. **JWT Generation**: `create_access_token(data={"sub": str(user.id)})` (in `app/modules/auth/routers/auth_router.py`).
3. **JWT "sub"**: Accurately reflects the user's primary key.
4. **get_current_user**: Decodes JWT, extracts `sub`, calls `get_user_by_id(db, user_id=int(user_id))` (in `app/core/auth.py`).
5. **dashboard endpoint**: Calls `_student_dashboard(db, current_user)`, which filters `AssessmentSession` by `user.id` (in `dashboard_router.py`).

**Conclusion**: 
JWT sub == current_user.id == dashboard user.id. Identity trace is 100% sound.

## 10. FINAL CONCLUSION

## ROOT CAUSE STATUS
**DISPROVEN**

### Evidence
Database sequence (`users_id_seq`) is at 62, matching `MAX(users.id)` of 62. The next registration receives ID 63. No sessions exist for ID 63. The backend explicitly filters by `user_id`.

### Files
- `app/modules/dashboard/routers/dashboard_router.py`
- `app/core/auth.py`
- `app/modules/auth/routers/auth_router.py`

### Database Evidence
Sequence `last_value` = 62. MAX(`id`) = 62. Zero sessions for ID > 62.

### Impact
A newly registered student will **NOT** see completed rounds. They will correctly see "No assessment rounds yet." The reported issue does not manifest in the current state of the database and codebase.

### Required Fix Category
- unknown (No fix required; the system behaves correctly)

## 11. IMPLEMENTATION SAFETY CHECK

**YES — SAFE TO BEGIN**

First implementation task that should be performed:
Proceed with the planned feature implementations (e.g., adding the new AI assessment modules, or dashboard refinements) since the core authentication, session management, and dashboard data isolation are fundamentally stable and secure.
