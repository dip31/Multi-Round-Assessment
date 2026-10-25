# EDI5 Phase 7L - Supabase Destination Ownership Audit and Isolated Staging Plan

- Audit date: 2026-10-25
- Scope: read-only local source/scratch verification, review of prior destination evidence, application/asset dependency inventory, and staging plan.
- Decision: **BLOCKED for a fresh Supabase audit; current destination is UNKNOWN - PRESERVE.** No migration, restore, cutover, DDL, DML, role/grant change, project provisioning, or asset copy was performed.

## Preservation and credential handling

Initial `git status --short` was:

```text
 M app/config/settings.py
 M requirements.txt
?? -
?? certs/
?? docs/audits/EDI5_PHASE_6C_3_SUPABASE_DESTINATION_AUDIT.md
?? docs/audits/EDI5_PHASE_7K_20261025_022d4117/
?? docs/audits/EDI5_PHASE_7K_SCRATCH_RESTORE_VALIDATION.md
?? docs/audits/EDI5_PHASE_7_LOCAL_TO_SUPABASE_MIGRATION_STATUS.md
?? scripts/audit_supabase_destination.py
?? tests/test_supabase_audit_config.py
```

These pre-existing changes were preserved. No files were staged, reverted, reset, cleaned, stashed, or deleted.

The audit-only URL and expected project reference were confirmed present through the audit script's `python-dotenv` loader without intentionally printing their values. A separate environment-inspection command accidentally emitted `.env` assignment lines to tool output. **The audit URL must be considered exposed and rotated before any further use.** No Supabase connection was opened in Phase 7L, and no destination query was run. This report deliberately omits the URL, user, password, token, and project reference. After rotation, verify the replacement locally and rerun the audit with output capture reviewed for secrets before considering any destination findings current.

## Phase 7K and local source verification

The Phase 7K report records a verified October 25 custom-format backup at `C:/Users/Akshada/AppData/Local/EDI5-Backups/ai_placement_platform_20261025T094836Z_phase7j_verified.dump`, 530,714 bytes, SHA-256 `466D701CAC2CA0C65B0793D7F5F4B2770BFE21C9BE88DD7C77DDD8C23418886B`. Its restore to the separately named local scratch database completed and the report records matching all 39 table counts and full-row fingerprints. The backup and scratch database were not modified in this phase.

Fresh Phase 7L read-only verification found:

| Check | Result | Evidence |
|---|---|---|
| Effective application target | PASS | Sanitized SQLAlchemy URL parse: `localhost:5432/ai_placement_platform`; no URL or credential printed. `app/database/db.py` builds the normal runtime engine from `settings.DATABASE_URL`; Alembic also reads that setting. |
| Local source connection | PASS | Read-only identity query: `ai_placement_platform`, role `postgres`, PostgreSQL 16.13, port 5432, loopback (`::1`). |
| Source inventory | PASS | Exact read-only counts: 39 public tables and 6,641 rows including Alembic metadata. |
| Phase 7K scratch | PASS | Read-only identity query: `edi5_restore_validation_20261025_022d4117`, PostgreSQL 16.13, same loopback port. Exact counts: 39 public tables and 6,641 rows. |
| Source/scratch counts | PASS | Exact table-name sets match and per-table row-count mismatch count is zero. Full-row fingerprint equivalence is historical Phase 7K evidence, not repeated in Phase 7L. |
| Application target change | PASS | No `DATABASE_URL` or `.env` edit was made. |

The approximate `pg_class.reltuples` estimate read during the local check was lower than the exact total; this is expected to be approximate and was not treated as a data discrepancy. The exact counts are the relevant comparison.

## Supabase destination and ownership

### Direct observations in Phase 7L

| Check | Result | Evidence |
|---|---|---|
| Audit-only configuration presence | PASS | Both dedicated variables were loadable through the audit script's dotenv mechanism; values are withheld. |
| Fresh destination identity/TLS/inventory/privileges | BLOCKED | Not run because the configured audit credential was exposed in command output and must be rotated first. No destination connection/query was attempted. |
| Destination ownership | BLOCKED - UNKNOWN / PRESERVE | No ownership, retention, tenant, or provenance evidence was available in Phase 7L. Do not treat any existing record or object as disposable or EDI5-owned. |

### Historical Phase 7G observations (not reverified in Phase 7L)

Phase 7G recorded the destination route as the intended Supabase project, database `postgres`, PostgreSQL 17.11, session pooler, with client TLS verified using `sslmode=verify-full` and the project CA. Its read-only inventory reported 34 public tables, 7,398 application rows in 28 populated tables, 2,486 overlapping primary-key values across 21 shared tables, 11 source-only tables, six destination-only tables (some populated), and broad write-capable privileges for the audit role. Phase 7G also recorded substantial schema/object drift. These are dated prior observations only; they are not current Phase 7L connection evidence.

**Ownership conclusion:** existing destination data must be treated as potentially production-owned and preserved. Matching primary keys do not prove entity identity. No safe replacement, append, merge, or reuse strategy for the existing destination is established.

