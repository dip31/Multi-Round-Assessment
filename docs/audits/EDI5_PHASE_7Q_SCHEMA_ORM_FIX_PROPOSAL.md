# EDI5 Phase 7Q - Schema/ORM Drift Fix Proposal

- Assessment date: 2026-10-25
- Scope: inspect the local PostgreSQL source, ORM metadata and Alembic history; prepare safe ORM parity fixes and database-free regression tests.
- Safety: no Supabase connection; no migration, restore, DDL/DML, credential/role change, asset operation, or scratch-database use.

## Evidence and preservation

Initial `git status --short` showed pre-existing changes in `app/config/settings.py` and `requirements.txt`, the root `-` file, certificates, prior audit reports, the audit script, and its tests. No staged changes were present. These were preserved. The local source configuration was parsed without printing its connection value and gated to loopback, port 5432 (including PostgreSQL's default when omitted), and database `ai_placement_platform` before connecting. The session verified PostgreSQL 16.13, role `postgres`, server address `::1`, port 5432, and transaction `read_only=on`; Alembic revision was `add_faculty_practice_assignments`.

The first stdin-based dotenv probe failed before connecting because automatic `.env` discovery asserted without a caller file. An explicit repository `.env` path was then used. One subsequent identity gate initially rejected an omitted URL port; the gate was corrected to treat the PostgreSQL default as 5432. Neither attempt connected to another endpoint. The successful catalog inspection used SELECT/catalog queries only.

## Findings and proposed minimum fixes

| Area | Status | Evidence and risk | Proposed change and verification |
|---|---|---|---|
| Student department default | **PARTIAL** | Live `student_profiles.department` is NOT NULL with no server default. ORM has Python default `Department Not Specified` and no server default. The repository head migration `use_unspecified_student_department_default` follows the live source revision, but claims its old server default was `Computer Science`; the historical profile-table migration did initially create that default. That historical create definition does not establish the current live default. Existing rows are unaffected by setting a default, but an incorrect `existing_server_default` can misstate the migration's starting schema and downgrade. | Prefer a reviewed forward migration that preserves existing values and sets the server default to `Department Not Specified` if the DB-level default is intended. It should describe the verified no-default source accurately; downgrade should restore no default only after checking target revision/schema. Do not rewrite the current revision until its distribution/application in all environments is known. If the current revision is unpublished everywhere, correct its old-default assumption instead. Keep ORM `server_default` aligned only if adopting a DB-level default. Regression test: metadata default/nullability plus offline upgrade/downgrade SQL review; verify inserts omitting the field in isolated staging. No migration run. |
| `refresh_tokens` | **PARTIAL / OWNER DECISION NEEDED** | The baseline migration creates a six-column table (`id`, `user_id`, `token_hash`, `expires_at`, `is_revoked`, `created_at`), FK to `users` with CASCADE and a non-unique `token_hash` index. Current source has these columns and index, and count is zero. ORM metadata omits it. Application auth uses access-token refresh behavior; its route says stored opaque refresh tokens are a future option. This supports a dormant/reserved migration-managed table, not proof it is disposable or actively used. Autogenerate could misinterpret the omission. | Preserve the table. Smallest safe metadata choice is either an exact passive ORM mapping with no auth CRUD behavior, or an explicit Alembic preservation rule if the owner wants it deliberately unmanaged. Do not invent columns or drop it based on count. Auth/data owner must choose. Verification: inspect offline autogenerate output against a catalog snapshot and ensure it proposes no drop; confirm mapping/index/constraint parity. No mapping or exclusion rule added in this phase. |
| `coding_problems.blueprint_id` | **PARTIAL** | Live column is nullable integer; no live FK is installed; current orphan count is zero. ORM and `add_question_pool_generation.py` specify nullable FK to `company_blueprints.id ON DELETE SET NULL`. This is a clear catalog/migration drift; a zero orphan count lowers immediate validation risk but can change after the snapshot. | Preserve nullability and existing values. Prepare a forward-only FK repair after rechecking target existence and zero orphans on the migration snapshot; if a constraint exists on another target, inspect before applying. Do not alter the historical migration without proving it is unpublished. The ORM declaration already captures the expected intent. Verify source/backup constraint and delete action plus offline DDL; test deletion/nullable behavior only in isolated staging. No DDL run. |
| `rl_attempt_log` | **PARTIAL; ORM PARITY FIX PREPARED** | Live source FKs are `user_id -> users.id`, `session_id -> assessment_sessions.id`, and `question_id -> aptitude_questions.id`, all with default `NO ACTION` behavior. Baseline migration and current ORM only declare the user FK. Application references these fields as log data; no application code intentionally removes constraints. Existing constraints must be preserved. | Added ORM FK declarations for session and question with no `ondelete`, matching the live `NO ACTION` behavior. Added database-free metadata tests for all three FKs. This changes metadata only and does not add/drop live constraints. Verify offline autogenerate against live schema yields no change for these FKs, and compare with the verified backup before later migration work. |
| Partial unique indexes | **PARTIAL; ORM PARITY FIX PREPARED** | Live definitions are unique `assessment_sessions(user_id)` where status is `in_progress`, and unique `assessment_rounds(session_id)` where status is `active`. Both are also present in `add_assessment_lifecycle_timing.py`; model declarations were missing. Installed SQLAlchemy is 2.1.1 and supports dialect-specific `Index` predicates; metadata test introspection passes. | Added matching named `Index` metadata declarations with PostgreSQL and SQLite predicates. The changes do not execute index DDL. Focused tests assert names, columns, uniqueness, and both predicates. Later verify dialect compilation and offline autogenerate produce no duplicate index operation against the live schema. |

### Safe code changes prepared

- `app/models/rl.py`: add the two verified live-source foreign keys to `RLAttemptLog`.
- `app/models/assessment.py`: represent the two already migration-managed partial unique indexes in metadata.
- `tests/test_schema_orm_drift_metadata.py`: database-free checks for those FKs/indexes, the current department Python-only default, and the existing nullable `coding_problems.blueprint_id` FK intent.

No Alembic revision was edited or executed. The department fix and `refresh_tokens` ownership remain proposals because migration distribution/ownership is unresolved. Existing data, backups, the Phase 7K scratch database, and assets were not modified.

## Test and verification plan

**Executed:**

- Local source identity and schema catalog checks: PASS under an explicit local identity gate and read-only transaction. Only identity/catalog metadata and aggregate orphan/table counts were selected; no row contents or personal data were emitted.
- `python -m pytest --noconftest -p no:cacheprovider tests/test_schema_orm_drift_metadata.py -q`: **5 passed**. `--noconftest` intentionally bypasses the inspected session fixture that may drop/recreate a configured test database. The initial attempt produced four test failures from incorrect test setup (missing explicit model imports and an unsupported `Table.indexes_by_name` accessor); the test was corrected and the final run passed. No DB connection occurred in either test run.
- Installed SQLAlchemy version query: **2.1.1**.
- No application-wide tests or database-backed tests were run. No Alembic command was run.

**Required later, in an approved isolated environment:**

1. Resolve all-environment migration distribution and department-default intent.
2. Compare ORM metadata to the live source and verified backup using offline autogenerate/catalog diff; require no unexpected drops and no duplicate creates.
3. Test constraints, default behavior and partial-index rejection with isolated test data in a separately identified disposable database, never the source or Phase 7K scratch DB.
4. Verify `refresh_tokens` owner decision and table preservation before generating migration scripts.

## Rollback and unresolved questions

- ORM metadata edits are reversible source changes, but reverting them before schema alignment could reintroduce false autogenerate diffs. Review and version control them with the corresponding migration plan.
- Do not downgrade a department-default migration until each target's current revision and actual column default are checked. A downgrade that sets `Computer Science` would not restore this verified source state.
- Does any shared environment already have `use_unspecified_student_department_default` applied?
- Should `refresh_tokens` be represented by an inert ORM model or preserved by an Alembic include-object rule? Who owns the future opaque-token feature?
- Are live `rl_attempt_log` constraints intentionally more complete than the baseline migration? Verify the backup and other approved environment catalogs before selecting a migration path.
- Is the intended student default only an application default, or should direct SQL inserts receive the same DB default?
- Destination identity, privileges, collision counts, and Supabase compatibility remain outside Phase 7Q and unverified here.

## Commands and checks actually executed

- `git status --short`, `git diff --cached --stat`, `git diff --stat` (initial working-tree snapshot).
- Focused `Get-Content` and `rg` inspections of Phase 7P/7O/overall reports, model files, Alembic revisions, auth references, requirements, and test harness behavior.
- Read-only Python/SQLAlchemy catalog query using explicit dotenv path and local target gate; one first dotenv autodiscovery probe failed before connecting, and one default-port gate check was corrected before the successful query.
- `python -c "import sqlalchemy; print(sqlalchemy.__version__)"` (version only).
- `python -m pytest --noconftest -p no:cacheprovider tests/test_schema_orm_drift_metadata.py -q` (initial setup run: 4 failed, 1 passed; final corrected run: 5 passed).
- `git diff --check` and final `git status --short`/diff review are recorded in the overall status update after report creation.

**Phase 7Q decision:** safe ORM metadata parity for verified live constraints/indexes is prepared and covered by offline tests. Department migration correctness and `refresh_tokens` ownership remain unresolved; no database migration or staging work is authorized. Preserve source, backup, scratch database and assets.
