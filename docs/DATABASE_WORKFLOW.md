# Database Workflow

This document describes how the EDI5 databases are configured, migrated,
backed up, restored, and tested. It is the reference for anyone running the
backend or the test suite.

## Databases at a glance

| Purpose | Location | Notes |
| --- | --- | --- |
| Development | PostgreSQL `ai_placement_platform` (local) | Primary working database. **Treat as precious** — it holds real/dev data. Never point tests at it. |
| Test | PostgreSQL `ai_placement_platform_test` | Created/dropped automatically by the test suite. Never commit or share. |
| Legacy SQLite | `database.db` (repo root) | Empty/legacy artifact referenced only by old root scripts. Not used by the app. Do not commit. |

Only the **development** database is authoritative. The test database is
disposable and rebuilt from the ORM models on every test session.

## Configuration

Database connection details live in `.env` (never committed):

```
DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@localhost:5432/ai_placement_platform
```

`app/config/settings.py` loads `.env`; `app/database/db.py` builds the engine
and session factory from `settings.DATABASE_URL`.

For tests, set a **separate** database:

```
TEST_DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@localhost:5432/ai_placement_platform_test
```

`TEST_DATABASE_URL` is only read by the test harness. Never set it to the
development database — the harness will refuse to run.

### Windows: PostgreSQL client tools

`pg_dump`, `pg_restore`, `psql`, `createdb`, and `dropdb` are typically **not**
on `PATH`. Use them via the install directory, for example:

```powershell
$env:PGPASSWORD = "<password from DATABASE_URL>"
& "C:\Program Files\PostgreSQL\16\bin\pg_dump" --version
```

## Running the backend

```powershell
uvicorn app.main:app --reload
```

The application always uses `settings.DATABASE_URL`. No test-only behaviour is
active unless `EDI5_TESTING=1` is set (which only the test harness does).

## Migrations

Alembic owns the development schema. Use it for all schema changes.

```powershell
alembic current          # show applied revision
alembic heads            # show head revision(s)
alembic upgrade head     # apply migrations
alembic revision -m "..."  # create a new migration
```

Notes:

- `alembic/env.py` (online mode) reads `settings.DATABASE_URL` directly.
- Schema changes must go through Alembic — do **not** rely on
  `Base.metadata.create_all` for the development database.

## Backup and restore

Backups live **outside** the repository, e.g.
`D:\Git Projects\Multi-Round-Assessment-backups\`.

Create a backup (custom format, restorable with `pg_restore`):

```powershell
$env:PGPASSWORD = "<password>"
& "C:\Program Files\PostgreSQL\16\bin\pg_dump" `
  -h localhost -p 5432 -U postgres -Fc `
  -d ai_placement_platform `
  -f "D:\Git Projects\Multi-Round-Assessment-backups\ai_placement_platform_dev_<timestamp>.dump"
```

Verify a backup without touching any database:

```powershell
& "C:\Program Files\PostgreSQL\16\bin\pg_restore" --list `<backup>.dump`
```

Restore into a **scratch** database (never over the development database):

```powershell
& "C:\Program Files\PostgreSQL\16\bin\createdb" -h localhost -U postgres restore_check
& "C:\Program Files\PostgreSQL\16\bin\pg_restore" -h localhost -p 5432 -U postgres `
  -d restore_check `<backup>.dump`
```

Every backup should be accompanied by a small manifest noting the timestamp,
database name, size, Alembic revision, table count, and row count.

## Testing

The test harness isolates all database access from the development database:

1. `tests/conftest.py` sets `EDI5_TESTING=1` **before** any application module
   is imported.
2. `app/database/db.py` sees `EDI5_TESTING=1` and binds `engine`/`SessionLocal`
   to `TEST_DATABASE_URL` instead of `settings.DATABASE_URL`.
3. A session-scoped fixture drops and recreates the test database, builds the
   schema with `Base.metadata.create_all`, and seeds the deterministic baseline
   (assessment policies 1 and 2, and assessment context 1).

Because binding happens in `app/database/db.py` itself, tests that import
`SessionLocal` directly (not just `get_db`) are isolated too.

### Running tests with a database

```powershell
$env:TEST_DATABASE_URL = "postgresql+psycopg2://postgres:<password>@localhost:5432/ai_placement_platform_test"
python -m pytest tests -q
```

### Running tests without a database

Tests that build their own in-memory SQLite engine and override `get_db` do not
need `TEST_DATABASE_URL`. Any test that reaches for the real database without
`TEST_DATABASE_URL` configured fails fast with an actionable error instead of
silently writing to the development database.

### Known test data dependencies (gap)

The isolated test database is built from the ORM models with only the minimal
baseline seeded (assessment policies 1 and 2, assessment context 1). It does
**not** contain a seeded aptitude question bank. As a result, tests that
previously read aptitude questions from the development database will fail
against a clean test database:

- `tests/test_practice_and_interview_modes.py` — MCQ / technical / combined
  round tests return `404` from `/api/v1/aptitude/next-question` because no
  `aptitude_questions` / `aptitude_topics` rows exist.

These are **known data-dependency gaps**, not isolation defects. Seeding a
minimal aptitude bank into the isolated test database is deferred to a
follow-up task. Two further modules
(`tests/test_adaptive_difficulty.py`, `tests/test_proctoring.py`) are manual
async scripts that fail under `pytest` because pytest-asyncio is not configured
for them; this is unrelated to database isolation.

### Isolation guarantees

- The harness refuses to run if `TEST_DATABASE_URL` names the development
  database.
- The development database is never created, dropped, or written to by tests.
- The guard behaviour is covered by `tests/test_db_isolation_guard.py`.

### Safety rules for maintainers

- Never set `TEST_DATABASE_URL` to the development database.
- Never point `DATABASE_URL` at a test database.
- Never commit `database.db`, `*.sqlite`, `*.sqlite3`, `*.dump`, or `.env`.
- Changes to database isolation must keep both the fail-fast guard and the
  dedicated-database requirement intact.
