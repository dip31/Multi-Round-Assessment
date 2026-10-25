# EDI5 Phase 7O - Non-destructive Migration Readiness

- Assessment date: 2026-10-25
- Scope: validate the local source/backup/scratch identities, review prior audit evidence and diffs, inspect safe offline checks, and record readiness gaps.
- Safety: no Supabase connection, cloud provisioning, credential change, database write, restore, migration, asset change, or cutover occurred in Phase 7O.

## Git preservation and evidence reviewed

Initial `git status --short`:

```text
 M app/config/settings.py
 M requirements.txt
?? -
?? certs/
?? docs/audits/EDI5_PHASE_6C_3_SUPABASE_DESTINATION_AUDIT.md
?? docs/audits/EDI5_PHASE_7K_20261025_022d4117/
?? docs/audits/EDI5_PHASE_7K_SCRATCH_RESTORE_VALIDATION.md
?? docs/audits/EDI5_PHASE_7L_SUPABASE_DESTINATION_OWNERSHIP_AND_STAGING_PLAN.md
?? docs/audits/EDI5_PHASE_7M_CREDENTIAL_RECOVERY_AND_DESTINATION_REAUDIT.md
?? docs/audits/EDI5_PHASE_7N_ISOLATED_STAGING_APPROVAL_AND_PLAN.md
?? docs/audits/EDI5_PHASE_7_LOCAL_TO_SUPABASE_MIGRATION_STATUS.md
?? scripts/audit_supabase_destination.py
?? tests/test_supabase_audit_config.py
```

No staged changes were present. The tracked diff was reviewed: `app/config/settings.py` has the existing `extra="ignore"` setting, and `requirements.txt` has the existing `python-dotenv` dependency. Both are pre-existing work and were left untouched. Phase 7J evidence is recorded in the overall status report; the Phase 7K, 7L, 7M, and 7N reports were reviewed. No file was reset, cleaned, stashed, reverted, or overwritten.

## Readiness checklist

| Area | Status | Verified evidence and remaining limitation |
|---|---|---|
| Local source identity | **COMPLETE** | Read-only query confirmed effective application target `localhost:5432/ai_placement_platform`, PostgreSQL 16.13, loopback, revision `add_faculty_practice_assignments`, 39 public tables, 6,641 bounded-exact rows. No source mutation occurred. |
| Verified backup identity | **COMPLETE** | Current file read-only check: 530,714 bytes and SHA-256 `466D701CAC2CA0C65B0793D7F5F4B2770BFE21C9BE88DD7C77DDD8C23418886B`, matching Phase 7K. `pg_restore --list` exited 0 and current normal listing had 438 numbered records. Phase 7I's prior verbose listing had 442 entries, explaining the four additional `DATABASE`, `ENCODING`, `SEARCHPATH`, and `STDSTRINGS` descriptors. This is archive/TOC verification, not a new restore. |
| Restore validation | **COMPLETE - LOCAL SCOPE ONLY** | Phase 7K reports a successful isolated local scratch restore, matching all 39 row counts and full-row fingerprints. Phase 7O independently confirmed the scratch DB remains on local PostgreSQL 16.13 with 39 tables and 6,641 rows at the same Alembic revision. ACL/runtime-role behavior, application behavior, and Supabase compatibility were not established by that restore. |
| Source schema/Alembic drift | **PARTIAL** | Source revision and repository head are known: source `add_faculty_practice_assignments`, head `use_unspecified_student_department_default`. Phase 7M's last destination audit found revision `47555f247a64`, not matching source history. Department-default assumptions, `refresh_tokens`, `coding_problems.blueprint_id`, `rl_attempt_log` FK/model drift, and partial-index differences remain unresolved or require revalidation against the eventual isolated target. |
| PK collision / entity mapping | **BLOCKED** | Current Phase 7M overlap analysis did not produce a usable result. The 2,486 overlapping keys in 21 tables are historical Phase 7G observations only. Before any import/merge, run a bounded, privacy-preserving aggregate comparison on approved source/staging data and separately resolve natural-key/entity mapping. Never infer entity equality from matching IDs. |
| Existing destination audit-role remediation | **BLOCKED** | Phase 7M found write permissions on 69 visible tables and elevated role attributes. No permission change is authorized or performed. Do not reuse this identity as runtime or migration role. Any remediation needs a future approved target and role-specific plan. |
| Separate runtime/migration/audit roles | **PARTIAL** | Phase 7N has conceptual least-privilege role boundaries. Exact platform-supported roles, grants, default privileges, RLS, and operator capabilities are not verified for a future project; no roles were created. |
| External assets and database paths | **PARTIAL** | Prior reports record 87 resume files and 487 company-history upload files with manifest/hash checks (Phase 7I), and a KB index matching its manifest/Git blob. Local code stores filesystem paths in resume/company records. Phase 7O did not rehash each asset or validate row-to-file mappings; originals remain untouched. |
| TLS and project identity | **PARTIAL** | Phase 7M positively verified TLS (`verify-full`, pinned CA) and expected identity for the existing destination. Phase 7O did not reconnect. No staging project exists, so its distinct identity and CA/TLS cannot yet be verified. |
| Rollback/recovery | **PARTIAL** | Phase 7N documents isolation, retention, rollback ownership and acceptance gates. No rollback was rehearsed, no staging resource exists, and owner selections for region, scope, cost, roles and rollback owner are absent. |
| Owner authorization / staging boundary | **BLOCKED** | Phase 7N approval checklist remains unfilled. No project identity, owner, region, scope, cost ceiling/currency, role approvals, data/asset retention, rollback owner, or explicit provision-now authorization has been supplied. |

