# EDI5 Phase 7 — Local PostgreSQL to Supabase Migration Status

- **Audit date:** 2026-10-25
- **Outcome:** BLOCKED before migration; no restore or cutover performed.
- **Scope:** Verify prerequisites and backup integrity. No database was modified.

## Status by required area

| Area | Status | Evidence |
|---|---|---|
| Supabase connection and identity | BLOCKED | `EDI5_SUPABASE_AUDIT_URL` and `EDI5_SUPABASE_EXPECTED_PROJECT_REF` are absent from both `.env` and the current process environment. The replacement credential's rotation/authorization status cannot be confirmed. No destination audit connection was made. |
| Destination audit | BLOCKED | No project identity, server/TLS, inventory, data, or privilege checks were performed in this phase. |
| Backup integrity | PASS | The specified dump exists, is 530,714 bytes, and its SHA-256 matches the recorded value `CD2D23825CD8CBFE1525A3CE5985DAD46848683E59EDBCABC843D1A0C9424982`. `pg_restore --list` exited 0 and returned 438 TOC entries. No restore was run. |
| Source identity and health | BLOCKED | Current `.env` `DATABASE_URL` resolves to a Supabase pooler endpoint on port 5432 and database `postgres`, not local `ai_placement_platform`. `alembic current` attempted a connection to that configured endpoint and failed with a network permission error. Local PostgreSQL identity, reachability, and current row counts were not checked. |
| Database restore | NOT RUN | Preconditions and destination approval are not satisfied. |
| Schema validation | NOT RUN | No destination restore exists to validate. |
| Data validation | NOT RUN | No destination restore exists to validate. |
| External file availability | NOT RUN | No cutover was authorized or performed. |
| Application cutover | NOT RUN | `DATABASE_URL` was not modified during this phase. It was already configured to the Supabase pooler when inspected. |
| Backend/frontend tests | NOT RUN | No cutover took place; destructive or production-like database tests were not run. |
| Git working tree | PASS | Initial status preserved the existing modified `requirements.txt` and untracked Phase 6C.4 report/script/test. Final status adds this report and no other files. |

## Blockers and next step

The required source-of-truth condition is unmet because the application's configured `DATABASE_URL` currently targets Supabase rather than the local `ai_placement_platform` database. The required audit-only connection and independent expected project reference are also absent, so destination identity and existing data remain unknown. The prior audit credential was reported as exposed and must not be reused; its replacement's status is unverified.

Do not restore or change configuration based on the current state. First establish the intended local source connection and independently authorized, rotated audit credential/project reference through the approved local secret configuration. Then rerun the read-only destination audit and source checks. If the destination contains data, prepare a restore plan and obtain explicit approval before any replacement or restore operation.

## Actions not taken

No `DATABASE_URL` change, migration, role/grant change, DDL/DML, restore, backup overwrite/deletion, source deletion, cutover, or application test against Supabase was performed.

## Phase 7A — Configuration recovery (2026-10-25)

| Check | Result | Evidence |
|---|---|---|
| Initial worktree status | PASS | Existing `requirements.txt` modification and untracked reports/script/test were preserved. |
| Current `.env` target | PASS | Sanitized parse resolves to Supabase pooler, database `postgres`, port 5432. |
| `DATABASE_URL` process override | PASS | No process-level `DATABASE_URL` is set. Pydantic effective settings resolve to the same target as the repository-root `.env`. |
| Cause of current target | PASS | The `.env` file loaded from the project root contains the pooler target. The app uses `env_file='.env'`; no process override was found. `.env` is ignored by Git, so its prior contents/change history and who changed it cannot be established from this worktree. |
| Existing local credential recovery | BLOCKED | No local PostgreSQL URL was found in available configuration beyond tracked placeholders/defaults. No Windows `pgpass.conf`, `.pg_service.conf`, process `PGPASSWORD`, or process `DATABASE_URL` is present. Credentials cannot be safely reconstructed. |
| Local source identity query | NOT RUN | No known local credential/configuration is available, and the current application URL targets Supabase. No local database connection was attempted. |
| Audit-only configuration | BLOCKED | `EDI5_SUPABASE_AUDIT_URL` and `EDI5_SUPABASE_EXPECTED_PROJECT_REF` are absent from `.env` and the process environment. The audit script safely returned `BLOCKED: EDI5_SUPABASE_AUDIT_URL is not configured` before connecting. |
| Destination read-only audit | NOT RUN | Required audit URL and expected identity are absent; no Supabase connection was made. |
| Git working tree | PASS | Final status preserves all preexisting files and adds/updates only this audit report. |

No `.env` or application setting was changed. To proceed, configure the verified local PostgreSQL URL using its actual existing credential, and configure the rotated audit URL plus the intended 20-character project reference through local secret configuration. Then rerun source identity and destination read-only checks. Do not continue to restore or cutover until both checks pass.

## Phase 7B — Access recovery check (2026-10-25)

### Source status: BLOCKED

The documented local connection target is PostgreSQL at `localhost:5432`, database `ai_placement_platform`. `docs/DATABASE_WORKFLOW.md` uses `postgres` as the local `pg_dump`/`pg_restore` username and describes the password as the one from `DATABASE_URL`; `.env.example` contains only a sample URL with placeholder credentials. No actual local password or known-good local URL is available from the inspected configuration. The PostgreSQL administrator must provide or restore the existing authorized local connection credential (and confirm the user if it differs from the documented `postgres` account). No source identity query was attempted and no configuration was changed.

### Destination status: BLOCKED

Both `EDI5_SUPABASE_AUDIT_URL` and `EDI5_SUPABASE_EXPECTED_PROJECT_REF` are now present in `.env` (values withheld). The documented invocation, `python scripts/audit_supabase_destination.py`, was run. It safely stopped before connecting because the expected project reference does not satisfy the script's required 20-character lowercase alphanumeric format. No destination identity, TLS, inventory, data, or privilege query ran. Correct the expected project reference locally and confirm the audit credential has been rotated before rerunning.

### Phase 7B safety and worktree

No `.env` edits, password resets, PostgreSQL authentication changes, database connections, migrations, restore, role/grant changes, DDL, or DML occurred. The final `git status --short` retains all previously modified/untracked files and includes only this report update from Phase 7B.

## Phase 7C — Read-only source and destination verification (2026-10-25)

| Area | Status | Evidence |
|---|---|---|
| Initial Git state | PASS | Existing modified/untracked files were preserved. `.env` is ignored by Git. |
| Required configuration | PASS | `DATABASE_URL`, `EDI5_SUPABASE_AUDIT_URL`, and `EDI5_SUPABASE_EXPECTED_PROJECT_REF` are present in `.env`. The expected project reference passes the audit script's 20-character lowercase alphanumeric format check. No values are recorded here. |
| Application settings load | FAIL | Importing `app.config.settings` raises Pydantic `ValidationError` because `EDI5_SUPABASE_AUDIT_URL` and `EDI5_SUPABASE_EXPECTED_PROJECT_REF` are rejected as extra dotenv fields. Thus the app settings object could not be used to verify runtime configuration. Direct safe parsing confirms `.env` `DATABASE_URL` targets `localhost:5432/ai_placement_platform`; no process-level `DATABASE_URL` override is set. |
| Local PostgreSQL source | COMPLETE | A `DATABASE_URL`-only connection was opened in a read-only transaction. Identity query returned database `ai_placement_platform`, role `postgres`, loopback server address `::1/128`, port `5432`, PostgreSQL `16.13` (64-bit). All expected source identity fields matched. |
| Supabase connection / identity | PARTIAL | The audit script connected and passed its pre-inventory identity gates for database `postgres` and expected project reference routing. This confirms the configured destination route, but the audit did not complete. |
| Supabase TLS | BLOCKED | The script's active-connection TLS check against `pg_stat_ssl` could not verify TLS. Per the audit's stop condition, it exited before schema/table/data/privilege inspection. No TLS success is claimed. |
| Supabase inventory, rows, objects, privileges | NOT VERIFIED | No inventory or aggregate row count query ran after the TLS check failed. Indexes, constraints, foreign keys, sequences, extensions, functions, and triggers were not checked. |
| Backup | COMPLETE | Rechecked the specified dump: exists, 530,714 bytes, SHA-256 matches recorded checksum, and `pg_restore --list` exits 0 with 438 TOC entries. It predates this audit and is not claimed to include later source writes. No restore occurred. |
| Tests | COMPLETE | `python -m pytest -p no:cacheprovider tests/test_supabase_audit_config.py -q`: 4 passed. |
| Migration / restore / cutover | NOT RUN | No migration, restore, schema/data modification, or cutover occurred. |
| Final Git state | PASS | Existing changes remain. This Phase 7 report was updated; no other files were modified in Phase 7C. |

### Phase 7C next safe step

Resolve why the destination audit connection's active TLS state is not visible to the script, and rerun only after TLS can be positively verified. Also resolve the Pydantic extra-field configuration failure before attempting application startup. Do not infer destination contents or proceed to restore/cutover until the destination audit completes and any existing data has been reviewed and an approved restore plan exists.

## Phase 7D — Audit configuration and TLS hardening (2026-10-25)

