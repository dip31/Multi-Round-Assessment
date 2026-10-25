# EDI5 Phase 7U - Local Migration Handoff

- Prepared: 2026-10-25
- Purpose: consolidate verified local preparation into a handoff; no new audit or migration executed.
- Safety: no Supabase connection, provisioning, database/credential/role change, restore, asset operation, or cutover occurred in Phase 7U.

## Readiness evidence

| Item | Status | Handoff finding |
|---|---|---|
| Local source identity | **VERIFIED (reported evidence)** | `ai_placement_platform`, PostgreSQL 16.13, loopback port 5432, current source revision `add_faculty_practice_assignments`; 39 public tables, 6,641 total rows including `alembic_version` (6,640 application rows). Source remains local. Phase 7U did not reconnect. |
| Verified backup identity | **VERIFIED (Phase 7K)** | `C:/Users/Akshada/AppData/Local/EDI5-Backups/ai_placement_platform_20261025T094836Z_phase7j_verified.dump`; 530,714 bytes; SHA-256 `466D701CAC2CA0C65B0793D7F5F4B2770BFE21C9BE88DD7C77DDD8C23418886B`. Keep the archive and manifest unchanged. |
| Scratch restore | **VERIFIED - LOCAL SCOPE ONLY** | Phase 7K restored to a new, separately identified local scratch database; all 39 table counts and full-row fingerprints matched the captured source snapshot. It did not prove Supabase restore compatibility, role/ACL behavior, application behavior, or external asset portability. The existing Phase 7K scratch database is preservation-only and must not be reused as a destructive test target. |
| Schema/ORM | **PARTIAL** | Phase 7Q prepared ORM metadata for the source's `rl_attempt_log` FKs and two partial unique indexes; focused metadata tests passed. `coding_problems.blueprint_id` is nullable but lacks the intended `company_blueprints.id ON DELETE SET NULL` FK on the source; reported orphan count was zero at that snapshot. Student department has no DB default on source. Do not treat ORM declarations as proof a migration was applied. |
| Department migration deployment | **NOT VERIFIED** | Repo head is `use_unspecified_student_department_default`, parent `add_faculty_practice_assignments`. Upgrade sets `Department Not Specified` but assumes old `Computer Science`; downgrade restores `Computer Science`. Local source/scratch are at the parent. No evidence establishes status in all shared environments. |
| `refresh_tokens` | **OWNER DECISION REQUIRED** | Baseline migration and SQL schema files define it; current auth code only refreshes access JWTs and mentions opaque table-backed tokens as a future option. Runtime persistence was not found. Preserve table, definition, records and backup representation pending authentication/security and schema/data owner decision. |
| Existing destination | **BLOCKED / UNKNOWN - PRESERVE** | Phase 7M historically found a populated destination and an over-privileged audit role. This is not a current re-audit; ownership remains uncertain. Do not use it as staging or infer its present state from prior reports. |
| Staging authorization | **OWNER DECISION REQUIRED** | No named owner/organization/region, maximum budget and currency, scope, role model, asset/data handling, rollback owner, or explicit provisioning approval is recorded. No project or cost is authorized. |

## Backup verification and restore-validation references

These commands are handoff references only. Phase 7U did not rerun backup checks or restore. Use the recorded backup path above; do not redirect output over the archive.

Read-only file checksum and archive listing:

```powershell
$backupPath = 'C:\Users\Akshada\AppData\Local\EDI5-Backups\ai_placement_platform_20261025T094836Z_phase7j_verified.dump'
Get-Item -LiteralPath $backupPath | Select-Object Length, LastWriteTimeUtc
Get-FileHash -LiteralPath $backupPath -Algorithm SHA256
& 'C:\Program Files\PostgreSQL\16\bin\pg_restore.exe' --list $backupPath
```

Expected size/hash are listed above. `pg_restore --list` reads the archive TOC; it does not restore it.

**Restore reference - NOT RUN; requires a separately approved, newly verified, empty disposable scratch database.** Never substitute the source, protected existing scratch database, verified Phase 7K scratch database, or Supabase destination. First verify that the exact target database name is absent, then create a unique scratch database only under a later explicit authorization. The restore command must target that exact empty database and omit `--create` and `--clean`:

```powershell
& 'C:\Program Files\PostgreSQL\16\bin\pg_restore.exe' `
  --host localhost --port 5432 --username postgres `
  --dbname '<new-unique-empty-scratch-db>' `
  --no-password --no-owner --no-privileges --exit-on-error --single-transaction `
  $backupPath
```

