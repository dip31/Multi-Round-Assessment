# EDI5 Phase 7R - Remaining Local Gaps and Staging Gate

- Assessment date: 2026-10-25
- Scope: resolve locally available evidence questions, review Phase 7Q metadata changes, and define the evidence gate for an owner-approved isolated staging environment.
- Safety: no Supabase connection/query, database write, migration, DDL/DML, credential/role change, project provisioning, backup/scratch operation, or asset operation.

## Preservation and evidence reviewed

The initial `git status --short` was captured before edits. Pre-existing modifications/untracked files were preserved, including `app/config/settings.py`, `requirements.txt`, certificate and prior audit artifacts, the Phase 7Q report/test, audit script, and other listed files. There were no staged changes. Phase 7Q model diffs and the complete untracked test were inspected; unrelated diffs were not edited.

Reviewed `docs/DATABASE_WORKFLOW.md`, Alembic `env.py` and revision files, the consolidated baseline migration, auth router/service/model references, Phase 7Q/7P/7O/7N evidence, and current local source metadata. The only directly queried database was the expected local source, behind a loopback/database gate and with `SET TRANSACTION READ ONLY`. It reported revision `add_faculty_practice_assignments` and no server default on `student_profiles.department`. No destination endpoint was contacted.

## Department-default migration

**Cross-environment application status: NOT VERIFIED.**

Evidence available:

- Current local source and Phase 7K scratch reports are at `add_faculty_practice_assignments`, the parent of `use_unspecified_student_department_default`.
- Current local source column has no server default. The revision changes it to `Department Not Specified`, but declares an assumed old default of `Computer Science`; its downgrade sets that old value back.
- `docs/DATABASE_WORKFLOW.md` states Alembic owns the development schema and documents commands; it is operating procedure, not an application/deployment ledger.
- Local Git history contains the migration file, which establishes repository history only. It does not establish which deployments applied it.
- No deployment ledger or other trustworthy shared-environment migration record was found in the inspected project documentation/configuration. This phase did not connect to Supabase or any shared environment. A prior audit's remote revision is historical evidence and cannot establish current status or map that revision to this migration.

Smallest safe recommendation, **not applied**:

1. Obtain a read-only `alembic_version` and `information_schema.columns.column_default` check from every currently supported environment, with endpoint identity verified independently first. Record environment and capture time without credentials.
2. If no environment has applied the revision and it has not been released/shared, correct that revision's starting-default assumption and downgrade to match the real parent schema.
3. If any environment has applied/shared it, leave migration history immutable and prepare a new forward correction. The forward change should set the chosen default without rewriting existing department values; guard/review actual defaults per target. A downgrade must restore each target's verified prior state, not assume `Computer Science` universally.
4. Confirm whether the desired default is application-only or a database server default. If DB-level, align ORM metadata and review generated SQL offline.

**Later read-only verification required:** project/environment identity, current revision, and actual column default per environment. Until that evidence exists, editing the historical revision or choosing one universal downgrade is unsafe.

## `refresh_tokens` purpose and ownership

**Likely purpose: EDI5-managed authentication schema reserved for a future opaque refresh-token flow. Runtime use: not found.**

The baseline migration creates the table with `id`, `user_id`, `token_hash`, `expires_at`, `is_revoked`, and `created_at`, a cascading FK to `users`, and a non-unique index on `token_hash`. Repository SQL schema files also declare it. The auth `/refresh` endpoint currently validates an access token and issues a replacement; its docstring explicitly describes opaque tokens in this table as a production consideration/future option. A repository search found no token persistence service or other runtime reads/writes. Earlier read-only source evidence reports the table exists and is empty; that does not make it obsolete or safe to remove.

The repository does not identify an individual table owner. The responsible decision belongs to the authentication/security feature owner and the application data/schema owner. Preserve the existing table and all records; do not infer or add columns. Before generating a migration, those owners must decide whether it is an inert EDI5-managed future table or intentionally unmanaged-but-preserved. The least-risk path is to keep its baseline/catalog definition intact and ensure metadata/autogeneration cannot propose dropping it. Any mapping must reproduce the known complete schema exactly and add no authentication behavior without a separate feature decision.

## Phase 7Q diff review

