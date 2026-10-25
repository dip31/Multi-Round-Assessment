# EDI5 Phase 7M - Credential Recovery and Destination Re-audit

- Audit date: 2026-10-25
- Scope: verify the owner-reported credential rotation by using the configured audit identity; perform fresh read-only Supabase identity, TLS, inventory, privilege, and bounded aggregate comparisons.
- Decision: **Destination identity and TLS PASS; destination restore/reuse BLOCKED.** No migration, restore, DDL/DML, role/grant change, staging project, or cutover was performed.

## Credential status and configuration separation

The owner confirmed that the exposed credential was rotated and the local audit configuration updated. Without printing or recording either credential, the audit loader confirmed both dedicated audit settings are configured. The new configured credential authenticated successfully to the expected destination route. The application `DATABASE_URL` still resolves to `localhost:5432/ai_placement_platform`; it was not changed.

The provider-side retirement of the prior password was not independently verified. This audit did not try the old password and did not inspect provider dashboard history. A successful connection with the new credential proves that the configured credential is accepted, but alone does not prove which earlier passwords are invalid. Treat the owner's rotation confirmation as the evidence for retirement; no credential values or project reference are included in this report.

## Fresh destination identity and TLS

| Check | Result | Evidence |
|---|---|---|
| Audit URL and expected project reference configured | PASS | Existing dedicated audit loader returned both settings without printing values. |
| Endpoint/project identity | PASS | Audit script verified the connected project route against the independently configured expected reference. No reference value recorded. |
| Database identity and version | PASS | Connected database `postgres`, PostgreSQL 17.11. |
| Connection mode | PASS | Session pooler. |
| Client TLS | PASS | Driver metadata confirmed TLS active; libpq used `sslmode=verify-full` and the pinned project CA, preserving hostname verification. Psycopg 3 did not expose protocol/cipher strings, so those are not claimed. |
| Read-only inspection | PASS | Audit inspection and bounded count queries ran after TLS and identity checks in explicit read-only transactions. No row values or personal data were printed. |
| Connection errors/output | PASS | Initial sandbox connection failed with a redacted network error before queries. The same read-only audit succeeded after approved network escalation. No raw connection exception or URL was emitted. |

## Fresh inventory and source comparison

The current local source identity was independently checked in a read-only transaction: `ai_placement_platform`, PostgreSQL 16.13, loopback port 5432. It has 39 public tables and 6,641 bounded-exact rows. The locally validated Phase 7K backup and scratch restore remain untouched.

| Inventory | Current source | Fresh destination | Comparison |
|---|---:|---:|---|
| Public base tables | 39 | 34 | 11 source tables absent at destination; 6 destination-only tables. |
| Public row total | 6,641 | 7,599 | Exact bounded count on each table with a 10,001-row cap; no table reached the cap. These aggregate totals differ by 958. This does not establish ownership or entity equivalence. |
| Public columns | Source catalog snapshot | Destination catalog snapshot | 125 source columns absent at destination; 104 destination-only columns; two shared column definitions differ. |
| Indexes | Source catalog snapshot | Destination catalog snapshot | 76 source index names absent at destination; 33 destination-only; shared definitions matched. |
| Constraints | Source catalog snapshot | Destination catalog snapshot | 51 source constraints absent at destination; 21 destination-only; one shared definition differs. |
| Sequences | Source catalog snapshot | Destination catalog snapshot | 11 source-only and 6 destination-only names; shared definitions matched. The audit's two metadata views report 33 versus 34 visible sequence objects; reconcile this count-method discrepancy before any migration design relies on it. |
| Extensions | Core extension inventory | Destination has four additional extensions | `pg_stat_statements`, `pgcrypto`, `supabase_vault`, and `uuid-ossp` are destination-only relative to source. |
| Routines/triggers | Source catalog snapshot | Destination catalog snapshot | Four destination-only routines and six destination-only triggers; definitions were compared but not printed. One inventory view counts 17 trigger events while the detailed snapshot counts 14 trigger objects; reconcile counting semantics before migration. |
| Alembic history | Phase 7K source revision: `add_faculty_practice_assignments` | Fresh destination revision: `47555f247a64` | Revisions differ; destination lineage is not established by this audit. |

The destination audit reports 73 non-system base tables in total across visible schemas. The script compared schema, table, column, index, constraint, sequence, extension, view, routine, trigger, and Alembic metadata without printing object definitions or record contents. Supabase-managed schemas must remain outside any generic application restore scope.

### Data and key overlap