| Dataset/object | Source evidence | Destination evidence | Ownership evidence | Risk and handling |
|---|---|---|---|---|
| Shared application tables and overlapping keys | 39 public tables; 6,641 total rows currently | Historical Phase 7G: 34 tables; 7,398 application rows; 2,486 overlapping PKs | No entity-level ownership/equivalence mapping | UNKNOWN - PRESERVE; no append/merge or key remapping until owner-authorized reconciliation. |
| Destination-only application tables/records | Not part of source snapshot | Historical Phase 7G found six destination-only tables; some populated | No provenance or retention owner established | UNKNOWN - PRESERVE; map owners and dependencies before any plan that might affect them. |
| Supabase-managed schemas and objects | Not source application scope | Historical inventory included provider schemas and extensions | Provider ownership presumed for provider-managed objects; not rechecked | Exclude from generic restore/migration scope; follow provider-supported procedures only. |
| Schema/revision/sequence/constraint differences | Phase 7K confirms source backup reproduces its local source schema/data | Historical Phase 7G reports major differences and a nonmatching Alembic revision | Not an ownership fact | High compatibility/collision risk; reconcile against a newly audited isolated target. |

## Compatibility risks carried forward

All destination-specific findings in this table are historical Phase 7G items and require revalidation against the selected staging destination.

| Risk | Status | Required resolution before writes |
|---|---|---|
| Source PostgreSQL 16.13 vs historical destination 17.11 | Historical finding; target must be reverified | Confirm server version, supported extensions, client/tool versions, and restore compatibility in isolated staging. |
| Alembic lineage mismatch; source one revision behind repository head | Confirmed for source in Phase 7K; destination revision from Phase 7G only | Select and review an explicit baseline and migration sequence; inspect generated SQL before approval. |
| `student_profiles.department` default assumption | Phase 7G found migration/live-default mismatch | Correct/review migration assumptions and validate existing rows before any DDL. |
| `refresh_tokens` absent from ORM metadata | Historical schema finding | Preserve its definition and determine application/provider ownership and semantics. |
| `coding_problems.blueprint_id` / foreign-key drift | Historical source/destination/model mismatch | Reconcile actual data and model before designing constraints or migration mapping. |
| `rl_attempt_log` foreign keys and partial unique indexes | Historical model/catalog drift | Preserve all source invariants and compare destination behavior; do not rely on ORM metadata alone. |
| Destination routines, triggers, extensions, constraints, ACLs | Historical differences; not Phase 7L reverified | Inventory in staging and review each object/privilege with owner and platform scope. |
| Runtime role and audit role permissions | Historical auditor was write capable | Design separate least-privilege read, migration, and runtime roles only under future approval. |
| PK/natural-key and sequence collisions | PK overlaps observed historically; natural-key analysis incomplete | Owner-approved pseudonymous reconciliation, unique-key checks, and sequence plan; do not infer same entity from IDs. |

## Application and external dependency inventory

- Application settings load `DATABASE_URL`; `app/database/db.py` constructs the runtime engine from it, and `alembic/env.py` supplies it to Alembic. Phase 7L confirmed the effective target remains local. Do not redirect the development application during staging work.
- API/profile and company-data code writes uploaded files to local filesystem paths and stores paths in `user_resumes.file_path` and `company_historical_data.file_path`. These paths will not automatically move with PostgreSQL rows; path portability and access control must be designed before any migration.
- Current metadata-only upload inventory: `uploads/resumes` has 87 files / 1,312,452 bytes; `uploads/company_historical` has 487 files / 5,124,636 bytes. No filenames or file contents were read or reported in this phase. Individual asset digests and row-to-file mapping remain unverified.
- `app/data/kb.index` is a separate runtime asset. Current metadata: 199,725 bytes, modified 2026-09-26 17:38:11.2872722 UTC, SHA-256 `E8070082A5CDAE71FABF13491869312324798D4F7FAD23A13B06E1AFE5B19C36`. The Phase 7I report says this matches the tracked `HEAD` blob and October 24 manifest; `scripts/build_kb_index.py` can rebuild it from knowledge-base inputs. Do not rebuild as part of this phase.
- Startup may warm models and load the KB index when heavy startup is enabled. No application process, job, migration, or API behavior was run against either database in Phase 7L.
- Review all required API secrets, auth/JWT settings, storage paths, pooler compatibility, background processes, logs, and deployment-only variables in an isolated staging deployment without exposing values. No independent scheduled worker was established by the inspected code; verify deployment configuration before staging.

## Staging options and recommendation

| Option | Assessment |
|---|---|
| New isolated Supabase staging project | **Recommended.** Strong project/database boundary; avoids cohabiting with the populated, ownership-uncertain current project. Requires owner approval, provider project provisioning, new independently rotated credentials/CA, and separate audit before writes. Cost/quota and project-region decisions are owner responsibilities. |
| Separately provisioned isolated PostgreSQL instance | Viable for restore/schema validation where Supabase-specific behavior is not required. Does not validate Supabase auth/storage/extensions/pooler behavior; needs isolated credentials, network controls, backups, and explicit lifecycle/rollback ownership. |
| Existing Supabase destination | **Not recommended / blocked.** Historical evidence shows application data, overlapping identifiers, different schema objects, and write-capable audit privileges. Coexistence cannot be proven safe without data owner identification, entity/natural-key mapping, runtime isolation, and a reviewed non-destructive design. |

