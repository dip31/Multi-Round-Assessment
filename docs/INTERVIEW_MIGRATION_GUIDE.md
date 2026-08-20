# IntelliHire — Migration Guide: PostgreSQL ↔ SQLite (Dev)

## Why Migration is Needed
- Local dev and CI use SQLite (aiosqlite) for lightweight testing; production uses PostgreSQL (asyncpg).
- Migration notes clarify incompatibilities and the changes required for SQLAlchemy async models and data fixtures.

## PostgreSQL → SQLite Incompatibilities (specific to this project)
- JSONB → JSON TEXT workaround:
  - PostgreSQL `JSONB` fields (e.g., `interview_answers.scores`) mapped to SQLAlchemy `JSON` with `server_default` in Postgres.
  - SQLite stores JSON as `TEXT`. Ensure app serializes/deserializes on read/write.
- async driver change (asyncpg → aiosqlite):
  - Update connection URL: `postgresql+asyncpg://...` → `sqlite+aiosqlite:///./dev.db`.
  - Replace any `asyncpg`-specific SQL with generic SQLAlchemy expressions.
- ARRAY types → comma-separated TEXT:
  - If any arrays used (not in core schema), convert to CSV stored as TEXT and parse in app layer.
- timestamp with timezone handling:
  - PostgreSQL TIMESTAMPTZ → SQLite store as ISO8601 TEXT in UTC. Enforce timezone-aware datetimes in app.

## SQLAlchemy Changes Required
- Use SQLAlchemy `JSON` type for cross-DB compatibility; on SQLite fallback to `types.Text` with `json.loads/json.dumps` at the mapper level.
- Use `sa.func.now()` for default timestamps; in SQLite ensure server_default is set to CURRENT_TIMESTAMP or fill from app.
- Migrations (Alembic) must include conditional blocks:
  - if context.get_x_argument(as_dictionary=True).get("dialect") == "sqlite": apply SQLite-compatible DDL.
- Primary key & unique constraints supported; composite PKs are honored.

## Environment Variable Changes
- PROD:
  - DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/intellihire
- DEV:
  - DATABASE_URL=sqlite+aiosqlite:///./dev_intellihire.db
- Ensure `AI_MODELS_ENABLED=true` for local tests requiring Groq mocks or set `GROQ_MOCK=true`.

## Step-by-Step Migration Procedure (numbered)
1. Create DB dumps from PostgreSQL (use pg_dump --data-only --column-inserts for core tables).
2. Transform JSONB columns in dump to plain JSON strings for SQLite.
3. Update SQLAlchemy connection URL in `.env` to `sqlite+aiosqlite:///./dev_intellihire.db`.
4. Adjust Alembic env.py to use `render_as_batch=True` for SQLite DDL modifications.
5. Run Alembic `upgrade head` against local dev DB.
6. Run data migration script to insert transformed rows (`scripts/migrate_pg_to_sqlite.py` — implement data-type conversions).
7. Run unit tests; verify `interview_answers.scores` round-trips JSON correctly.
8. Validate RL tables `rl_q_table` keys and defaults (ensure optimistic init).
9. If seeding fallback questions, run `scripts/seed_coding_questions.py`.
10. Commit migration scripts and document environmental changes.

## Rollback Procedure
1. Restore PostgreSQL from backup or use `pg_restore`.
2. If irreversible changes applied, notify ops and revert migrations using Alembic downgrade (careful with data loss).
3. For dev, delete `dev_intellihire.db` and re-run `alembic upgrade head` to create fresh schema.

## Data Integrity Verification Steps
- Check `interview_sessions` count matches expected rows.
- Verify `interview_answers.scores` JSON parsed and each key `technical,communication,confidence,problem_solving,total` exists.
- Confirm timestamps parse as UTC ISO8601 strings.
- Validate `rl_q_table` has primary key uniqueness (user_id,state,action) and `visit_count >= 0`.
- Run sample session end-to-end: start → 1 question → submit → ensure `interview_evaluation` created.