### Schema and data preparation still needed

- Resolve the source/repository Alembic baseline and review all migration assumptions before preparing executable migration SQL.
- Reconcile the student department default, `refresh_tokens` ORM omission, `coding_problems.blueprint_id`, `rl_attempt_log` foreign keys, and required partial unique indexes against the verified source/backup.
- Define exact included application schemas/objects and explicitly exclude Supabase-managed schemas from generic restore procedures.
- Reconcile sequence and trigger counting differences reported by the Phase 7M audit before using those totals as acceptance criteria.
- Resolve current key/natural-key collision and entity ownership analysis; existing destination data remains UNKNOWN - PRESERVE.
- Define role ACLs, extension versions, auth/session keys, staging-only configuration, path mapping, and asset-copy verification in an approved isolated target.

## Offline script and test safety review

| Check/tool | Safe behavior inspected | Phase 7O use/result |
|---|---|---|
| `tests/test_supabase_audit_config.py` | Tests use temporary fixture env files and in-memory TLS metadata/certificate fixtures; they do not create an engine or connect to a database. Fixture writes are confined to pytest temporary directories. | Ran `python -m pytest -p no:cacheprovider tests/test_supabase_audit_config.py -q`: **14 passed**. |
| `scripts/audit_supabase_destination.py --self-test-config` | Explicit self-test calls the config loader with an empty environment and a deliberately nonexistent dotenv path, then exits before `audit()`/engine creation. | Ran; **PASS: missing audit URL detected safely; no connection attempted**. |
| `scripts/audit_supabase_destination.py` default mode | Loads the configured audit URL, verifies TLS, then creates a Supabase engine and queries destination catalogs. It is not offline. | Not run in Phase 7O. |
| `pg_restore --list` | Reads the local archive TOC and does not restore or write to a database/file. | Ran read-only; exit 0; 438 normal-list entries. |
| Local identity/count check | Uses the local application target only, gates on loopback and expected database, and sets each transaction `READ ONLY` before catalog/count queries. | Ran against source and existing local scratch; both identities/revisions/table counts confirmed above. No Supabase endpoint was used. |

No broad application test suite was run because its database behavior was not established as offline; the inspected `app/database/db.py` binds normal runtime to `DATABASE_URL`. The targeted config tests and explicit self-test are the only automated checks run.

## Next safest step

Complete the Phase 7N owner checklist before provisioning: identify owner/organization/region and intended project identity, approve scope and data minimization, set a maximum monthly cost and alert boundary, approve separate auditor/migration/runtime permissions, specify asset/retention rules, name a rollback owner, and explicitly authorize provisioning. After provisioning under that later authorization, verify project identity and TLS read-only before any import. Do not use the current populated destination as staging. No provisioning, role changes, imports, migrations, asset copy, or cutover are authorized by Phase 7O.

## Tests, files, and final status

- Audit configuration tests: **14 passed**.
- Audit script missing-URL self-test: **passed without reading `.env` or connecting**.
- Backup checksum/size and `pg_restore --list`: **PASS**; current hash matches Phase 7K manifest/report; list exit 0.
- Local source/scratch identities and bounded counts: **PASS**; both remain on the expected local server/database names with 39 tables and 6,641 rows.
- No Supabase connection, credential readout, project provisioning, database write, restore, migration, or asset modification occurred.
- Intended Phase 7O edits: this report and the appended Phase 7O status section only. All initial Git changes remain preserved.