Proceed with a separately provisioned staging project only after explicit project owner approval. Keep the current destination untouched and preserve it as potentially live data.

## Phased plan, rollback, and approval gates

1. **Credential containment and destination re-audit:** rotate the exposed audit credential through the authorized secret owner; update it locally, validate the expected project reference independently, and rerun the read-only audit with output redaction. Verify identity, TLS, inventory, data counts, and effective privileges before broader queries.
2. **Ownership and scope approval:** the data owner identifies existing destination datasets, retention rules, tenant/application owners, provider-managed scope, and whether any coexistence/merge is desired. Until documented, classify all destination application data UNKNOWN - PRESERVE.
3. **Isolated staging authorization:** approve a new staging project/instance, exact project identity/region, authorized auditor/migration/runtime identities, cost boundary, asset scope, and who can approve any later writes. Provisioning and credential changes are outside Phase 7L.
4. **Source freeze and recovery set:** before a later staging restore, authorize a write-freeze, create a uniquely named fresh backup and manifest, verify hashes/counts, and conduct restore validation on an isolated target. Preserve the verified Phase 7K backup and scratch database.
5. **Schema and data mapping:** approve baseline/revision, object inclusion/exclusion, conflict/key strategy, sequence handling, role/ACL design, extensions, provider-managed schema exclusions, and asset/database path mapping. Review every migration/restore command before execution.
6. **Staging validation:** only after separate written authorization, restore/migrate into the isolated stage; compare schema and bounded/exact aggregate data; validate FKs/indexes/sequences/roles/assets and run application smoke/security tests with staging-only configuration.
7. **Go/no-go and rollback:** define a named change owner, maintenance/write-freeze window, retained source and backup, tested rollback/recovery procedure, monitoring, and objective acceptance thresholds. No production cutover until explicit separate approval. Rollback must route traffic back to the retained source and preserve both source and destination evidence; do not drop either database as rollback.

### Acceptance criteria for a later staging phase

- Independently verified staging project identity and `verify-full` TLS, with an appropriately scoped role.
- Approved source snapshot/backup hashes and verified restore.
- Reviewed schema/revision plan with all identified drift accounted for and no unreviewed provider objects.
- Row-count, constraints, indexes, sequences, key-collision, and asset-mapping results meet owner-approved thresholds.
- Staging application/auth/session behavior and required external services pass documented checks.
- Rollback owner, trigger, retained artifacts, and go/no-go approver are recorded.
- No production cutover without a separate explicit authorization naming target, operations, time window, and rollback owner.

## Tests, commands, and Phase 7L Git result

Commands/checks actually executed in Phase 7L:

- `git status --short`, `git diff --cached --stat`, `git diff --stat`, and `git diff -- app/config/settings.py requirements.txt` for preservation review.
- Read-only local SQLAlchemy queries for effective target, source/scratch identities, public table counts, and exact per-table row counts. No destination database command was executed.
- Audit configuration loader presence check (printed booleans only).
- Metadata-only `Get-ChildItem`, `Get-Item`, and `Get-FileHash` for upload counts/bytes and KB-index metadata.
- `python -m pytest -p no:cacheprovider tests/test_supabase_audit_config.py -q`: **14 passed**.
- `git diff --check`: **PASS**; the only output was Git's line-ending warning for the pre-existing `requirements.txt` modification. Both report files also passed a direct trailing-whitespace scan.

Phase 7L report files are the only intended edits: this report and the appended Phase 7L section in `EDI5_PHASE_7_LOCAL_TO_SUPABASE_MIGRATION_STATUS.md`. All existing modifications/untracked artifacts remain preserved. No database-changing command, migration, restore, cutover, role/grant operation, backup change, or asset operation occurred.

## Remaining blockers and next approval

1. Rotate the audit credential that was exposed in local command output; do not reuse it. Do not send the replacement in chat.
2. With the rotated local credential, rerun and record a fresh read-only Supabase identity/TLS/inventory/privilege audit. Confirm the exact project and ownership with its data owner.
3. Obtain explicit owner approval to provision/use a named isolated staging target and define its scope/cost/roles. This is the next approval needed before Phase 7M planning or staging provisioning.
4. Resolve asset row-to-file mapping, per-file integrity, natural-key/entity identity, role/ACL parity, and schema drift before any later restore or merge.

**Phase 7L stopping decision:** no current destination ownership or safe reuse is established. Treat the existing destination as populated and **UNKNOWN - PRESERVE** based on historical Phase 7G evidence. Recommend a newly approved, isolated staging project. Stop here; no Phase 7M or destination-changing operation is authorized.
