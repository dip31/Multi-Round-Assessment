# EDI5 Phase 7P - Blocker Resolution Plan

- Assessment date: 2026-10-25
- Scope: source-only schema/model/migration inspection, source asset-reference inventory, offline test-safety review, and non-destructive blocker plans.
- Safety: no Supabase connection; no database/schema/role/credential/backup/asset changes; no cloud resource or cost incurred.

## Evidence and Git preservation

Initial Git status was recorded before inspection. Existing modified files were `app/config/settings.py` and `requirements.txt`; existing untracked artifacts included the root `-` file, certificates, Phase 6C/7 audit materials, the audit script, and audit tests. No staged changes were present. The tracked diffs were reviewed and left unchanged. This phase edits only this report and the appended section in the overall status report.

Reviewed Phase 7O, Phase 7N, Phase 7K, Phase 7M, and the overall migration status. Phase 7G/7M destination evidence is historical/current-as-of-Phase-7M; this phase did not connect to the existing Supabase destination. Its ownership remains **UNKNOWN - PRESERVE**.

## Current read-only source findings

The effective application target was checked without printing the URL. A local-only identity gate required `localhost`/loopback, port 5432, and database `ai_placement_platform` before connection. All source inspection used explicit `READ ONLY` transactions.

| Check | Status | Current evidence |
|---|---|---|
| Source identity | **COMPLETE** | `ai_placement_platform`, PostgreSQL 16.13, loopback, role `postgres`; Alembic revision `add_faculty_practice_assignments`. |
| ORM table/column coverage | **PARTIAL** | Alembic's imported model metadata contains 37 tables/388 columns; live `public` has 39 tables/395 columns. The live-only objects are `alembic_version` (Alembic-managed) and `refresh_tokens` (application schema object with no ORM mapping). All other live columns were represented in imported metadata. |
| Foreign keys | **PARTIAL** | Live source has 60 FKs; imported ORM metadata has 58. Three live-only: `refresh_tokens.user_id -> users.id`, `rl_attempt_log.question_id -> aptitude_questions.id`, and `rl_attempt_log.session_id -> assessment_sessions.id`. One ORM-only: `coding_problems.blueprint_id -> company_blueprints.id`. |
| `student_profiles.department` | **PARTIAL** | Live column is NOT NULL with no server default. ORM has Python default `Department Not Specified`, no server default. |
| `coding_problems.blueprint_id` | **PARTIAL** | Live nullable integer column exists; no FK is installed; current read-only orphan count is zero. ORM expects FK to `company_blueprints.id` with `ON DELETE SET NULL`. |
| `rl_attempt_log` | **PARTIAL** | Live source has the user, question, and session FKs. ORM currently declares only the user FK. The baseline migration creates all three. |
| `refresh_tokens` | **PARTIAL** | Present with six columns and zero rows; not in `Base.metadata`. Baseline migration creates it and an index. Application auth code currently uses JWT refresh behavior and mentions stored opaque tokens only as a future option. Empty does not mean disposable. |
| Partial unique indexes | **PARTIAL** | Live source has unique `one_active_session_per_user` on `user_id` for `status='in_progress'`, and `one_active_round_per_session` on `session_id` for `status='active'`. `add_assessment_lifecycle_timing.py` creates them; matching named partial `Index` declarations are absent from ORM code. |
| Source/repository revision | **PARTIAL** | Live source is at `add_faculty_practice_assignments`; Alembic head is `use_unspecified_student_department_default`, whose parent is the source revision. The one pending revision changes the department server default. |

The source has 151 live public indexes versus 81 ORM index names; name-only differences are not a definition comparison. The two critical partial indexes above were directly verified, but a complete predicate/definition comparison for every index was not run. The source schema query did not inspect or expose row contents.

### Smallest safe schema/migration resolutions (plans only)