The fresh read-only audit establishes that both databases contain application data and that their aggregate public row totals differ. A current source/destination primary-key overlap comparison did not return a usable aggregate result in this run. No current overlap count or per-table overlap claim is made. Phase 7G's 2,486 overlapping PK values across 21 tables is historical only and must not be treated as a current comparison. No key values were printed or stored in this report. Matching IDs, when found, do not establish that records are the same entity.

### Effective privileges

| Check | Fresh destination finding | Assessment |
|---|---|---|
| SELECT | 73/73 visible base tables | Sufficient for the catalog and aggregate inspection performed. |
| Write-capable table access | INSERT/UPDATE/DELETE/TRUNCATE on 69 tables | **FAIL for least-privilege audit identity.** The connection was used only for read-only transactions; the role retains write capability outside them. |
| Database/schema capabilities | CONNECT, CREATE, TEMP; schema USAGE on 8 and CREATE on 2 | Broader than an audit role needs. |
| Role attributes | Not superuser; CREATEDB, CREATEROLE, and REPLICATION are true | **FAIL for least privilege.** No role or grant was changed. |
| Sequence privileges | USAGE/SELECT/UPDATE on 33 visible sequences | Excess write-related capability for an audit role. |

Do not attempt to fix privileges in this phase. Any future role design or grant changes require separate explicit authorization and provider-aware review.

## Ownership and staging decision

Destination application data is **UNKNOWN - PRESERVE**. The fresh aggregate count and schema comparison do not establish who owns its data. No source/destination entity equivalence or current PK-overlap result was obtained. Destination-only tables, additional columns, routines, triggers, constraints, and extensions could represent application-specific or other-owner behavior. The current destination is not a safe restore, overwrite, merge, or cutover target.

Recommend a newly provisioned, isolated Supabase staging project after owner approval. Do not provision it in this phase. A separate isolated PostgreSQL instance is suitable for generic PostgreSQL checks but does not cover Supabase-specific auth, storage, extension, and pooler behavior. Required approvals before provisioning include named project/region and owner, data/asset scope, cost boundary, permitted role design, and rollback/change owner.

Before any future write, reconcile current destination ownership and per-table data/key collisions; resolve source/destination schema and Alembic drift; review extensions and provider-managed object exclusions; define asset mapping; and approve a frozen source snapshot and isolated restore-validation procedure. Phase 7K validates the October 25 backup in local scratch only; it does not authorize or establish Supabase restore compatibility.

## Checks, files, and safety boundary

- `python -m pytest -p no:cacheprovider tests/test_supabase_audit_config.py -q`: **14 passed**.
- `python -m py_compile scripts/audit_supabase_destination.py tests/test_supabase_audit_config.py app/config/settings.py`: **passed**.
- Existing `python scripts/audit_supabase_destination.py`: initial sandbox attempt failed at connection establishment with a redacted network error; after approved network escalation it verified identity/TLS, completed metadata/privilege/source-schema checks, and returned `BLOCKED` because existing destination data was estimated present.
- Supplemental read-only destination count check: **PASS**, identity/TLS reverified, 34 public tables, 7,599 rows, zero tables at the 10,001 cap, revision `47555f247a64`.
- Supplemental exact source check: **PASS**, local identity verified, 39 public tables, 6,641 rows, zero tables at the cap.
- Current exact PK-overlap comparison: **NOT VERIFIED**; the attempted supplemental aggregation yielded no usable result. No key values were reported.
- No DDL, DML, migration, restore, role/grant change, project provisioning, asset operation, application cutover, or database write was performed. The configured application target and local Phase 7K backup/scratch database were not changed.
- Phase 7M adds this report and appends the Phase 7 status report only. Existing worktree changes were preserved; no code or `.env` file was edited.

## Blockers and next approval

1. Existing destination ownership and application-data provenance remain unknown. Preserve all current destination rows and objects.
2. Configure a least-privilege read-only audit identity before future audits; the current role is broadly write-capable. Do not change grants without separate authorization.
3. Re-run current PK-overlap/entity analysis with a bounded, successfully reporting audit, and reconcile the sequence/trigger inventory counting discrepancies.
4. Obtain explicit owner approval for a named isolated staging project, region, scope, cost limit, roles, and rollback owner before provisioning or Phase 7N.

**Phase 7M decision:** fresh destination identity/TLS/read-only inspection **PASS**; destination ownership **UNKNOWN - PRESERVE**; least-privilege role check **FAIL**; safe reuse/restore/cutover **BLOCKED**. Stop here. No staging project, migration, restore, or production cutover is authorized.