| Review point | Result |
|---|---|
| `rl_attempt_log` foreign keys | **PASS**: ORM declarations point `session_id` to `assessment_sessions.id` and `question_id` to `aptitude_questions.id`. Existing `user_id -> users.id` is retained. All three use default `NO ACTION`, matching the live source's `confdeltype` and definitions. Nullability remains nullable. No FK is removed. |
| Partial unique indexes | **PASS**: session index is unique on `user_id` under `status = 'in_progress'`; round index is unique on `session_id` under `status = 'active'`. Names, key columns, uniqueness, and PostgreSQL/SQLite predicates match the migration and live source semantics. |
| Regression assertions | **PASS**: tests compare FK source/target/delete action sets; index uniqueness, columns, and predicates; department nullability/Python default/server default; and blueprint FK nullability/target/delete action. They assert substantive metadata, not name presence alone. |
| Table creation behavior | **EXPECTED CHANGE**: `Base.metadata.create_all` now creates the two declared partial indexes and the two added FK constraints for fresh metadata-built schemas. This is intentional parity with the verified live source, and changes test/fresh-schema creation. No table or column is added by these edits. |
| Alembic migration behavior | **NO migration-file change**: existing Alembic revision files and operation bodies are untouched. Because target metadata now represents objects already present on the verified source, autogenerate should stop reporting these metadata gaps there. That expectation still needs a reviewed offline comparison against each target; it is not proven for another environment. |
| Unrelated work | **PRESERVED**: the pre-existing settings/requirements changes, root artifact, certificates and prior audit artifacts were not edited. |

The modified code files are `app/models/assessment.py` and `app/models/rl.py`; the Phase 7Q test file is untracked in this working tree and was inspected in full. No migration, test fixture, app config, or database code was modified in Phase 7R.

## Isolated staging evidence gate

Do not provision or load data until each item is documented and explicitly approved:

- [ ] **Owner and project authorization:** named owner; organization; project name/reference; region; data scope; retention; monthly budget/currency and alerts; written approval to provision this isolated project. Confirm no reuse of the populated existing destination.
- [ ] **Identity and transport:** independently verify the new project's expected reference/database identity, endpoint/connection mode, client-side TLS with `verify-full` and trusted CA, and the intended staging-only credentials. Record redacted evidence only.
- [ ] **Current source and destination inventories:** capture table/schema/revision/version, relevant constraints/indexes/sequences/extensions and aggregate counts from a frozen verified source/backup and the empty isolated destination. Recheck identity and TLS first. Do not treat old destination audit evidence as current staging evidence.
- [ ] **Primary-key overlap:** compare compatible table/key definitions using bounded reads and in-memory keys; report aggregate overlaps only. Resolve shared-ID entity ownership and natural-key conflicts before any append/merge. No current destination collision result is verified.
- [ ] **Least privilege:** document and verify distinct migration-operator, runtime, and read-only audit roles, exact required grants, RLS/default privileges and denied elevated powers. Role owners approve; no shared broad audit credential.
- [ ] **Assets:** map each database asset reference to its source file/checksum and owner/retention category; account for resume files, historical company uploads and the KB index/metadata pair. Approve an isolated transfer/path-mapping plan and validate the staging copy without moving or deleting originals.
- [ ] **Backup and rehearsal:** identify the immutable verified backup by size/hash/manifest; approve a separate disposable staging target; rehearse restore only there; capture pre/post schema and aggregate row/fingerprint checks; prove no writes target source or existing destination.
- [ ] **Acceptance and rollback:** define acceptance thresholds for data, constraints, sequences, application auth/session behavior, assets, TLS and least privilege; name the rollback owner; document stop triggers, recovery point, credentials/config rollback, staging cleanup and cost stop conditions. Obtain approval before any restore/import.

All staging items remain **BLOCKED / NOT VERIFIED** until approvals and evidence are supplied. This phase did not connect to or inspect the existing destination.

## Tests and commands executed

- Inspected `tests/conftest.py` before test execution. Its session fixture can drop/recreate a configured test database; tests were run with `--noconftest` and `-p no:cacheprovider` to avoid that fixture and cache writes.
- `python -m pytest --noconftest -p no:cacheprovider tests/test_schema_orm_drift_metadata.py tests/test_db_isolation_guard.py -q`: **9 passed**.
- Local read-only source metadata query (loopback identity gate): confirmed revision and department default; **PASS**.
- `git status --short`, `git diff --cached --stat`, `git diff --stat`, focused `git diff`, `git log --all --oneline --decorate -- <migration>`, focused `Get-Content`/`rg` inspections: completed. A broad `rg` invocation included absent optional paths and printed file-not-found diagnostics; it did not modify files. Follow-up searches of existing docs/config and tracked revision history found no deployment ledger.
- `git diff --check` and direct trailing-whitespace checks for new report files: final results recorded after writing below.
- No Alembic CLI, migration, restore, destination connection/query, DDL/DML, role operation, cloud resource, backup, scratch database or asset operation was run.

**Phase 7R decision:** local source and test evidence are sufficient to review the Phase 7Q ORM parity changes. Department-default application outside local source/scratch is **NOT VERIFIED**. `refresh_tokens` is migration-managed and likely reserved for future EDI5 authentication, but its feature/data owner must affirm its status. Do not edit migration history or generate/apply migration SQL until environment state and ownership decisions are documented. Staging remains gated on every checklist approval and verification item above.