| Blocker | Risk | Proposed smallest safe resolution | Verification required | Approval/access required |
|---|---|---|---|---|
| Department default assumption | The pending migration says the old server default is `Computer Science`, but the verified source has no server default. Forward and downgrade assumptions may not describe the actual starting schema. | If the revision has not been applied in any shared environment, correct its `existing_server_default` to reflect no old default and make downgrade restore no server default. If it has been distributed/applied elsewhere, do not rewrite history; create a reviewed follow-up based on each target's actual catalog. Keep the ORM Python default and database server default decision explicit. | Check every environment's revision and live column default; generate/review upgrade and downgrade SQL offline; validate default behavior in isolated staging. | Owner/change approval for migration design and later application; staging required for runtime verification. |
| `refresh_tokens` absent from metadata | Autogenerate may interpret a baseline-managed table absent from ORM metadata as an object to remove. The table is empty now, but may have retention/security significance. | Preserve the table. Add an ORM mapping for its exact six-column/FK/index definition if the application will manage it; otherwise explicitly exclude it from Alembic autogenerate as a preserved unmanaged object. Do not drop it based on zero rows. | Reconcile mapping/exclusion with baseline and live catalog; run offline metadata diff and review that no drop is emitted; obtain auth-owner decision on future use. | Auth/data-owner approval required before deciding ownership or future behavior; staging needed for application tests. |
| `coding_problems.blueprint_id` FK | Model and historical migration expect an FK, but live source lacks it. Adding constraints without checking orphans could fail or change delete behavior. | Keep the existing nullable column and index. Since current orphan count is zero and model/migration specify `ON DELETE SET NULL`, prepare a forward-only FK repair (or correct an unpublished revision); do not edit an already distributed migration. | Recheck null/orphan totals on the frozen source snapshot; verify target table and delete semantics; inspect proposed DDL and restore behavior in isolated staging. | Explicit migration approval; staging required before applying. |
| `rl_attempt_log` ORM FKs | ORM metadata understates existing source constraints; autogenerate can propose unsafe drops and model code can miss database integrity assumptions. | Align ORM with the two existing question/session FKs and their actual delete actions. No database migration is indicated if the restored target already contains the validated source constraints. | Compare source/backup FK definitions and delete actions; offline metadata comparison must show parity; application tests on staging. | Code-review approval; staging required for integration verification. |
| Partial unique indexes absent from ORM | Migration-managed unique predicates are live but not represented as named ORM indexes; autogenerate may misclassify them. | Add exact `Index` declarations to the model metadata using the verified names, columns, uniqueness, and predicates. Avoid duplicate DDL if the source/restore already has them. | Compare full catalog definitions and predicates; offline Alembic diff must preserve both; test duplicate-active-row rejection only in isolated staging. | Code review and staging approval before any write test. |
| Other index name/definition drift | 151 live index names versus 81 ORM names is too broad to classify by name alone. | Do not bulk-create/drop indexes. Reconcile definitions, predicates, validity and purpose; encode only intentional application indexes in metadata or explicit preservation rules. | Full catalog-definition comparison against verified backup and target; reviewed offline migration script. | Staging and explicit migration approval. |

## Primary-key collision analysis procedure

**Current collision status: NOT VERIFIED.** Phase 7M's current key-overlap aggregation produced no usable result. Phase 7G's 2,486 shared values across 21 tables is historical only. No destination query was run in Phase 7P.

Phase 7M observed 28 shared public table names (39 source, 34 destination; 11 source-only and 6 destination-only). Revalidate that set against a separately approved target before using it. Source key columns verified from local catalogs are:

- `id`: `admin_question_feedback`, `advanced_proctoring_events`, `approved_question_pools`, `aptitude_attempts`, `aptitude_questions`, `aptitude_topics`, `assessment_contexts`, `assessment_policies`, `assessment_rounds`, `assessment_sessions`, `coding_problems`, `coding_submissions`, `coding_test_cases`, `faculty_profiles`, `interview_sessions`, `interview_turns`, `proctoring_events`, `proctoring_violations`, `refresh_tokens`, `rl_attempt_log`, `rl_sessions`, `session_problems`, `student_profiles`, `tpo_profiles`, `user_resumes`, `users`.
- `rl_q_table`: composite key `(user_id, state, action)`.
- `alembic_version`: `version_num`; compare separately as migration metadata, not an application entity key.

Safe procedure for a later explicitly authorized read-only comparison:

1. Verify each endpoint independently (local source identity; destination/staging project identity and `verify-full` TLS) before inventory queries. Use one read-only snapshot per endpoint and record capture times/revisions.
2. Inventory table/PK column order and types independently. Compare only tables with compatible ordered key definitions; revalidate the Phase 7M table intersection instead of assuming it is unchanged.
3. Read only PK fields in bounded batches; keep raw keys in process memory and emit per-table counts, overlap counts, and caps only. Never log, save, hash to a report, or display raw identifiers.
4. Separately inspect approved natural/unique keys and FK mapping. Matching PKs alone do not prove the same person/session/entity. Any unexplained collision is **UNKNOWN - PRESERVE** and blocks append/merge.
5. Do not use the existing destination until a separate owner-approved audit authorizes its read-only access. Prefer a new isolated staging project for later restore validation.

## Role design (no role or grant changes)

| Role | Minimum intended access | Status and guardrail |
|---|---|---|
| Read-only auditor | SELECT on approved application tables and needed catalog visibility. No writes, sequence updates, CREATE, role/database/replication powers. | **BLOCKED for current destination role**: Phase 7M found write access on 69 tables and elevated role attributes. Do not remediate there in this phase or reuse this role. |
| Migration operator | Temporary, approved object/import privileges limited to the isolated staging application schema and exact reviewed operation set. | **PARTIAL**: design only. Confirm Supabase-managed role restrictions and exact grants for the owner-selected stage before writing SQL. |
| Runtime application | Only required schema usage, specific table DML, sequence usage, and required function execution. No ownership/DDL, role creation, database creation, replication, or provider-schema access. | **PARTIAL**: endpoints and table operations must be mapped from actual application flows; test with staging-only credentials. |
| Project administrator | Owner-managed human dashboard access, MFA, break-glass audit trail. | Separate from runtime/operator credentials. No project/role credentials are configured in this phase. |

