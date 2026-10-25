# EDI5 Phase 7T - Local Uncertainty Resolution

- Assessment date: 2026-10-25
- Scope: repository-only review of department-default migration evidence and `refresh_tokens` ownership; safe ORM metadata tests.
- Safety: no connection to Supabase or any shared environment; no database writes, migrations, DDL/DML, role/credential changes, provisioning, backup/scratch/asset operation, or cutover.

## 1. Department-default migration

### Finding

**Revision:** `use_unspecified_student_department_default`

**Parent:** `add_faculty_practice_assignments`
**Cross-environment applied status: NOT VERIFIED.**

The revision file's upgrade alters `student_profiles.department` to have server default `Department Not Specified`, while passing `existing_server_default='Computer Science'`. Its downgrade explicitly sets the server default back to `Computer Science`. Repository migration history therefore proves the intended new default and the script's old-default assumption; it does not prove execution in any environment.

The parent revision is the latest revision recorded by the local source and by the Phase 7K scratch-restore report. Phase 7R's review found no deployment ledger in the inspected project documentation/configuration. `docs/DATABASE_WORKFLOW.md` says Alembic owns the development schema and documents `alembic current`/upgrade commands, but is procedure documentation, not evidence that a deployment occurred. Local Git history contains the revision file but cannot prove an environment applied it. No remote or shared environment was queried in this phase. A historical destination audit is not current deployment evidence.

The repository's schema definitions are not perfectly uniform across history: the consolidated baseline declares no server default for this department, while an older profile-table migration declared `Computer Science`. The parent schema's actual default must be taken from each target's live catalog, not inferred from an older create-table definition.

### Safest recommendation (not applied)

First obtain a read-only check from each supported environment, after independently verifying its identity. Record both its `alembic_version.version_num` and `information_schema.columns.column_default` for `public.student_profiles.department`.

- If the revision has never been released or applied anywhere, and the agreed behavior is a server-side default, the smallest history correction is to make the migration's `existing_server_default` accurately reflect the parent schema and make downgrade restore that parent state. Do not assume one historical DDL file describes all environments.
- If any environment has applied/shared the revision, do not rewrite the historical migration. After environments and defaults are reconciled, prepare a reviewed forward migration that sets the agreed default without rewriting existing department values. Define downgrade behavior against the verified baseline; do not restore `Computer Science` by assumption.
- If the desired behavior is application-side only, do not add a DB default; document that decision and keep ORM behavior consistent.

No migration SQL was generated or executed. **Required later query (read-only, identity-gated):**

```sql
SELECT version_num FROM public.alembic_version;
SELECT column_default
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'student_profiles'
  AND column_name = 'department';
```

Run separately against each explicitly authorized environment; do not use local/scratch results as a substitute for shared-environment evidence.

## 2. `refresh_tokens` purpose and ownership

### What repository evidence establishes

- The baseline Alembic migration creates `refresh_tokens` with `id`, `user_id`, `token_hash`, `expires_at`, `is_revoked`, and `created_at`, a cascading FK to `users`, and a non-unique index on `token_hash`. It also drops the table/index in its downgrade; that destructive downgrade is not authorized here.
- `database/schema.sql` and `database/complete_schema.sql` also declare the table/index.
- The `/auth/refresh` handler currently decodes an access token and issues another access token. Its docstring says opaque refresh tokens stored in this table are a future/production consideration. Repository search found no token-table ORM model, persistence service, or runtime query/write to the table.
- Earlier local read-only reports recorded the table present and empty. That is only a point-in-time count; it does not establish obsolescence, ownership outside EDI5, retention policy, or whether another deployed consumer exists.

**Likely classification:** EDI5-authentication schema reserved for a possible future opaque-token flow; current application runtime usage is not present in inspected code. **Unverified:** actual owner, any external/deployed consumers, retention/security requirements, and whether the feature is still planned.

### Required owner decision and preservation-first recommendation

The decision must be made jointly by the **authentication/security owner** and **schema/data owner**; repository files do not name an individual accountable owner. Record whether EDI5 continues to own this as migration-managed dormant schema or intentionally leaves it unmanaged-but-preserved. Until that decision is recorded, preserve the table, all records, constraints, index, and backup representation. Do not invent a model, token format, expiry/rotation/revocation behavior, or retention policy. Ensure future migration review cannot silently propose dropping it.

Before changing its treatment, the owners need evidence of table definitions and dependencies across approved environments, any runtime/deployed consumers, record counts and retention obligations, backup/restore coverage, and an explicit decision authorizing a schema-management change. No such change occurred in Phase 7T.

## 3. Safe test result

Inspected `tests/test_schema_orm_drift_metadata.py` and `tests/conftest.py` before execution. The normal conftest session fixture can drop/recreate a configured test database, so the focused offline test ran with conftest disabled and cache provider disabled. Its assertions compare FK source/target/delete action, partial-index columns/uniqueness/predicates, and relevant column/FK metadata; they are not name-only checks.

- `python -m pytest --noconftest -p no:cacheprovider tests/test_schema_orm_drift_metadata.py -q` — **5 passed**.
- No test requiring database writes or shared environment access was run. No assertion was skipped or weakened.

## 4. Remaining blockers to isolated staging

1. **Owner authorization:** still need project owner, organization, region, maximum cost and currency/current plan confirmation, approved scope and data/asset handling, role model, named rollback owner, and explicit provision-now approval. These are owner decisions, not coding work.
2. **Migration status:** cross-environment application/default status is **NOT VERIFIED**; obtain the identity-verified read-only checks above before deciding whether historical correction or a forward revision is appropriate.
3. **Authentication/schema ownership:** auth/security and schema/data owners must make and record the preservation/management decision for `refresh_tokens`.
4. **After an isolated stage is authorized and exists:** verify its project identity, TLS/CA, version, connection mode, empty inventory, effective least-privilege roles, source/stage inventories and PK overlaps; rehearse restore and acceptance checks; verify asset mapping and rollback ownership. None can be claimed complete before provisioning.
5. Existing populated destination remains **UNKNOWN - PRESERVE** and is not staging. No Phase 7T query or change to it is authorized.

## 5. Commands actually executed

- `git status --short`, `git diff --cached --stat`, `git diff --stat` — initial state captured; no staged changes.
- Focused `Get-Content` of the migration, `docs/DATABASE_WORKFLOW.md`, Phase 7S report, auth router, and test/conftest files — inspected.
- `git log --all --format="%h %ad %s" --date=short -- alembic/versions/use_unspecified_student_department_default.py` — one local commit shown; establishes source-control history only.
- Focused `rg` searches for revision IDs, deployment/release filenames, `refresh_tokens`, and token-handling references — no deployment ledger or runtime token-table use found in the inspected repository; matches were migration/schema declarations and the auth-route future-use comment.
- `python -m pytest --noconftest -p no:cacheprovider tests/test_schema_orm_drift_metadata.py -q` — **5 passed**.
- Final `git diff --check` and direct trailing-whitespace checks — results recorded after report update.
- No database connection, Alembic CLI, migration, destination audit, DDL/DML, provisioning, credential/role operation, restore, backup operation, or asset operation was performed.

**Phase 7T decision:** cross-environment migration status remains **NOT VERIFIED**; `refresh_tokens` remains preservation-first with ownership unresolved. Keep staging **BLOCKED** until owner decisions are recorded and required post-provisioning checks can be safely completed under a later authorization.