The Phase 7K scratch restore already passed its local row-count and full-row fingerprint comparison. Do not rerun it against that existing scratch database.

## Read-only migration/default check for authorized environments

**NOT RUN in Phase 7U.** After separately authorized access and independent endpoint identity verification, collect these values per environment inside a read-only transaction; do not rely on local or historical destination values:

```sql
BEGIN TRANSACTION READ ONLY;
SELECT current_database(), current_setting('server_version'), current_user;
SELECT version_num FROM public.alembic_version;
SELECT column_default
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'student_profiles'
  AND column_name = 'department';
COMMIT;
```

Record the environment identity and capture time without credentials. If an environment has applied/shared the department revision, do not rewrite migration history; review a forward correction against each environment's actual default. If none has applied it and it was never released, an owner-reviewed correction to the historical migration may be considered. Decide first whether the intended default is application-side or database-side. No correction is applied here.

## External assets

Phase 7P's local read-only inventory recorded:

- **Resumes - PARTIAL:** 41 database references resolved to local files; the directory held 87 files. Preserve unreferenced files; their presence alone does not make them disposable.
- **Company historical uploads - PARTIAL:** 51 records total; 28 file-upload records had paths resolving locally; the directory held 487 files. The other records include manual/pre-seeded data. Preserve all files.
- **Knowledge-base index - VERIFIED LOCAL FILE ONLY:** `app/data/kb.index`, 199,725 bytes, SHA-256 `E8070082A5CDAE71FABF13491869312324798D4F7FAD23A13B06E1AFE5B19C36` in the prior audit. It is an application asset, not database state.

Before staging, owners must approve asset scope, access, retention and transfer. Build a manifest mapping each included database reference to an asset identifier and checksum; test paths/access in an isolated copy. The Phase 7P path resolution is local evidence only; no asset transfer or staging mapping is verified. Do not move, rename, overwrite, rebuild, or delete originals.

## Future staging verification

All items below are **NOT VERIFIED** until a distinct isolated staging project is owner-approved and exists. Do not use the current populated destination.

1. Verify project owner, organization, assigned project reference, region and database identity; confirm it is distinct from the protected destination.
2. Positively verify TLS with the new project's trusted CA and hostname validation (`sslmode=verify-full`); record PostgreSQL version, connection/pooler mode and effective role. Do not bypass TLS checks.
3. Inventory the empty stage and current source: schemas/tables, revision, counts, constraints/FKs/orphans, indexes/predicates, sequences, extensions and privileges. Keep provider-managed schemas out of generic restore scope.
4. Compare compatible primary-key definitions and compute privacy-preserving overlap counts. Resolve entity ownership and natural-key conflicts; historical Phase 7G overlap counts are not current evidence.
5. Verify separate least-privilege migration operator, runtime identity, and read-only auditor; document exact grants, RLS/default privileges and absence of unnecessary elevated powers.
6. Rehearse restore only into an approved disposable staging target; validate schema, aggregate row counts/fingerprints, FK/orphan state, indexes, sequences, extensions, ACLs and written acceptance thresholds.
7. Verify application behavior with staging-only configuration and non-production accounts, including auth/session flows, upload retrieval, external integrations and background jobs.

## Acceptance and rollback prerequisites

Before a later import, owners and technical reviewers must agree written thresholds for identity/TLS, schema/revision, per-table counts/fingerprints, constraints/orphans, indexes, sequences/extensions, role privileges, application workflows and asset mapping. Resolve department migration distribution and `refresh_tokens` ownership before generating migration SQL. No PK collision or entity mapping result is currently verified for a future stage.

Name a rollback owner and approve triggers, recovery point, immutable source/backup retention, staging isolation, application/config rollback, failed-stage evidence retention and cost stop conditions. A failed staging exercise must not require changing the source, verified backups, Phase 7K scratch DB, original assets, or protected existing destination. Production cutover requires a separate go/no-go and is outside this handoff.

## Phase 7U execution record

- Reviewed Phase 7Q, 7R, 7S, 7T and the overall migration status; reused their evidence rather than repeating database or backup audits.
- No tests were rerun; the existing Phase 7Q/7R offline test results remain as reported in those phase records.
- Only documentation whitespace/diff checks were run after edits; results are recorded in the overall status update/final response.
- Created this handoff and appended a dated summary to the overall migration status. Existing work was preserved; no database, backup, scratch database, credential, role, destination, or asset was changed.