Least-privilege changes require an approved isolated target and explicit owner permission; no SQL/grants are proposed here.

## External assets and database path references

Source local rows and filesystem metadata were compared read-only. File paths and filenames stayed in memory and are not recorded here.

| Asset | Code/database reference | Current source/disk aggregate | Status and risk |
|---|---|---|---|
| Resumes | `user_resumes.file_path` and `file_name`; upload code writes under `uploads/resumes` using an absolute current-working-directory path. | 41 DB rows; 41 nonempty unique absolute paths; all 41 exact paths exist and basenames match. Disk has 87 files / 1,312,452 bytes; 46 disk files are not referenced by this table's paths. | **PARTIAL**: references resolve locally, but deployment path mapping, access controls, and full asset ownership/retention are unresolved. Preserve referenced and additional files. |
| Company history uploads | `company_historical_data.file_path` and `file_name`; upload service writes under `uploads/company_historical`. | 51 DB rows: 28 `file_upload` with 28 unique nonempty absolute paths, 5 `manual`, 18 `pre_seeded`. All 28 exact paths exist and basenames match. Disk has 487 files / 5,124,636 bytes; 459 files are not referenced by these rows. | **PARTIAL**: path resolution is local only; determine ownership/retention and stage mappings. Do not infer the remaining files are disposable. |
| Knowledge-base index | No database path column/reference was found. Retriever code loads `app/data/kb.index` and `app/data/kb_metadata.json`; builder consumes `question_bank.json` and `concept_kb.json` and writes both outputs. | `kb.index` exists, 199,725 bytes, SHA-256 `E8070082A5CDAE71FABF13491869312324798D4F7FAD23A13B06E1AFE5B19C36`, matching Phase 7I evidence. | **PARTIAL**: separate application asset, not DB state. Decide controlled staging copy/build and verify the metadata/index pair; do not rebuild or copy in this phase. |

Asset path resolution requires a staging storage design: preserve source files and DB paths; create a separate verified staging copy only after approval; map DB references to the copy in an authorized staging import; verify access and checksums without deleting or moving originals. No asset operation occurred.

## Offline validation and actual results

Scripts/tests were inspected before execution. The normal `tests/conftest.py` session fixture drops and recreates a configured test database; therefore test execution used `--noconftest`. The default Supabase audit script opens a destination connection and was not run. The explicit `--self-test-config` branch uses an empty environment plus a nonexistent dotenv path and exits before connecting.

- `python -m pytest --noconftest -p no:cacheprovider tests/test_supabase_audit_config.py tests/test_db_isolation_guard.py -q`: **18 passed**. These tests use temporary files/in-memory checks and make no database connection.
- `python scripts/audit_supabase_destination.py --self-test-config`: **PASS**, detects missing audit configuration without reading `.env` or connecting.
- Read-only local source metadata/asset queries: **PASS** for the findings above; all ran after a loopback/database identity gate and `SET TRANSACTION READ ONLY`.
- Offline Alembic metadata: **PASS** for one head, source revision parent, and head parent. An initial revision-range invocation used an invalid range and returned an Alembic range error; a corrected direct revision lookup verified the parent relationship. No migration command was run.
- No default pytest harness, migration, destination audit, role operation, DDL/DML, backup write, or asset mutation was run.

## Blockers and next safe steps

1. Resolve ORM/migration drift before generating a migration script: address the department default, map or explicitly preserve `refresh_tokens`, align `coding_problems` and `rl_attempt_log` foreign keys, and encode both partial unique indexes in model metadata.
2. Review migration history distribution before editing the pending department-default revision; use a follow-up migration if it has been applied/shared.
3. Prepare the privacy-preserving PK/key comparison, but leave current destination collisions **NOT VERIFIED** until a separately authorized read-only destination audit or approved isolated target is available.
4. Keep the existing destination role unchanged. Establish distinct least-privilege auditor, temporary migration operator, runtime and human administrator identities only for an approved isolated project.
5. Obtain owner approval for project identity, data scope/retention, staging asset strategy, role model, cost boundary and rollback owner. No staging access or cost is approved by Phase 7P.

**Phase 7P decision:** local source evidence is current and the validation tests pass; collision analysis, destination-role remediation, schema compatibility and asset portability remain **PARTIAL/BLOCKED**. Existing destination remains **UNKNOWN - PRESERVE**. Stop here; no schema/data changes or cloud provisioning are authorized.