| Area | Status | Evidence |
|---|---|---|
| Pydantic root cause | COMPLETE | `Settings` loads the repository `.env` and Pydantic's default extra-field policy rejected the two audit-only keys. |
| Pydantic correction | COMPLETE | `Settings.model_config` now sets `extra='ignore'`. Audit variables remain absent from the application model; `app.config.settings` imports successfully and still resolves `DATABASE_URL` to local `localhost:5432/ai_placement_platform`. No `.env` values changed. |
| Audit configuration separation | COMPLETE | `scripts/audit_supabase_destination.py` continues to read audit URL/project reference directly through process environment / `python-dotenv`, independent of application `Settings`. Tests prove this works when a strict app settings model would reject those dotenv keys. Missing and malformed project references are rejected. |
| TLS method | COMPLETE (implementation) | The audit now strengthens its connection URL to `sslmode=verify-full` and verifies client-side libpq/psycopg connection metadata (`ssl_in_use`, TLS protocol, cipher). A CA and hostname must validate before any SQL inspection. It no longer relies on `pg_stat_ssl` for the client-facing pooler leg. |
| TLS readiness/evidence | BLOCKED | No `sslrootcert=system` configuration, explicit `sslrootcert`/`PGSSLROOTCERT` certificate path, or default PostgreSQL `root.crt` file is available. The invocation stopped at this preflight before opening a destination connection. Therefore TLS is **NOT VERIFIED** and no destination inventory queries were run. |
| Prior `pg_stat_ssl` limitation | PARTIAL / INFERRED | PostgreSQL documents `pg_stat_ssl` per backend connection. Supabase documents separate client-to-pooler and pooler-to-Postgres legs. Therefore a server-side `pg_stat_ssl` row may not establish the client-to-pooler TLS state; this is an inference from those connection layers, not a verified diagnosis of the prior empty/false result. See [PostgreSQL `pg_stat_ssl`](https://www.postgresql.org/docs/current/monitoring-stats.html) and [Supabase connection modes and SSL](https://supabase.com/docs/guides/database/connecting-to-postgres). |
| Destination identity, inventory, rows, objects, privileges | NOT VERIFIED | The stricter TLS preflight blocked connection. Schema/table inventory, approximate row estimates, indexes, constraints, foreign keys, sequences, extensions, functions, triggers, and privileges were not queried. |
| Tests | COMPLETE | `python -m pytest -p no:cacheprovider tests/test_supabase_audit_config.py -q`: 11 passed. `py_compile` passed for `app/config/settings.py` and `scripts/audit_supabase_destination.py`. Effective app settings were inspected safely and resolve to the local source. |
| Database changes / migration | NOT RUN | No destination connection was opened in Phase 7D; no database was modified. No migration, restore, DDL, DML, or cutover occurred. |

### Phase 7D next safe step

Obtain the Supabase project CA certificate from its authorized dashboard and make it available to libpq through a trusted local certificate path (or approved system trust configuration). Then rerun the existing audit, which requires `verify-full` and checks client TLS metadata before read-only inventory queries. Do not change the TLS mode to `require`, `prefer`, or another weaker setting. Destination data and permissions remain unknown; no restore plan is approved.

## Phase 7E — CA file verification (2026-10-25)

| Check | Status | Evidence |
|---|---|---|
| Certificate file | COMPLETE | The requested repository path exists, is readable, and is 1,367 bytes. |
| PEM and CA structure | COMPLETE | Python cryptography parsed one PEM X.509 certificate; BasicConstraints `CA=True`, KeyUsage `keyCertSign=True`, and the self-signature verified. |
| Certificate metadata | COMPLETE | Subject and issuer are both `CN=Supabase Root 2021 CA, O=Supabase Inc, L=New Castle, ST=Delware, C=US`; validity is 2021-04-28 10:56:53 UTC through 2031-04-26 10:56:53 UTC; it is currently within validity. SHA-256 fingerprint: `807025ad50d4ed219d2c9c7d299c004f824eb00cf7f65afef607d07b72e6cafa`. |
| Official provenance / trust | BLOCKED | Metadata is consistent with the documented Supabase CA name, but it does not prove where this local file came from. Official [Supabase SSL documentation](https://supabase.com/docs/guides/platform/ssl-enforcement) says to obtain the CA from the project's Database Settings dashboard and use it with `verify-full`; it does not publish a fingerprint for independent comparison. No authorized dashboard certificate source was available in this phase. The file's Supabase origin and suitability therefore remain unverified. |
| Audit configuration or connection | NOT RUN | The certificate was not added to the connection configuration, and no destination connection was attempted because its provenance could not be confirmed. No TLS, identity, inventory, data, or privilege results are claimed. |
| Tests / compilation | NOT RUN | The Phase 7E certificate trust precondition failed, so no new audit run or test suite was started. Phase 7D test results remain historical. |
| Database changes | COMPLETE | No database was contacted or changed; no migration, restore, DDL, DML, role change, or cutover occurred. |

### Phase 7E next safe step

Verify the certificate fingerprint against the certificate downloaded from the authorized Supabase project's Database Settings, or provide an authenticated certificate source. Do not configure this file as a trust anchor until that comparison succeeds. The destination audit remains blocked; no destination contents or privileges are verified.

## Phase 7F — Verified CA, TLS, and read-only destination audit (2026-10-25)

### Certificate provenance and TLS

| Check | Status | Evidence |
|---|---|---|
| CA provenance | VERIFIED | `certs/supabase-project-ca.crt` is 1,367 bytes and readable. Its Windows `Zone.Identifier` records the Supabase downloads object `/prod/ssl/prod-ca-2021.crt` on `supabase-downloads.s3-ap-southeast-1.amazonaws.com`, with `supabase.com` as referrer host. The official [Supabase SSL documentation](https://supabase.com/docs/guides/platform/ssl-enforcement) states that the database CA is downloaded in Database Settings and identifies the asset as `prod-ca-2021.crt`. The saved asset metadata corroborates the reported dashboard origin. |
| Certificate structure and validity | COMPLETE | Valid PEM X.509 certificate; self-signature valid; BasicConstraints `CA=True`; KeyUsage `keyCertSign=True`; subject and issuer are `CN=Supabase Root 2021 CA, O=Supabase Inc, L=New Castle, ST=Delware, C=US`; valid 2021-04-28 10:56:53 UTC through 2031-04-26 10:56:53 UTC and currently within validity. SHA-256: `807025ad50d4ed219d2c9c7d299c004f824eb00cf7f65afef607d07b72e6cafa`. |
| TLS configuration | PASS | The audit pins `sslrootcert` to the verified certificate path and sets `sslmode=verify-full`, preserving the configured hostname. The active Psycopg 3/libpq connection metadata confirmed `ssl_in_use=True`, `sslmode=verify-full`, and the exact CA path. The verified handshake confirms certificate-chain and hostname validation. Psycopg 3 exposes the active SSL boolean here, but not protocol/cipher attributes; those are marked not exposed rather than inferred. |
| Destination identity | VERIFIED | Session pooler route's project reference matched `EDI5_SUPABASE_EXPECTED_PROJECT_REF`; connected database is `postgres`; server version is PostgreSQL 17.11. |

### Read-only inventory and source comparison

The audit ran in a PostgreSQL read-only transaction. Table row estimates use `pg_class.reltuples`, are approximate, and are not exact counts.

| Finding | Result |
|---|---|
| Schemas / base tables | 8 schemas; 73 base tables total, 34 in `public`. |
| Estimated data | 20 tables have nonzero estimates across all schemas; 17 are in `public`. Existing data is present; exact row counts were not run. |
| Database objects | 807 columns; 247 indexes, all marked valid; 242 constraints (77 FKs, 73 PKs, 23 unique, 69 checks); 33 sequences visible in `information_schema` and 34 in the catalog snapshot; 3 views; 17 trigger events (14 unique trigger names in the catalog snapshot); 104 routines; 5 extensions. |
| Extensions | `pg_stat_statements`, `pgcrypto`, `plpgsql`, `supabase_vault`, `uuid-ossp`. Four are destination-only relative to local. |
| Privileges | CONNECT/CREATE/TEMP and usage on all 8 schemas; CREATE on 2 schemas; SELECT on 73/73 tables; INSERT/UPDATE/DELETE/TRUNCATE on 69/73 tables; USAGE/SELECT/UPDATE on 33/33 visible sequences. Current role is `postgres`, not superuser, but has `CREATEDB`, `CREATEROLE`, and `REPLICATION` attributes. |
| Public table comparison | 11 local tables missing in destination; 6 destination-only; no table-definition differences. Missing examples include `aptitude_round_questions`, `company_blueprints`, `company_historical_data`, `competency_evidence_mappings`, and `faculty_practice_assignments`. Destination-only examples include `competency_evidence`, `dynamic_interviewers`, and interview support tables. |
| Public columns | 125 local columns missing in destination; 104 destination-only; 2 shared columns differ in type/default/nullability metadata: `advanced_proctoring_events.event_metadata`, `interview_sessions.rl_state`. |
| Public indexes | 76 local indexes missing in destination; 33 destination-only; no differing definitions among shared names. Full definitions and partial predicates were compared in memory and not printed. |
| Public constraints | 51 local constraints missing in destination; 21 destination-only; one shared definition differs (`users_role_check`). |
| Public sequences | 11 local sequences missing in destination; 6 destination-only; no differing definitions among shared names. Ownership and sequence parameters were compared. |
| Other public objects | No public view differences; 4 destination-only routines and 6 destination-only triggers. Four Supabase/provider extensions are destination-only. |
| Alembic revision | Local source reports `add_faculty_practice_assignments`; destination reports `47555f247a64`. Revisions differ. |

The role can write to most destination tables and has role-creation/database-creation attributes, so it is more privileged than a read-only audit identity should be. The audit transaction itself was read-only. No grants were changed.

### Tests, changes, and safety

| Check | Status | Evidence |
|---|---|---|
| Audit configuration and certificate tests | PASS | `python -m pytest -p no:cacheprovider tests/test_supabase_audit_config.py -q`: 14 passed. Tests cover missing/malformed configuration, Pydantic separation, CA path, invalid/missing certificates, and safe TLS metadata failures. |
| Python compilation | PASS | `py_compile` passed for the audit script, its tests, and app settings. |
| Diff whitespace check | PASS | `git diff --check` completed; Git emitted only the pre-existing `requirements.txt` line-ending warning. |
| Files changed in Phase 7F | — | `scripts/audit_supabase_destination.py`, `tests/test_supabase_audit_config.py`, and this report. `certs/` was present as untracked before Phase 7F and was not modified. Pre-existing changes to `app/config/settings.py`, `requirements.txt`, and the Phase 6C.3 report were preserved. |
| Database writes / migration | NOT RUN | No DDL, DML, role/grant change, migration, restore, cutover, or backup modification occurred. |

### Phase 7F decision and next safe step

The destination audit is **COMPLETE**, but the destination is not a safe restore target as-is. It contains existing estimated data, has substantial public schema differences from the local source, and has a different Alembic revision. Do not restore, overwrite, merge, or cut over. Review these findings and prepare a separate staging/replacement plan; explicit approval is required before any destination write.

## Phase 7G — Read-only source/destination reconciliation and migration plan (2026-10-25)

### Identity and method

| Check | Result | Evidence |
|---|---|---|
| Local source | PASS | `DATABASE_URL` connected to `ai_placement_platform` on loopback port 5432 as role `postgres`; PostgreSQL 16.13. No configuration was changed. |
| Supabase destination | PASS | Independent audit URL and expected project reference were present; project routing matched, database was `postgres`, role `postgres`, PostgreSQL 17.11, session pooler. Client TLS metadata confirmed TLS with `sslmode=verify-full` and the pinned CA. The reference and connection URL are omitted. |
| Inspection safety | PASS | Destination metadata and bounded count queries ran in `SET TRANSACTION READ ONLY` transactions, after destination TLS and identity checks. PK values used for overlap comparison stayed in process memory; no identifiers or record fields were printed or written. The audit role itself has write-capable privileges, recorded below; no write statement was issued. |
| Effective destination privileges | RISK | SELECT on 73/73 tables; INSERT/UPDATE/DELETE/TRUNCATE on 69/73; CONNECT/CREATE/TEMP; USAGE on all 8 schemas and CREATE on 2; EXECUTE on 4/4 public functions. Role `postgres` is not superuser but has CREATEDB, CREATEROLE, and REPLICATION. This is broader than an audit identity needs. No privileges were changed. |

### Schema reconciliation

The live source has 39 public base tables and the destination has 34. Names below were compared from both live catalogs. Classification describes the migration risk, not an authorization to make changes.

| Object | Source state | Destination state | Classification | Risk / evidence |
|---|---|---|---|---|
| Public tables | 39 tables | 34 tables | CONFLICTING | 11 source-only: `aptitude_round_questions`, `company_blueprints`, `company_historical_data`, `company_patterns`, `competency_evidence_mappings`, `faculty_practice_assessment_rounds`, `faculty_practice_assessments`, `faculty_practice_assignments`, `faculty_practice_round_attempts`, `generated_question_pools`, `mock_drives`. Six destination-only: `competency_evidence`, `dynamic_interviewers`, `interview_conversations`, `interview_messages`, `interview_question_analysis`, `student_competencies`. Some destination-only tables contain rows. A replacement or merge can lose or misassociate data. |
| Columns | Comparison across public tables | Comparison across public tables | CONFLICTING | 125 source columns absent at destination, 104 destination-only, and two shared definitions differ (`advanced_proctoring_events.event_metadata`, `interview_sessions.rl_state`). The differences may affect application behavior or restoration. |
| Indexes | 76 names absent at destination | 33 destination-only | CONFLICTING | No definition differences among shared names. `one_active_session_per_user` is a valid partial unique index in both; `one_active_round_per_session` is present and valid on source but absent on destination. |
| Constraints | 51 names absent at destination | 21 destination-only | CONFLICTING | One shared definition differs (`users_role_check`). Missing destination constraints could fail on existing rows or permit behavior the source prevents. |
| Sequences | 11 names absent at destination | 6 destination-only | CONFLICTING | Shared-name definitions match; ownership/parameters were inspected. Sequence state and ID alignment remain a collision risk. |
| Views | Same public inventory/definitions | Same | COMPATIBLE | No public view differences detected. |
| Routines and triggers | Four fewer public routines and six fewer public triggers | Four destination-only routines and six destination-only triggers | CONFLICTING | Destination behavior includes objects absent from the source. The audit compared definitions without printing them. |
| Extensions | Core `plpgsql` shared | Four additional destination extensions | NEEDS INVESTIGATION | Destination has `pg_stat_statements`, `pgcrypto`, `supabase_vault`, and `uuid-ossp`; availability/ownership and restore behavior need an explicit decision. |
| Other schemas | Application source scope is `public` | Supabase also has `auth`, `extensions`, `graphql`, `graphql_public`, `realtime`, `storage`, and `vault` | POTENTIALLY DESTRUCTIVE | Provider-managed schemas and contents must be excluded from any application restore plan unless Supabase explicitly documents otherwise. `storage.objects` and `storage.buckets` each had bounded exact count 0. |

### Data inventory and collision indicators

Bounded count query: count rows from a subquery limited to 10,001 rows per table. Every reported public application table was below the cap, so these counts are exact for this audit. `alembic_version` is excluded from application-row totals and contains the revision recorded below.

| Endpoint | Exact aggregate | Populated public application tables (table=count) |
|---|---:|---|
| Local source | 6,640 rows in 34 tables | `advanced_proctoring_events=425`, `approved_question_pools=56`, `aptitude_attempts=263`, `aptitude_questions=905`, `aptitude_round_questions=360`, `aptitude_topics=75`, `assessment_contexts=183`, `assessment_policies=245`, `assessment_rounds=562`, `assessment_sessions=365`, `coding_problems=180`, `coding_submissions=9`, `coding_test_cases=418`, `company_blueprints=45`, `company_historical_data=51`, `company_patterns=70`, `competency_evidence_mappings=52`, `faculty_practice_assessment_rounds=9`, `faculty_practice_assessments=3`, `faculty_practice_assignments=8`, `faculty_practice_round_attempts=1`, `faculty_profiles=31`, `generated_question_pools=64`, `interview_sessions=20`, `interview_turns=9`, `mock_drives=104`, `rl_attempt_log=263`, `rl_q_table=169`, `rl_sessions=263`, `session_problems=224`, `student_profiles=474`, `tpo_profiles=93`, `user_resumes=41`, `users=600`. |
| Supabase destination | 7,398 rows in 28 tables | `advanced_proctoring_events=2007`, `approved_question_pools=143`, `aptitude_attempts=763`, `aptitude_questions=63`, `aptitude_topics=10`, `assessment_contexts=120`, `assessment_policies=24`, `assessment_rounds=521`, `assessment_sessions=365`, `coding_problems=12`, `coding_submissions=26`, `coding_test_cases=69`, `faculty_profiles=1`, `interview_conversations=20`, `interview_messages=99`, `interview_question_analysis=11`, `interview_sessions=83`, `interview_turns=11`, `proctoring_events=317`, `rl_attempt_log=762`, `rl_q_table=453`, `rl_sessions=583`, `session_problems=321`, `student_competencies=30`, `student_profiles=269`, `tpo_profiles=2`, `user_resumes=7`, `users=306`. |

The other five destination public tables were exactly empty in the bounded check: `admin_question_feedback`, `competency_evidence`, `dynamic_interviewers`, `proctoring_violations`, and `refresh_tokens`. The destination `alembic_version` row exists even though its old `reltuples` estimate was zero. Managed-schema estimates from the inventory also show migration metadata in `auth`, `realtime`, and `storage`; those schemas were not treated as application data.

| Collision / integrity check | Result | Classification and limitation |
|---|---|---|
| Primary-key overlap | Exact comparison for 27 shared public tables with compatible PK columns; all row samples were below the 10,001 cap. 21 tables had 2,486 matching PK values in total. | CONFLICTING. This is key equality only; it does not prove that the rows are the same entities. Highest visible overlaps include `users` 202, `assessment_rounds` 377, `assessment_sessions` 189, `aptitude_attempts` 263, and `rl_attempt_log` 263. A blind append can violate primary keys or attach records to the wrong entity. |
| `student_profiles.department` | Both databases: `varchar`, NOT NULL, no server default; null count 0. | CONFLICTING / NEEDS INVESTIGATION. The pending migration declares the existing default as `Computer Science` and changes it to `Department Not Specified`, while neither live column has a server default. ORM Python default is `Department Not Specified`. Do not apply without correcting and reviewing migration assumptions. |
| `refresh_tokens` | Present on both databases; exact count 0 on both; table is not represented in ORM metadata. | UNKNOWN / NEEDS INVESTIGATION. Preserve and reconcile the table definition deliberately; absence of rows does not establish that it is unnecessary. |
| `coding_problems.blueprint_id` | Source: nullable integer column and index, no FK to `company_blueprints`; aggregate orphan count 0. Destination: column and related index are absent. Both retain the `created_by` FK. | CONFLICTING. Destination cannot represent source blueprint associations. ORM declares the FK, but Phase E found the live source FK absent. |
| `rl_attempt_log` FKs | Both databases have validated FKs for `user_id`, `question_id`, and `session_id`; zero unvalidated public FKs on either database. ORM declares only `user_id`. | CONFLICTING model/live metadata drift. Keep the two live FKs in any migration plan; model metadata alone is not a safe schema specification. |
| Unique keys and natural identifiers | Per-database PK/unique constraints and indexes were inventoried; cross-database natural-key matches (including non-PK unique keys) were not queried. | UNKNOWN. Entity ownership and collisions on unique keys must be resolved without exposing personal data before any merge. |
| FK orphan / null checks | Public FK constraints are validated on both endpoints. The source's unconstrained `coding_problems.blueprint_id` has zero orphan references; department null counts are zero. Other per-table orphan and critical-FK null aggregates were not run. | PARTIAL. Do not claim a complete data-quality reconciliation. |

### Alembic and compatibility

| Item | Finding | Classification |
|---|---|---|
| Current live revisions | Source `add_faculty_practice_assignments`; destination `47555f247a64`. | CONFLICTING. Destination revision is not a matching source revision and was not found among the repository revision IDs. |
| Repository head | `use_unspecified_student_department_default`, whose parent is `add_faculty_practice_assignments`. | Source is one repository migration behind; destination revision lineage is unknown. No migration was run. |
| Pending migration assumptions | `add_faculty_practice_assignments` adds four source-only tables already present on the live source. `use_unspecified_student_department_default` assumes a prior server default of `Computer Science`; current source metadata shows no default. | POTENTIALLY DESTRUCTIVE / NEEDS INVESTIGATION. Review migration graph and generated DDL against both live catalogs; do not autogenerate or apply blindly. |
| PostgreSQL versions / archive | Source is 16.13; destination is 17.11. The existing manifest records a PostgreSQL 16 custom-format dump; installed `pg_restore` is 16.13 and `--list` succeeded (407 output lines, 35 `TABLE DATA` entries). | Version direction is suitable in principle for logical dump into a newer PostgreSQL server, but this does not validate Supabase-specific objects, roles, extensions, or successful restoration. PostgreSQL documents that dump output is expected to load into newer servers and recommends using current dump tools for cross-version transfers ([pg_dump documentation](https://www.postgresql.org/docs/16/app-pgdump.html)). |

### Backup and asset implications

- The backup manifest records 2026-10-10, source revision `add_competency_mapping_status_4g`, 4,978 rows, and prior restore validation at that point. Live source now has 6,640 application rows and revision `add_faculty_practice_assignments`; therefore that backup is stale for a current-source migration. A fresh backup after an agreed write freeze and a new isolated restore validation would be required.
- The current dump at the manifest path is 373,132 bytes with SHA-256 `92C5CBACB062BE12DF6B6C09C7AB895B6E98CDB3AEBE79F48C553E852BAA3705`; `pg_restore --list` passed. The earlier Phase 7 status section records 530,714 bytes and a different hash for the specified dump. This audit did not alter the backup; reconcile that documentation/artifact discrepancy before relying on it.
- Local ignored asset directories contain 87 resume files (1,312,452 bytes) and 487 company historical-upload files (5,124,636 bytes). Source rows include 41 `user_resumes` and 51 `company_historical_data`; destination has 7 `user_resumes`, no `company_historical_data` table, and zero objects/buckets in Supabase Storage. File-to-row mappings were not opened. These files require a separate access-controlled asset migration and integrity plan; no asset was changed.
- `app/data` has `question_bank.json`, `concept_kb.json`, `kb.index`, and `kb_metadata.json`, dated 2026-09-26. The index is an application asset, not database state; deployment must either carry a verified compatible copy or rebuild it from approved source documents. No index rebuild or file modification occurred.

### Strategy, prerequisites, and approval gate

**Recommendation: BLOCKED on data ownership; prefer a newly provisioned isolated Supabase project for staging.** A clean, separately provisioned destination avoids colliding with 7,398 existing destination rows, the 2,486 overlapping primary-key values, destination-only entities, and provider-managed schemas. The current Supabase project must be treated as data that may belong to production until its owner confirms otherwise. A preservation/merge alternative remains possible only after an entity-level reconciliation, ownership decision, natural-key collision analysis, and mapping plan; current evidence is insufficient to call that safe.

Prerequisites before any database write:

1. The data owner identifies the purpose and retention authority for existing destination records and chooses either a separate staging project or a documented preservation/merge plan.
2. The owner approves the exact destination project/database, schema scope, asset scope, write window, and rollback/recovery plan. Provider-managed schemas are explicitly excluded.
3. Review and correct the pending migration's department-default assumption; reconcile ORM/live drift for `coding_problems.blueprint_id`, `rl_attempt_log`, and partial indexes; account for destination-only objects and extensions.
4. Resolve the current backup hash/size discrepancy; after a write freeze, produce a fresh source backup and manifest, verify its hash and archive listing, and restore it only to a separately approved disposable validation database. Validate source-to-backup counts and schema before destination work.
5. Decide how to preserve or migrate resume/company-upload files and the knowledge-base index, with access controls and checksums; map database file references without exposing personal contents.
6. Before DDL, DML, restore, role/grant work, or cutover, obtain explicit approval naming the selected project, exact operation set, timing, and rollback owner. None of those actions is approved by Phase 7G.

Alternatives assessed: (A) isolated newly provisioned destination — safer and recommended for staging, but project provisioning is not performed here; (B) preserve/reconcile the populated destination — currently blocked because data ownership and natural-key/entity equivalence are unknown, and schema/revision drift is substantial.

### Queries, tests, Git state, and safety

| Check | Result |
|---|---|
| Secure destination audit | PASS for connection identity, PostgreSQL version, session-pooler mode, verify-full TLS, schema/object inventory, and effective privileges; existing data is a restore blocker. |
| Source/destination identity and schema queries | PASS; each connection used a read-only transaction; destination TLS/identity gates passed before inspection. |
| Bounded public table counts | PASS; max 10,001 rows per table; all returned counts were below the cap and exact. No record contents were printed. |
| PK overlap / named drift / storage checks | PASS as described above; primary-key values were compared only in memory and aggregate overlaps reported. |
| Audit tests | PASS: `python -m pytest -p no:cacheprovider tests/test_supabase_audit_config.py -q` — 14 passed (configuration/TLS test suite; no DB writes). |
| Changes during Phase 7G | Only this report section was appended. No scripts, tests, `.env`, `DATABASE_URL`, certificates, backups, local assets, or database objects/records were changed. Initial and final Git statuses retain the same modified `app/config/settings.py`, `requirements.txt`, and untracked `certs/`, audit reports, audit script, and audit tests. |
| Database-changing operations | NOT RUN: no DDL, DML, migrations, restores, cutover, grants, role changes, cleanup, or writes. |

**Phase 7G decision: BLOCKED pending human review.** Do not restore, merge, overwrite, or cut over. Reconcile data ownership, backup identity, schema/migration drift, natural-key collisions, and external assets first. Wait for explicit approval before any database-changing phase.

## Phase 7H — Backup integrity reconciliation and isolated staging readiness (2026-10-25)

### Backup artifact identity and report discrepancy

| Artifact / check | Verified result | Assessment |
|---|---|---|
| Candidate 2026-10-24 dump | `C:\Users\Akshada\AppData\Local\EDI5-Backups\ai_placement_platform_20261024T192924Z.dump`; size 530,714 bytes; modified 2026-10-24 19:29:26.6039251 UTC; SHA-256 `CD2D23825CD8CBFE1525A3CE5985DAD46848683E59EDBCABC843D1A0C9424982`. | Identity matches the size/hash reported in the earlier Phase 7 status. The artifact was read only and left untouched. |
| Candidate manifest | Sibling `.manifest.json`; size 350,302 bytes; modified 2026-10-24 19:32:28.5058938 UTC; manifest creation time 2026-10-24 19:32:28.4115515 UTC. It records PostgreSQL custom format, 530,714 bytes, the matching SHA-256, and `pg_dump` / `pg_restore --list` exit code 0. | PASS for artifact checksum/manifest agreement. Manifest reports source `ai_placement_platform`, PostgreSQL 16.13, revision `add_faculty_practice_assignments`. It records five expected objects (Alembic version plus the four faculty-practice tables), each marked present. |
| Candidate archive listing | PostgreSQL 16.13 `pg_restore --list` exited 0. Header says 442 TOC entries; the listing contains 438 numbered entries (the same 438 reported earlier) and 39 `TABLE DATA` entries. All 39 table-data names match the current source's 39 public base tables; no missing or extra names. Format is custom/gzip; dump source and dump tool are PostgreSQL 16.13. | PARTIAL. Archive is structurally listable and its public table-data name set matches, but the header/numbered-entry count difference of four is unexplained. Listing is not a data restore or data-equality check. |
| Earlier failed attempt | The same backup directory also contains a distinct timestamped 0-byte dump from 2026-10-24 19:26 UTC. The candidate manifest records a prior zero-byte attempt. | It is a separate failed artifact, not the 530,714-byte candidate. Neither file was changed. |
| October 10 historical dump | `D:\Git Projects\Multi-Round-Assessment-backups\ai_placement_platform_dev_20261010_231634.dump`; size 373,132 bytes; SHA-256 `92C5CBACB062BE12DF6B6C09C7AB895B6E98CDB3AEBE79F48C553E852BAA3705`. Its Phase E manifest agrees and records PostgreSQL 16, revision `add_competency_mapping_status_4g`, and 4,978 rows. | Separate, older backup. The Phase E manifest documents a historical scratch restore/count check for this October 10 artifact only. That evidence is historical and does not validate the October 24 candidate. |
| Earlier Phase 7G wording | Phase 7G compared the October 24 candidate figures in the prior report to the October 10 dump found through the Phase E manifest path, describing them as one “current dump at the manifest path.” | **Correction:** these are two different paths/artifacts. The size/hash difference is explained by comparing the October 24 candidate (530,714 bytes / `CD2D…4982`) with the October 10 historical dump (373,132 bytes / `92C5…3705`), not by a changed file at one path. Earlier report entries remain as historical notes; this section records the reconciled paths. |

### Current source and freshness

The source was queried through the existing local `DATABASE_URL` in a `REPEATABLE READ`, read-only transaction. No destination was contacted in Phase 7H.

| Check | Current source result | Candidate manifest comparison |
|---|---|---|
| Identity and version | `ai_placement_platform`, loopback port 5432, role `postgres`, PostgreSQL 16.13; transaction reported read-only. | Matches manifest source identity/version. No connection URL or credential was printed. |
| Alembic revision | `add_faculty_practice_assignments`. | Matches the candidate manifest. It is still one revision behind repository head `use_unspecified_student_department_default`. |
| Public schema | 39 base tables, 395 columns, 151 indexes, 136 constraints, 37 sequences. | The candidate lists all 39 current public table-data names and its five expected migration objects. The manifest has no per-table or total row counts and no schema-definition checksum. |
| Current source rows | Bounded per-table aggregate counts (limit 10,001) totaled 6,641 including the one `alembic_version` row: 6,640 application rows in 34 populated application tables; largest table 905 rows; no cap was reached. | Cannot compare data freshness or row equality: candidate manifest records no row counts. Current source revision matching the candidate does not prove its row data is current. |

### Candidate trust decision and historical validation

**Candidate status: NOT TRUSTED FOR RESTORE.** Its file identity, checksum, source version/revision, expected objects, and public table-data name set are consistent. However, its manifest has no row counts; the archive TOC count discrepancy is unresolved; and no scratch restore/count/schema comparison of this October 24 candidate was found. A successful `pg_restore --list` proves the archive is readable as a listing, not that restoring it reproduces the current source. The October 10 manifest's historical scratch validation applies only to the separate October 10 archive.

The candidate manifest also tracks external assets separately from the database dump. Current resume-upload inventory matches its recorded aggregate metadata (87 files, 1,312,452 bytes), as does company-history upload inventory (487 files, 5,124,636 bytes). Individual upload contents/digests were not re-read or compared. The current `app/data/kb.index` has the same size as the manifest (199,725 bytes) but its SHA-256 does **not** match the manifest's index digest. No personal file contents or filenames were printed. The candidate is therefore not a verified full-system recovery set even apart from its database restore gap.

### Fresh backup procedure — prepared, not executed

1. Obtain an approved source write-freeze window from the application/data owner. Pause all application writers and scheduled jobs; record the freeze time and confirm the target is still the local source. Without a freeze, dump consistency is transactional for PostgreSQL but associated file assets and app-level relationships may change during capture.
2. Confirm capacity on the backup volume for a new dump, manifest, temporary logs, and a scratch database with reasonable growth headroom. The live database currently occupies 16,833,559 bytes by `pg_database_size`; the available free space was not verified. Keep the dump and scratch database outside the repository. Never reuse either existing dump filename.
3. Use a current PostgreSQL 17 client `pg_dump` (not currently installed; only PostgreSQL 16.13 tools were found) against the verified PostgreSQL 16.13 source. Use a protected Windows PostgreSQL password file/approved secret provider, not a password in command arguments or logs. Create a new UTC-timestamped custom-format (`-Fc`) dump using a unique filename. Do not point the command at Supabase.
4. After a successful dump, record source identity/version/revision, capture time, per-table counts, table/object inventory, archive size, and SHA-256 in a new manifest. Run `pg_restore --list`; verify its exit status, archive format, source/tool versions, table-data inventory, and manifest checksum. Record any discrepancies; do not overwrite an earlier manifest.
5. Only after separate explicit approval, restore the new artifact to a uniquely named disposable scratch database on an isolated local cluster (or approved isolated server). Scratch database creation and `pg_restore` perform writes, so they are not authorized in this phase. Validate exact source/scratch per-table counts, schema objects, constraints/FKs, indexes/partial predicates, sequences/ownership/current values, extensions, migration history, and integrity aggregates. Drop the scratch database only under that later explicit approval and after retaining the validation evidence.
6. Keep database backup verification separate from file-asset preservation. Create a separate manifest of upload assets and KB-index checksums without putting personal contents in the audit report; verify every asset digest in an approved protected process. The present KB-index fingerprint mismatch must be resolved.

Required approvals/resources: application write freeze; permission to read/dump all source schemas and sequences; operator access to a protected credential file; PostgreSQL 17 client installation/availability; sufficient backup-volume and scratch-instance space; explicit approval to create and restore into a disposable scratch DB; and data-owner approval for retention of the resulting backup and asset manifests. No such freeze, backup creation, or scratch restore was performed here.

### Isolated Supabase staging checklist — not provisioned or contacted

| Readiness item | Required before staging |
|---|---|
| Project identity | Provision a separate, approved staging project. Record expected project reference and database name; verify direct/pooler endpoint, server version, connected database and role before inspection or writes. Do not reuse the populated project as disposable. |
| TLS | Obtain that project's CA from its authorized Supabase dashboard. Verify certificate metadata/provenance and use `sslmode=verify-full`; positively confirm hostname/CA validation and client TLS metadata before inspection. Do not assume the current project CA applies to a new project. |
| Roles and privileges | Separate read-only auditor, narrowly scoped migration role, and least-privilege application runtime role. Review Supabase-managed role limits; runtime role must not have role creation, database creation, or replication privileges. Configure only after approval. |
| PostgreSQL 16 to 17 | Validate a PostgreSQL 17 client/dump workflow and extension availability. PostgreSQL documents logical dump forward compatibility to newer server versions; this is not a substitute for restore testing or Supabase-specific validation ([PostgreSQL `pg_dump`](https://www.postgresql.org/docs/16/app-pgdump.html)). |
| Alembic/schema | Decide the baseline and exact target revision; the live source is `add_faculty_practice_assignments`, repository head is `use_unspecified_student_department_default`, and current destination history is unrelated. Resolve model/live drift, department default, missing blueprint column/FK, `rl_attempt_log` FKs, partial unique indexes, and destination-only functions/triggers/constraints before generating or applying SQL. Review every migration; no blind autogeneration. |
| Extensions/provider objects | Confirm required extensions are available and versions compatible. Restore only approved application schemas/objects; exclude Supabase-managed `auth`, `storage`, `realtime`, `vault`, `graphql`, and provider-owned objects from generic restore operations. |
| Seed/reference data and collisions | Define which reference/seed rows come from the source, disable duplicate startup seeding, handle sequences, and validate primary/natural keys. Do not merge the current destination's 7,398 rows; destination ownership and equivalence remain unknown. |
| External assets | Plan access-controlled upload of resumes and company files, preserve database-to-object mappings and policies, validate per-file checksums, and resolve the KB-index mismatch or rebuild from approved inputs. |
| Application configuration/pooling | Keep local `.env` and `DATABASE_URL` unchanged. Configure a separate staging deployment secret only after approval; verify pooler mode/port and driver compatibility. Use a connection mode appropriate for migrations and session-level features; test pool sizing/timeouts without exposing URLs. |
| Validation/rollback/cutover | Restore only to isolated staging after scratch validation. Compare schema, row counts, constraints, indexes, sequences, extension/function behavior, assets, and application smoke tests. Define a write-freeze and rollback owner, source preservation, monitoring, and explicit go/no-go before any production cutover. |

### Commands, tests, working tree, and decision

| Check | Result |
|---|---|
| Candidate file metadata/hash and manifest | PASS for observed size/hash agreement; manifest parsed without printing asset filenames or credential fields. |
| `pg_restore --list` on October 24 candidate | PASS for command exit and custom archive readability; 39 table-data names match the current source. TOC header 442 vs 438 numbered listing records remains unexplained. |
| October 10 historical dump | PASS for file identity match with its Phase E manifest and archive listing (historical only); no restore repeated. |
| Current source identity/schema/counts | PASS; read-only repeatable-read transaction; 16.13, revision `add_faculty_practice_assignments`, 39 public tables; bounded counts exact under the cap. |
| Asset manifest comparison | PARTIAL; upload counts/bytes match, individual upload digests not checked; KB-index digest differs despite equal size. |
| Audit configuration tests | PASS: `python -m pytest -p no:cacheprovider tests/test_supabase_audit_config.py -q` — 14 passed. No application or database tests were run. |
| Files changed in Phase 7H | Only this report section was appended. Existing tracked modifications and untracked files were preserved. No database, backup, manifest, asset, `.env`, or connection target was modified. |
| Database / backup operations | NOT RUN: no new dump, database creation, scratch restore, DDL/DML, grant/role changes, migration, or cutover. |

**Phase 7H decision: BLOCKED.** The October 24 dump is a promising candidate but remains **NOT TRUSTED FOR RESTORE** until the archive listing discrepancy is explained and it is restored and validated in a separately approved scratch database against a current frozen source. The separate October 10 backup is historical and stale. Resolve the KB-index digest mismatch and prepare an isolated staging project only after owner approval. Stop here and wait for explicit approval before creating a backup or scratch database.

## Phase 7I — Read-only archive listing and KB-index integrity investigation (2026-10-25)

### Scope and preservation

The October 24 candidate was read only at its documented path. No archive was extracted, rewritten, or restored. The local source was inspected in a `REPEATABLE READ`, read-only transaction to compare catalog metadata only. No Supabase connection was made. The October 10 artifact and both manifests remain separate and untouched. Initial Git status and relevant diffs were reviewed; no staged changes were present. Existing changes to `app/config/settings.py`, `requirements.txt`, and the untracked audit/certificate/report files were preserved.

### Archive identity and TOC discrepancy

| Check | Verified result | Assessment |
|---|---|---|
| October 24 archive identity | 530,714 bytes; modified 2026-10-24 19:29:26.6039251 UTC; SHA-256 `CD2D23825CD8CBFE1525A3CE5985DAD46848683E59EDBCABC843D1A0C9424982`. | PASS: current file size and hash match the candidate manifest (case-insensitive hex comparison). It was not modified. |
| Archive header | `TOC Entries: 442`; custom format; gzip compression; dump source PostgreSQL 16.13; dumped by PostgreSQL 16.13 `pg_dump`. | Header count is the complete archive TOC count. PostgreSQL 16 source writes the count of all stored TOC entries. |
| Normal `pg_restore --list` | PostgreSQL 16.13; exit 0; 438 numbered entries. | The four-entry difference is a listing selection convention, not evidence of four malformed or missing archive entries. |
| Verbose `pg_restore --list --verbose` | Exit 0; 442 numbered entries, exactly the header count; zero parse failures and zero duplicate dump IDs. The four additional descriptors are `DATABASE`, `ENCODING`, `SEARCHPATH`, and `STDSTRINGS`. | PASS: the discrepancy is resolved. In PostgreSQL 16, the three session-state entries are `REQ_SPECIAL`, and the database entry is not selected unless `--create` is requested. Normal list output prints only schema/data entries; verbose output includes all. See [PostgreSQL 16 `pg_restore` documentation](https://www.postgresql.org/docs/16/app-pgrestore.html) and [PostgreSQL 16 archive-list implementation](https://github.com/postgres/postgres/blob/REL_16_STABLE/src/bin/pg_dump/pg_backup_archiver.c#L1133-L1200). |
| Public table schema/data entries | 39 `TABLE` entries and 39 `TABLE DATA` entries; each name set exactly matches the current source’s 39 public base tables (no missing or extra names). All five manifest-expected table objects, including `alembic_version` and the four faculty-practice tables, occur in the archive table entries. | PASS for public table and table-data inventory. This does not compare table row contents. |
| Explicit `SCHEMA public` TOC entry | None. The live source has one non-system schema (`public`), owned by `pg_database_owner`. | Expected for this source: PostgreSQL 16 `pg_dump` omits the definition of the initdb-created `public` schema when it has the default `pg_database_owner`; the archive contains table entries under that schema. Any restore target must supply the standard `public` schema. See [PostgreSQL 16 namespace-dump logic](https://github.com/postgres/postgres/blob/REL_16_STABLE/src/bin/pg_dump/pg_dump.c#L1634-L1695). |
| Other archive entries | Listing has object entries for indexes, constraints/FKs, sequences and sequence state, defaults, functions, and other schema objects. | The TOC was parseable and IDs were unique. This phase did not compare every archived object definition with the live source or inspect data payloads; full schema/data equivalence remains unverified. |

The source catalog check confirmed database `ai_placement_platform`, PostgreSQL 16.13, public revision `add_faculty_practice_assignments`, and 39 public tables. The revision matches the candidate manifest. The dump listing does not expose the `alembic_version` row value, so the archived revision itself is **not independently verified** without restoring or extracting payload data. The manifest’s five expected-object flags and live source revision are corroborating metadata, not a substitute for reading restored contents.

The count discrepancy is therefore explained by PostgreSQL’s listing behavior. The archive has no observed malformed or duplicate TOC IDs, and its public table schema/data name sets have no missing or unexpected names. This does not prove every compressed data block can be restored or that archived rows equal the current source. `pg_restore --list` reads and displays the TOC; it is not a restore or full data-payload integrity test.

### Knowledge-base index and asset integrity

| Asset/check | Current evidence | Result |
|---|---|---|
| `app/data/kb.index` | Exists; 199,725 bytes; modified 2026-09-26 17:38:11.2872722 UTC; SHA-256 `E8070082A5CDAE71FABF13491869312324798D4F7FAD23A13B06E1AFE5B19C36`. | PASS: exact digest matches the October 24 manifest and the committed `HEAD` blob. The file is tracked, has no working-tree change, and Git history records prior tracked revisions (latest 2026-08-15). |
| Phase 7H hash difference | The prior comparison used Python’s lowercase hexadecimal digest and compared it case-sensitively with the manifest’s uppercase hexadecimal string. | **Correction:** SHA-256 values are case-insensitive hexadecimal representations; normalized values are identical. The prior “hash mismatch” was a comparison-format false negative, not an index update or evidence of corruption. |
| Build/history evidence | `scripts/build_kb_index.py` reads `app/data/question_bank.json` and `app/data/concept_kb.json`, builds the FAISS index, and writes `kb.index` and `kb_metadata.json`. The tracked index matches `HEAD`; current data/index files have no Git modifications. `kb_metadata.json` contains 65 indexed metadata entries but no top-level build timestamp/version or artifact digest. | The present index’s integrity against both Git and the candidate manifest is verified. Its exact generation time and reproducible input/configuration snapshot are not independently recorded. No index contents were printed or rebuilt. |
| Resume/company upload assets | Current inventory compared to the October 24 manifest by hashed relative path, size, and SHA-256, without outputting paths, names, or contents. | PASS: all 87/87 resume files and all 487/487 company-history files match their manifest sizes and SHA-256 digests. Aggregate counts/bytes also match. |
| Other asset-manifest coverage | The candidate manifest fingerprints `kb.index` and inventories the upload files; it does not record a digest for `kb_metadata.json`. | PARTIAL: `kb_metadata.json` is tracked and unchanged in Git, but it is not independently bound into the candidate backup manifest’s asset checksum set. |

### Trust status and remaining prerequisites

The archive listing discrepancy is resolved and the candidate file still matches its manifest. The knowledge-base hash discrepancy is also resolved as a case-format comparison error. **The October 24 archive remains NOT TRUSTED FOR RESTORE.** No scratch restore has validated its data payload, exact row counts, archived Alembic revision, constraints/indexes/sequences, or compatibility against an isolated target. Do not upgrade trust based solely on a readable TOC, matching table names, or checksum identity.

Prioritized prerequisites:

1. Obtain explicit approval for a uniquely named, disposable scratch database and restore validation; this phase does not authorize either operation. Keep the existing dump and manifests unchanged.
2. At an approved source write freeze, compare source and scratch exact per-table counts, Alembic revision, schema definitions, constraints/FKs, indexes/partial predicates, sequences/current values, and relevant integrity aggregates. Preserve the local source and candidate archive.
3. Decide whether `kb_metadata.json` should be included in a future full-system asset manifest; add a digest only during a separately approved backup procedure. The current index itself matches its manifest and Git `HEAD`.
4. Retain the already matched upload-file manifest as evidence; do not expose candidate filenames or contents in migration reports.

### Checks, working tree, and safety

| Check | Result |
|---|---|
| PostgreSQL archive tools | `pg_restore --version`, `pg_restore --help`, normal `--list`, and `--list --verbose` were run. Both listing modes exited 0; the TOC count behavior is explained above. |
| Source catalog | PASS: local target identity/revision/table inventory queried in a read-only repeatable-read transaction; no source rows were modified. |
| KB/Git integrity | PASS: file metadata/hash, candidate manifest digest, Git tracking/status, `git hash-object` vs `HEAD`, and history metadata checked without printing index contents. |
| Upload integrity | PASS: 574 manifest entries matched current file path hashes, sizes, and content digests; no personal filenames or contents were printed. |
| Automated tests | NOT RUN: no code was changed; archive, metadata, manifest, and Git checks were used instead. |
| Files changed in Phase 7I | Only this report section was appended. No backup, manifest, database, KB index, metadata file, upload asset, `.env`, script, or test file was modified. |
| Database/backup actions | NOT RUN: no database writes, DDL/DML, migration, backup creation, extraction, restore, scratch database, project provisioning, or cutover. |

**Phase 7I decision: archive-list discrepancy RESOLVED; KB-index hash discrepancy RESOLVED; restore trust remains BLOCKED.** Wait for explicit approval before any backup creation or scratch-restore validation.


## Phase 7J - Zero-overwrite backup protection and validation (2026-10-25)

### Preflight

| Check | Result |
|---|---|
| Git preservation | PASS. Initial status was reviewed; no staged changes were present. Existing modified and untracked files were preserved. |
| Configured source | PASS. Existing application settings resolved to loopback localhost:5432/ai_placement_platform; the URL and credential were not printed or changed. |
| Read-only source identity | PASS. PostgreSQL 16.13, role postgres, Alembic revision add_faculty_practice_assignments; 39 public tables, 6,640 application rows plus the Alembic version row, database size 16,833,559 bytes. Query transaction reported read_only=on. |
| Historical October 10 artifact | PASS. D:/Git Projects/Multi-Round-Assessment-backups/ai_placement_platform_dev_20261010_231634.dump; 373,132 bytes; modified 2026-10-10 17:46:36.626877 UTC; SHA-256 92C5CBACB062BE12DF6B6C09C7AB895B6E98CDB3AEBE79F48C553E852BAA3705, matching its previously recorded value. |
| Historical October 24 candidate | PASS. C:/Users/Akshada/AppData/Local/EDI5-Backups/ai_placement_platform_20261024T192924Z.dump; 530,714 bytes; modified 2026-10-24 19:29:26.603925 UTC; SHA-256 CD2D23825CD8CBFE1525A3CE5985DAD46848683E59EDBCABC843D1A0C9424982, matching its manifest. The October 10 and October 24 artifacts remain separate and unchanged. |
| Tools and capacity | PASS. pg_dump and pg_restore are PostgreSQL 16.13. Backup volume had 20,131,622,912 bytes free at preflight. Conservative reserved space was 117,609,541 bytes (three times the measured source database size plus 64 MiB for overhead); capacity was sufficient. Both final target names were checked absent before creation. |
| Consistent source inventory | PASS. Exact table counts and inventory were captured under one REPEATABLE READ READ ONLY transaction and exported snapshot. No application write freeze was imposed. External asset synchronization is outside this database dump. |

### Backup creation and structural validation

The first output attempt used pg_dump --file=-. PostgreSQL treated - as a literal filename: a 530,714-byte archive was created at the repository-root path - (SHA-256 673C36D9263548C88137B03612BB9AE20437B7AA4002E515EFA773278E7E3AEE), while the intended first target remained zero bytes. pg_restore --list on that zero-byte target exited 1. The zero-byte failed artifact and its manifest were preserved; nothing was deleted or overwritten. The root - archive is independently listable (exit 0) and its 39 table and 39 table-data entries match the captured source inventory. It remains as a new untracked file for review.

A corrected invocation omitted the output-file option and directed standard output to an exclusive-created, previously absent target:

C:/Users/Akshada/AppData/Local/EDI5-Backups/ai_placement_platform_20261025T094836Z_phase7j_verified.dump

| Check | Result |
|---|---|
| pg_dump | PASS; PostgreSQL custom format; exit code 0; source snapshot imported from the read-only transaction. |
| Archive file | 530,714 bytes; modified 2026-10-25 09:49:19.252159 UTC; SHA-256 466D701CAC2CA0C65B0793D7F5F4B2770BFE21C9BE88DD7C77DDD8C23418886B. Independent post-write hash and manifest comparison passed. |
| pg_restore --list | PASS; exit code 0. The archive has 39 TABLE and 39 TABLE DATA entries. Both inventories exactly match the 39 source tables; no table or table-data entries were missing or extra. |
| Manifest | Created alongside the archive as ai_placement_platform_20261025T094836Z_phase7j_verified.manifest.json; records source identity/version/revision, snapshot row counts, tool results, archive size/hash, and inventory comparison. |
| Full restore/data validation | NOT RUN. TOC readability and table-name agreement do not establish that every data block restores or that restored rows/schema equal the source. The archive remains NOT TRUSTED FOR RESTORE. |

### Preservation, checks, and decision

- The original October 10 and October 24 backup sizes and hashes were rechecked after creation and still match their recorded values.
- A post-backup local identity query again returned ai_placement_platform, PostgreSQL 16.13, revision add_faculty_practice_assignments, 39 public tables, and a read-only transaction. No database-changing command was issued.
- No Supabase connection, migration, DDL/DML, restore, scratch database, role/grant change, cutover, or asset operation occurred. The existing backup, source database, .env, and application assets were not modified.
- Checks actually run: git status --short; review of tracked diffs and staged status; pg_dump --version; pg_restore --version; pg_restore --list on the failed target, the root - archive, and the final archive; SHA-256 and file metadata checks; manifest comparison; and read-only repeatable-read source identity, inventory, and exact count queries. git diff --check was run after the report append. Automated tests were NOT RUN; no code was changed.

Files introduced or updated by Phase 7J:
- This Phase 7 status report was appended.
- - is a new untracked 530,714-byte archive produced by the first command's output-option behavior; it was preserved for review.
- The failed zero-byte artifact and its manifest are preserved in the external backup directory as ai_placement_platform_20261025T094512Z_phase7j.dump and ai_placement_platform_20261025T094512Z_phase7j.manifest.json.
- The verified archive and its manifest are preserved there as ai_placement_platform_20261025T094836Z_phase7j_verified.dump and ai_placement_platform_20261025T094836Z_phase7j_verified.manifest.json.

**Phase 7J decision: backup creation and structural inventory checks PASS; restore trust remains BLOCKED.** Next prerequisite: obtain explicit approval for a uniquely named disposable scratch database and a restore-validation procedure. Stop before creating a scratch database or restoring anything.


## Phase 7K - Isolated backup restore validation and data integrity audit (2026-10-25)

### Scope and target

Phase 7K was authorized to restore only the Phase 7J October 25 candidate into a new local scratch database. It did not authorize Supabase restore, migration, application cutover, or cleanup.

- Backup: C:/Users/Akshada/AppData/Local/EDI5-Backups/ai_placement_platform_20261025T094836Z_phase7j_verified.dump; 530,714 bytes; SHA-256 466D701CAC2CA0C65B0793D7F5F4B2770BFE21C9BE88DD7C77DDD8C23418886B. The manifest agrees.
- Source: localhost:5432/ai_placement_platform, PostgreSQL 16.13, cluster system identifier 7612714455082792120, revision add_faculty_practice_assignments.
- Scratch: edi5_restore_validation_20261025_022d4117 at localhost:5432, same positively verified local cluster, created from template0 with matching UTF8 encoding and collation. The database was absent before creation, empty before restore, and had zero other sessions. It is left intact.
- Existing edi5_restore_verify_20261025 was not reused: read-only inspection found 39 tables and 6,641 rows. It remains untouched.
- The configured application target remains ai_placement_platform. No Supabase connection was made.

### Restore and comparison results

The exact restore command and pre-restore evidence are in [the Phase 7K report](EDI5_PHASE_7K_SCRATCH_RESTORE_VALIDATION.md), with machine-readable metadata in EDI5_PHASE_7K_20261025_022d4117/. The explicit pg_restore command named only the new scratch database, used --exit-on-error and --single-transaction, and used --no-owner --no-privileges while omitting --create and --clean. It exited 0 with no stderr output.

| Check | Result |
|---|---|
| Archive identity and listing | PASS. Size/hash and manifest match; verbose listing has 442 unique TOC IDs; 39 TABLE and 39 TABLE DATA entries. |
| Table counts | PASS. All 39 table counts match the Phase 7J snapshot manifest and current source; total 6,641 including the Alembic version row. |
| Full-row fingerprints | PASS. Deterministic SHA-256 fingerprints of all rows, ordered by each table primary key with UTC timestamp serialization, match for 39/39 tables. No record values or fingerprints were printed. |
| Columns and indexes | PASS. All 395 columns and 151 index definitions match; partial predicates and validity/readiness were included. All 39 tables have primary keys. |
| Constraints | PASS with a documented textual difference. Both sides have the same 136 named constraints and validation flags; all are validated. Fifteen CHECK constraint definitions have a PostgreSQL deparse difference in varchar/text casts. Read-only tests evaluated all listed allowed values plus a rejected sentinel in both databases; all 15 pairs have matching behavior. The other four check definitions match exactly. |
| Foreign keys and integrity | PASS. All 61 foreign keys are validated and orphan counts are zero on both databases. Critical null counts match. There are no invalid unique indexes or unvalidated constraints. |
| Sequences | PASS. All 37 sequence definitions, ownership mappings, states, and next-value safety checks match; each next value is above its owned-column maximum. |
| Extensions and database options | PASS. plpgsql 1.0, database encoding/collation, and absence of database-specific role settings match. Both have no public views, routines, triggers, or large objects. |
| ACL and application checks | NOT VERIFIED. Restore used --no-owner --no-privileges; ACL parity and runtime role access were not tested. No application process or write test was run. |

### Tests, preservation, and decision

- PASS: python -m pytest -p no:cacheprovider tests/test_supabase_audit_config.py -q (14 passed).
- PASS: pg_restore archive listings, source/scratch read-only catalog and data comparisons, hashes/manifest checks, and git diff --check. Git emitted only its existing line-ending warning for requirements.txt.
- No source database changes, Supabase writes, migrations, role/grant changes, application setting changes, asset changes, or cleanup occurred. Only the new scratch database received restore writes.
- The October 10 and October 24 original backups still match their recorded size/hash. The Phase 7J root-level - artifact, zero-byte failed artifact, manifests, populated earlier scratch DB, and application assets remain preserved.
- Git-visible Phase 7K additions are EDI5_PHASE_7K_SCRATCH_RESTORE_VALIDATION.md and EDI5_PHASE_7K_20261025_022d4117/; prior modified and untracked files remain present. No source code was changed.

**Phase 7K decision: local backup schema and data restore validation PASS.** The October 25 candidate is now RESTORE-VALIDATED IN LOCAL SCRATCH for PostgreSQL schema and data. This evidence does not establish Supabase compatibility, ACL/application behavior, existing destination ownership, or cutover readiness. Next, review destination data ownership and migration mapping, then use a separately approved isolated staging project. Do not restore to the existing Supabase destination or cut over without separate explicit authorization.


## Phase 7L - Supabase destination ownership and isolated staging plan (2026-10-25)

### Scope and safety

Phase 7L performed local read-only source/scratch checks, reviewed Phase 7K and historical Phase 7G evidence, and inventoried application asset dependencies. No Supabase connection was opened because an environment-inspection command accidentally emitted `.env` assignment lines in tool output. The audit URL is considered exposed and must be rotated before further use. No destination values are reproduced here. No migration, restore, DDL/DML, role/grant change, project provisioning, cutover, or asset copy was performed.

Initial `git status --short` was captured before edits. Existing modifications to `app/config/settings.py` and `requirements.txt`, the root `-` artifact, certificates, audit reports, Phase 7K artifacts, audit script, and tests were preserved. No staged changes were present. The complete new Phase 7L report is [EDI5_PHASE_7L_SUPABASE_DESTINATION_OWNERSHIP_AND_STAGING_PLAN.md](EDI5_PHASE_7L_SUPABASE_DESTINATION_OWNERSHIP_AND_STAGING_PLAN.md).

### Local source and backup

| Check | Result | Evidence |
|---|---|---|
| Effective application database target | PASS | Sanitized settings parse remains `localhost:5432/ai_placement_platform`; no application database setting was changed. |
| Local source identity | PASS | Read-only identity query returned `ai_placement_platform`, role `postgres`, PostgreSQL 16.13, port 5432, loopback. |
| Source and scratch data | PASS | Exact read-only counts found 39 public tables and 6,641 rows in each; table-name sets match and per-table row-count mismatches are zero. Phase 7K separately records 39/39 full-row fingerprints matching. |
| October 25 verified backup | PASS per Phase 7K | 530,714 bytes; SHA-256 `466D701CAC2CA0C65B0793D7F5F4B2770BFE21C9BE88DD7C77DDD8C23418886B`; local scratch restore validation passed. Backup and scratch database were left untouched in Phase 7L. |

### Destination ownership and staging decision

Both dedicated audit configuration entries were present via the audit script's existing independent dotenv loader. Their values are not included here. A fresh destination TLS, identity, inventory, row-count, schema, and privilege audit is **BLOCKED** until the exposed credential has been rotated. Do not treat the prior Phase 7G results as current connection evidence.

Historical Phase 7G evidence recorded a PostgreSQL 17.11 Supabase session-pooler destination with verify-full TLS, 34 public tables, 7,398 application rows in 28 populated tables, 2,486 matching PK values across 21 shared tables, six destination-only tables (some populated), 11 source-only tables, schema/object drift, and broad audit-role privileges. Destination ownership/provenance was not established then and was not established in Phase 7L. Classify all destination application data **UNKNOWN - PRESERVE**. Do not reuse, append, merge, overwrite, or restore into the existing destination.

**Recommendation:** after credential rotation and a fresh read-only audit, obtain owner approval for a new isolated Supabase staging project. A separately provisioned isolated PostgreSQL instance is a secondary option for generic PostgreSQL validation but cannot establish Supabase-specific behavior. Existing-destination reuse remains blocked. The full report includes the schema-compatibility register, application/asset dependencies, staging comparison, rollback outline, and acceptance/approval gates.

Phase 7L rechecked metadata only for external assets: 87 resume files / 1,312,452 bytes; 487 company historical-upload files / 5,124,636 bytes; and `app/data/kb.index`, 199,725 bytes, SHA-256 `E8070082A5CDAE71FABF13491869312324798D4F7FAD23A13B06E1AFE5B19C36`. No file contents, personal data, or filenames were read or printed; no assets were modified. Row-to-file mapping and individual upload digests remain unverified.

### Tests, files, and stopping point

- `python -m pytest -p no:cacheprovider tests/test_supabase_audit_config.py -q`: **14 passed**.
- Local exact table-count comparison and source/scratch identity queries: **PASS**, read-only transactions.
- Destination audit: **NOT RUN** in Phase 7L because credential rotation is required.
- `git diff --check`: results recorded after final report edits; no code files were changed by Phase 7L.
- Files added/updated in Phase 7L: this migration status report and `EDI5_PHASE_7L_SUPABASE_DESTINATION_OWNERSHIP_AND_STAGING_PLAN.md` only.

**Phase 7L decision: BLOCKED pending credential rotation, fresh destination audit, and owner confirmation.** The existing destination remains UNKNOWN - PRESERVE. Next approval required: authorize the named isolated staging project, scope, role model, and cost boundary after the read-only audit is repeated. Stop here; Phase 7M, provisioning, migration, restore, and cutover are not authorized.


## Phase 7M - Credential recovery and fresh destination re-audit (2026-10-25)

### Credential and identity

The owner confirmed credential rotation and local audit-setting update. The dedicated audit configuration loaded without exposing values, and the new configured credential authenticated successfully. The old password was not tested; provider-side retirement is owner-confirmed but not independently verified. The application target remains `localhost:5432/ai_placement_platform`; no app DB configuration was changed.

Fresh destination connection checks **PASS**: expected project route matched, database `postgres`, PostgreSQL 17.11, session pooler, and client TLS verified by libpq `sslmode=verify-full` with the pinned project CA and hostname validation. Protocol/cipher details are not exposed by Psycopg 3, so those are not claimed. Inspection queries ran in read-only transactions. No URL, password, token, project reference, or record content is included here.

### Fresh inventory and risk

| Check | Result |
|---|---|
| Destination public inventory | 34 public tables; bounded-exact count 7,599 rows; no table reached the 10,001-row cap. |
| Local source | 39 public tables; bounded-exact count 6,641 rows. |
| Schema comparison | 11 source-only tables, 6 destination-only tables; 125 source-only columns, 104 destination-only columns, 2 shared column-definition differences. 76 source-only and 33 destination-only index names; 51 source-only and 21 destination-only constraints, with one shared constraint definition difference. |
| Other objects | Four destination-only extensions, four destination-only routines, and six destination-only triggers. Sequence/trigger total counts differ between two metadata views and need reconciliation. Destination Alembic revision `47555f247a64` differs from source `add_faculty_practice_assignments`. |
| Effective privileges | SELECT on 73/73 visible base tables, but write privileges on 69 tables, CREATE on 2 schemas, plus CREATEDB, CREATEROLE, and REPLICATION. **FAIL least privilege**; no permission changes were made. |
| Current PK overlap | NOT VERIFIED. The supplemental current overlap aggregation produced no usable result. Phase 7G's 2,486-key result is historical only. No key values were reported. |
| Existing data and ownership | Destination contains 7,599 bounded-exact public rows. Ownership/provenance is **UNKNOWN - PRESERVE**. Do not restore, overwrite, merge, or cut over to this project. |

The full evidence and staging recommendation are in [EDI5_PHASE_7M_CREDENTIAL_RECOVERY_AND_DESTINATION_REAUDIT.md](EDI5_PHASE_7M_CREDENTIAL_RECOVERY_AND_DESTINATION_REAUDIT.md). Recommend a newly approved isolated Supabase staging project; it was not provisioned. The Phase 7K backup and scratch database remain untouched.

### Tests, Git state, and stopping point

- `python -m pytest -p no:cacheprovider tests/test_supabase_audit_config.py -q`: **14 passed**.
- `python -m py_compile scripts/audit_supabase_destination.py tests/test_supabase_audit_config.py app/config/settings.py`: **passed**.
- The first audit attempt was blocked at connection establishment by sandbox network restrictions; after approved network escalation, the same read-only audit completed its identity/TLS, metadata, privileges, and source schema comparison. It returned a data-present blocker as expected.
- Supplemental bounded count checks passed for destination and source. Current PK overlap is not verified; sequence/trigger inventory counting differences remain to reconcile.
- No migration, restore, DDL/DML, role/grant change, staging project, cutover, or asset operation occurred. Phase 7M changed only this report and the separate Phase 7M audit report.
- `git diff --check` and final worktree status are recorded after report review. Existing changes/untracked files were preserved; `.env`, databases, backup, and assets were not modified.

**Phase 7M decision: identity/TLS/read-only inventory PASS; least-privilege audit role FAIL; destination ownership UNKNOWN - PRESERVE; restore/reuse/cutover BLOCKED.** Obtain explicit owner approval for a named isolated staging project, region, scope, cost limit, role design, and rollback owner before provisioning or Phase 7N. Stop here.


## Phase 7N - Isolated Supabase staging approval and provisioning plan (2026-10-25)

### Scope and boundary

Phase 7N prepared an approval package for a separate isolated staging project only. No Supabase project was provisioned or contacted. No database, application configuration, credential, role, backup, scratch database, asset, or existing destination was changed. Existing destination data remains **UNKNOWN - PRESERVE** and is excluded from any restore or merge plan.

Phase 7M's current read-only findings are retained: expected destination route and TLS verification passed; destination PostgreSQL 17.11/session pooler; 34 public tables and 7,599 bounded-exact rows. The local source is PostgreSQL 16.13 with 39 public tables and 6,641 bounded-exact rows. Current key-overlap analysis remains unverified; the old destination audit role was broadly write-capable. Phase 7K validated the October 25 backup only in the local scratch database, not in Supabase.

### Proposal and approval requirements

Use a new owner-approved Supabase project with a distinct project identity, separately stored credentials, project-specific CA and verify-full TLS, staging-only application configuration, and no production traffic or shared mutable resources. Keep the development `DATABASE_URL` local. The project owner must select organization/region, cost ceiling and currency, compute/storage/backup/egress limits and alerts, authorized users, data/asset scope, retention, and named rollback owner. No cost or plan tier was assumed.

The plan defines conceptual roles for human project administrator, temporary migration operator, runtime application, and read-only auditor. It contains no executable SQL or grants; platform support and exact privileges must be verified for the selected project before a later separately approved implementation. Do not reuse the existing broadly privileged audit role as runtime identity.

Compatibility items requiring resolution before an import include PostgreSQL 16-to-staging compatibility; source/repository Alembic baseline; student department default assumptions; `refresh_tokens` metadata drift; `coding_problems.blueprint_id` and `rl_attempt_log` constraint/model differences; partial unique indexes; sequences, extensions, ACLs and role design; auth/session behavior; and external upload/KB-index/path handling. The Phase 7N plan includes measurable acceptance criteria, isolation conditions, rollback, cleanup, cost/ownership boundaries, and an owner checklist with an explicit provision-now authorization item.

### Tests, files, and stopping point

- `python -m pytest -p no:cacheprovider tests/test_supabase_audit_config.py -q`: **14 passed**.
- `git diff --check`: **passed**; Git emitted its existing line-ending warning for the pre-existing `requirements.txt` modification. Both report files also passed a direct trailing-whitespace scan.
- Files added/updated for Phase 7N: [EDI5_PHASE_7N_ISOLATED_STAGING_APPROVAL_AND_PLAN.md](EDI5_PHASE_7N_ISOLATED_STAGING_APPROVAL_AND_PLAN.md) and this status report only.
- Initial Git status was captured before editing. Existing modifications and untracked artifacts were preserved; no files were staged, reset, cleaned, stashed, or reverted.
- No database connection, project provisioning, restore/import, migration, role/grant change, application config change, asset copy, or cutover occurred.

**Phase 7N decision: plan prepared; provisioning is NOT AUTHORIZED until the owner explicitly approves the project identity, ownership, scope, cost boundary, roles, data/asset handling, rollback owner, and provision-now action.** Stop here and wait for explicit approval before Phase 7O.


## Phase 7O - Non-destructive migration readiness (2026-10-25)

### Current checks

Phase 7O did not connect to Supabase. The local application target was safely parsed as `localhost:5432/ai_placement_platform`; read-only identity and bounded-count checks confirmed the local source and Phase 7K scratch database both remain PostgreSQL 16.13 with 39 public tables, 6,641 rows, and revision `add_faculty_practice_assignments`.

The Phase 7J October 25 backup was rechecked read-only: 530,714 bytes, SHA-256 `466D701CAC2CA0C65B0793D7F5F4B2770BFE21C9BE88DD7C77DDD8C23418886B`. `pg_restore --list` exited 0 with 438 normal-list TOC entries. Phase 7I explains that PostgreSQL 16 verbose listing includes four special descriptors, giving 442 entries; the Phase 7K local restore validation remains separate evidence and was not repeated.

### Readiness summary

| Area | Phase 7O status |
|---|---|
| Source identity and verified backup | COMPLETE for current source identity and artifact hash/size/listing. |
| Local restore validation | COMPLETE within local scratch scope; ACL/runtime, Supabase, and application behavior remain outside that validation. |
| Schema/Alembic compatibility | PARTIAL; source/repository/destination revisions and identified model/schema drift need resolution/revalidation. |
| PK collision and entity mapping | BLOCKED; current key-overlap result is unavailable; Phase 7G overlap is historical only. |
| Existing destination role remediation | BLOCKED; Phase 7M found excessive privileges. No grant change is authorized. |
| Separate least-privilege roles | PARTIAL; Phase 7N has a conceptual matrix only; exact platform-supported roles/grants await a named target and approval. |
| External assets and path dependencies | PARTIAL; manifest evidence exists, but Phase 7O did not rehash all files or validate row-to-file mappings. |
| TLS/project identity | PARTIAL; existing destination was verified in Phase 7M; future staging identity/CA do not exist yet. |
| Rollback and recovery | PARTIAL; plan exists, but no staging rollback has been rehearsed and owner fields remain unapproved. |
| Staging provisioning authorization | BLOCKED; Phase 7N approval checklist is not complete. |

The complete non-destructive checklist, evidence references, limitations, and safest next step are in [EDI5_PHASE_7O_NON_DESTRUCTIVE_MIGRATION_READINESS.md](EDI5_PHASE_7O_NON_DESTRUCTIVE_MIGRATION_READINESS.md). Complete the Phase 7N owner selections and approval before provisioning; then verify the new target's identity/TLS read-only. Do not use the populated existing destination as staging.

### Offline checks, files, and safety

- `python -m pytest -p no:cacheprovider tests/test_supabase_audit_config.py -q`: **14 passed**. Inspected fixtures write only under pytest temporary directories and make no database connections.
- `python scripts/audit_supabase_destination.py --self-test-config`: **PASS**, detects missing config using an empty environment and nonexistent dotenv path; no `.env` read or connection.
- `pg_restore --list`: **PASS**, read-only TOC listing; local source/scratch identity/count checks: **PASS**, explicit read-only transactions.
- The default Supabase audit script was not run in Phase 7O because it creates a destination connection; no broad application/database-writing tests were run.
- Files added/updated in Phase 7O: [EDI5_PHASE_7O_NON_DESTRUCTIVE_MIGRATION_READINESS.md](EDI5_PHASE_7O_NON_DESTRUCTIVE_MIGRATION_READINESS.md) and this report only. Initial modifications/untracked files were preserved.
- No Supabase connection, cloud resource, credential, database write, restore, migration, role/grant change, asset operation, or cutover occurred.

**Phase 7O decision: local source and backup prerequisites are ready; migration/staging readiness remains PARTIAL/BLOCKED by compatibility, ownership, role, PK-overlap, asset-mapping, and owner-approval gaps. Stop here.**


## Phase 7P - Resolve migration blockers without data changes (2026-10-25)

### Scope and preservation

Phase 7P reviewed Phase 7O, 7N, 7M, 7K, and prior migration evidence; inspected repository diffs; compared live local source catalogs to Alembic ORM metadata in read-only transactions; checked local file-path references using aggregate counts only; and ran safe offline tests. No Supabase connection or query occurred. No database, credential, migration, role/grant, backup, asset, cloud resource, or application configuration was changed.

Initial Git status preserved the existing modified `app/config/settings.py`, `requirements.txt`, root `-` artifact, certificate/audit artifacts, scripts, and tests. No staged changes were present. This phase adds [EDI5_PHASE_7P_BLOCKER_RESOLUTION_PLAN.md](EDI5_PHASE_7P_BLOCKER_RESOLUTION_PLAN.md) and this summary only.

### Live source/model findings

The local source identity gate passed: `localhost:5432/ai_placement_platform`, PostgreSQL 16.13, Alembic revision `add_faculty_practice_assignments`; inspection transactions were explicitly read-only. Imported Alembic model metadata represents 37 tables/388 columns versus 39 live public tables/395 columns. The two live-only tables are `alembic_version` and unmapped `refresh_tokens`.

Live source has 60 FKs versus 58 in ORM metadata. The source includes `refresh_tokens.user_id`, `rl_attempt_log.question_id`, and `rl_attempt_log.session_id` FKs not represented in ORM metadata; ORM alone expects `coding_problems.blueprint_id` FK, absent in the source. The current `coding_problems.blueprint_id` orphan count is zero. `student_profiles.department` is NOT NULL with no server default; ORM has a Python default only. Both critical partial unique indexes for active sessions/rounds exist in the source, but matching model index declarations are absent. Source Alembic revision is the parent of repository head `use_unspecified_student_department_default`; that pending migration assumes a prior `Computer Science` server default not present on the live source.

The blocker plan gives conditional, minimal proposed fixes and verification/approval gates. Nothing was edited in ORM or Alembic code. Review migration distribution before altering a pending revision; otherwise prepare a new reviewed forward migration. Current PK overlap remains **NOT VERIFIED**; Phase 7G key counts are historical and no destination query was run.

### Assets, roles, and tests

Read-only source references: 41/41 resume rows have unique absolute file paths resolving to disk files; the resume directory has 87 files. Company history has 51 rows (28 file-upload, 5 manual, 18 pre-seeded); 28 unique absolute paths resolve, while the directory contains 487 files. Additional disk files are preserved and not classified disposable. `app/data/kb.index` exists at 199,725 bytes and matches the previously recorded digest; code loads it as a filesystem asset, with no database path reference found. Exact path mapping/ownership remains a staging task.

Phase 7M's destination role had broad write powers; Phase 7P made no changes. Phase 7N's auditor/migration/runtime/admin role matrix remains conceptual; exact Supabase-supported roles/grants require a named approved staging target. Destination ownership remains **UNKNOWN - PRESERVE** and collision results remain **NOT VERIFIED**.

- `python -m pytest --noconftest -p no:cacheprovider tests/test_supabase_audit_config.py tests/test_db_isolation_guard.py -q`: **18 passed**. `--noconftest` bypassed the inspected session fixture that can drop/recreate a configured test database.
- `python scripts/audit_supabase_destination.py --self-test-config`: **PASS**, no `.env` read and no connection.
- Source catalog/FK/default/asset aggregate queries: **PASS** under identity-gated read-only transactions. Offline Alembic revision metadata confirms one head and the source-to-head parent relation; an initial invalid range invocation was corrected with direct revision lookup.
- No default pytest suite, destination audit, migration, DDL/DML, role change, cloud provisioning, backup write, or asset operation was run.
- `git diff --check` and final Git status are recorded after report review.

**Phase 7P decision:** source/backup and local asset reference evidence is useful for planning; migration compatibility remains **PARTIAL**, PK collision and destination-role action remain **BLOCKED**, and destination ownership remains **UNKNOWN - PRESERVE**. Resolve model/migration drift, complete an authorized key/ownership analysis, obtain a least-privilege staging role design and owner approval before any staging import. Stop here; no migration or provisioning is authorized.


## Phase 7Q - Prepare local schema/ORM drift fixes (2026-10-25)

Phase 7Q rechecked the configured source through a loopback-only identity gate and inspected it under `SET TRANSACTION READ ONLY`: local `ai_placement_platform`, PostgreSQL 16.13, port 5432, source revision `add_faculty_practice_assignments`. The database reported no server default for `student_profiles.department`; `coding_problems.blueprint_id` remains nullable with no FK and zero current orphans; `rl_attempt_log` has user/session/question FKs; the two expected partial unique indexes exist with predicates `in_progress` and `active`. `refresh_tokens` has six baseline-defined columns, its user FK/index, and zero rows. Zero rows does not authorize dropping it.

Prepared ORM-only parity changes in [assessment.py](../../app/models/assessment.py) and [rl.py](../../app/models/rl.py), plus database-free regression tests in [test_schema_orm_drift_metadata.py](../../tests/test_schema_orm_drift_metadata.py). The focused final test run was **5 passed** with `--noconftest` to avoid the normal test fixture that can provision/drop a database. The department migration old-default assumption remains unresolved pending cross-environment revision checks; `refresh_tokens` remains pending an auth/data-owner decision. See [Phase 7Q proposal](EDI5_PHASE_7Q_SCHEMA_ORM_FIX_PROPOSAL.md) for per-item evidence, risks, detailed proposals, commands and verification plan.

No migration, restore, DDL/DML, Supabase connection, role change, backup/scratch database change, or asset operation occurred. Existing Git work was preserved. Phase 7Q stops before database schema changes; the next safe step is to review the ORM diff and resolve the two ownership/distribution questions before proposing executable migration SQL.


## Phase 7R - Close remaining local questions and prepare staging gate (2026-10-25)

Phase 7R reviewed the Phase 7Q model/test changes, local Alembic history and database workflow documentation, baseline/schema definitions, and authentication references. The current local source remains at `add_faculty_practice_assignments` with no server default on `student_profiles.department`. The Phase 7K scratch report records the same parent revision. No trustworthy deployment ledger was found, and repository history only proves that the migration file exists in source control. Whether `use_unspecified_student_department_default` was applied in any shared environment is therefore **NOT VERIFIED**; remote state was not queried. Check each approved environment's revision and actual column default read-only before deciding whether to amend an unpublished revision or add a corrective forward migration.

The `refresh_tokens` table is created by the baseline migration and SQL schema files. Current auth code refreshes access JWTs and describes opaque database refresh tokens as a future option; no runtime persistence implementation was found. Treat it as EDI5-managed, preserved schema with an unresolved authentication/security and data/schema owner decision. Do not drop it, infer a replacement schema, or allow autogeneration to propose its removal without an explicit owner decision.

Review of Phase 7Q confirmed that the added `rl_attempt_log` FKs match the live source targets and default NO ACTION delete behavior; the partial index metadata matches live source and migration key columns, uniqueness, and predicates. Tests assert those definitions and other relevant metadata. `Base.metadata.create_all` intentionally creates these constraints/indexes for fresh metadata-built test schemas; migration files themselves were unchanged. Focused offline tests: **9 passed** with `--noconftest -p no:cacheprovider`, avoiding the test fixture that can drop/recreate a configured database. No Supabase connection or database mutation occurred. See [Phase 7R remaining gaps and staging gate](EDI5_PHASE_7R_REMAINING_LOCAL_GAPS_AND_STAGING_GATE.md) for evidence, limitations, owner decisions, and the exact staging approval checklist.

Phase 7R leaves the source, backup, Phase 7K scratch database, assets, credentials, roles, and existing destination unchanged. No staging project is authorized. Obtain deployment revision/default evidence and the named auth/schema-owner decision, then complete every owner, budget, identity/TLS, inventory, PK-overlap, least-privilege, asset, backup/rehearsal, acceptance, and rollback gate before any staging provisioning or restore.


## Phase 7S - Final staging preflight (2026-10-25)

Phase 7S consolidated the Phase 7N/7R approval and evidence gates without a new database audit. Local source/backup identity and Phase 7K scratch-restore comparison are **READY WITH LOCAL SCOPE LIMITS**; they do not establish Supabase compatibility. The department migration's cross-environment application status remains **NOT VERIFIED**. `refresh_tokens` remains preservation-first pending an auth/security and schema-owner decision. The existing destination remains **UNKNOWN - PRESERVE** based on historical populated-destination evidence and unresolved ownership; it was not contacted.

Staging provisioning is **NOT AUTHORIZED**: the record lacks project owner/organization/region, maximum budget and currency, scope, role model, asset/data handling, rollback owner, and explicit provision-now approval. The Phase 7S preflight lists these required owner decisions separately from technical checks that can only occur after staging exists, including new project identity/TLS, inventories, PK overlap, role verification, restore rehearsal, asset mapping, and rollback/acceptance checks. See [Phase 7S final staging preflight](EDI5_PHASE_7S_FINAL_STAGING_PREFLIGHT.md). No tests were run because only documentation changed; no destination connection, provisioning, database operation, or asset operation occurred.


## Phase 7T - Resolve local uncertainty (2026-10-25)

Phase 7T inspected Alembic history, database workflow docs, release/deployment references, and auth/token code without contacting any shared database. Revision `use_unspecified_student_department_default` follows `add_faculty_practice_assignments`, changes the department server default to `Department Not Specified`, assumes the previous default was `Computer Science`, and downgrades back to `Computer Science`. Local source/scratch revision evidence and Git history do not establish deployment status; no deployment ledger was found. Cross-environment status remains **NOT VERIFIED**. Obtain an identity-verified read-only `alembic_version` and `student_profiles.department` default check in each supported environment before amending history or proposing a forward correction.

The baseline migration and SQL schema files create `refresh_tokens`; current auth code only refreshes access JWTs and describes opaque table-backed tokens as a future option. No runtime persistence implementation was found. Treat the table as migration-managed preserved schema until the authentication/security owner and schema/data owner explicitly decide its status. Preserve all definitions and any records; no model or policy was invented.

`python -m pytest --noconftest -p no:cacheprovider tests/test_schema_orm_drift_metadata.py -q`: **5 passed**. No database-writing test was run. See [Phase 7T local uncertainty resolution](EDI5_PHASE_7T_LOCAL_UNCERTAINTY_RESOLUTION.md) for evidence, exact later checks, owner decisions, and remaining staging blockers. No existing destination access, provisioning, migration, database operation, credential/role change, backup/scratch operation, or asset change occurred.


## Phase 7U - Local migration handoff (2026-10-25)

Phase 7U consolidated Phase 7Q-7T and prior verified local evidence into [the local migration handoff](EDI5_PHASE_7U_LOCAL_MIGRATION_HANDOFF.md). It records the Phase 7K source/backup identity and local-only scratch restore scope, safe reference commands, outstanding schema decisions, local asset inventory, and future staging verification/acceptance/rollback requirements. No prior database, backup, or asset audit was repeated.

Staging remains **NOT AUTHORIZED** pending owner/project/budget/scope/role/data-asset/rollback decisions and explicit provisioning approval. Cross-environment department migration status is **NOT VERIFIED**; `refresh_tokens` remains preservation-first pending auth/security and schema/data owner decisions. No tests were rerun because Phase 7U changed documentation only; documentation checks and final Git review were performed. No Supabase connection, provisioning, migration, restore, database or asset operation occurred.
