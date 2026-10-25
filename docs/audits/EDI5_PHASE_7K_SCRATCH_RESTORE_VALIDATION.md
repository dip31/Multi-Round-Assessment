# EDI5 Phase 7K - Scratch Restore Validation

- Audit start: 2026-10-25 10:07:39 UTC
- Status: restore and read-only validation complete; scratch database left intact.
- Scope: restore the verified local PostgreSQL backup into one new local scratch database and compare it with the source snapshot. No Supabase or application configuration change is in scope.

## Preflight findings

| Check | Result | Evidence |
|---|---|---|
| Repository state | PASS | Initial git status recorded in the Phase 7 status report. No staged changes. Existing modified and untracked files were preserved. |
| Candidate backup | PASS | C:/Users/Akshada/AppData/Local/EDI5-Backups/ai_placement_platform_20261025T094836Z_phase7j_verified.dump; 530,714 bytes; SHA-256 466D701CAC2CA0C65B0793D7F5F4B2770BFE21C9BE88DD7C77DDD8C23418886B. Manifest size/hash agree; pg_restore --list exits 0. |
| Archive inventory | PASS | Verbose TOC has 442 unique IDs, no duplicate IDs, 39 TABLE, 39 TABLE DATA, 37 SEQUENCE and 37 SEQUENCE SET, 95 INDEX, 56 CONSTRAINT, and 61 FK CONSTRAINT entries. The source has 37 sequences, 151 indexes, 136 total constraints (39 primary keys, 61 foreign keys, 17 unique and 19 check constraints). PostgreSQL 16 documentation places validated check constraints in the pre-data section ([pg_dump documentation](https://www.postgresql.org/docs/16/app-pgdump.html)). Full definition comparison is recorded in the restore results below. |
| Source identity and snapshot | PASS | Local server address ::1, port 5432, database ai_placement_platform, PostgreSQL 16.13, revision add_faculty_practice_assignments; cluster system identifier 7612714455082792120. The backup manifest snapshot is 2026-10-25T09:49:18.920890+00:00. All 39 current source per-table counts match the captured snapshot counts (6,641 rows including alembic_version; 6,640 application rows). |
| Source schema inventory | PASS | 39 public tables, 395 columns, 151 indexes, 136 constraints, 39 primary keys, 61 validated foreign keys, 37 sequences, no public views/routines/triggers, and plpgsql 1.0. |
| Existing scratch candidate | BLOCKED FOR REUSE | Existing database edi5_restore_verify_20261025 is on the source cluster and has 39 user tables and 6,641 rows. It has no active sessions, but it contains data; it will not be reused or modified. Other existing databases are also excluded. |
| New target identity | PASS | New target edi5_restore_validation_20261025_022d4117 was absent from pg_database and has no application configuration reference. It was created on the positively identified local source cluster at localhost:5432 from template0, with source-matching UTF8 encoding and collation. Its identity and empty state were rechecked immediately before restore. Supabase was not the target. |
| Restore privileges | PASS WITH SCOPE LIMIT | postgres is the only local login role found and has CREATEDB/superuser attributes. The repository's documented local restore procedure uses postgres; no lower-privilege login is configured. This role will be used only with an explicit new scratch database name and pg_restore --no-owner --no-privileges; no --create, --clean, role, or grant operation is planned. |
| Space | PASS | The data directory is on C:, with 20,111,331,328 bytes free at preflight; conservative restore reserve is 117,609,541 bytes. |
| Existing artifacts | PASS | The root-level - archive and the zero-byte Phase 7J failed target were rehashed and will remain untouched. October 10 and October 24 historical backups were separately verified in Phase 7J and will be rechecked after validation. |

The exact pre-restore inventory and artifact metadata are in EDI5_PHASE_7K_20261025_022d4117/pre_restore.json. The root - archive, zero-byte target, all old backups, and the populated existing scratch database are preservation-only artifacts and are not restore targets.

## Planned operations

Expected side effects are limited to creating the one new scratch database and restoring the candidate archive into it. No application, background worker, or service will be configured to use the scratch target. No source, other local database, Supabase database, backup, or asset will be changed.

Database creation statement (targeted to the local postgres maintenance database):

CREATE DATABASE "edi5_restore_validation_20261025_022d4117" WITH TEMPLATE template0 OWNER postgres ENCODING 'UTF8' LC_COLLATE 'English_United States.1252' LC_CTYPE 'English_United States.1252';

Immediately before restore, verify the new database name, owner, cluster identifier, empty application schema, encoding/collation, and zero active sessions.

Exact restore command (password supplied only through the existing local environment, not command arguments or report):

C:/Program Files/PostgreSQL/16/bin/pg_restore.exe --host localhost --port 5432 --username postgres --dbname edi5_restore_validation_20261025_022d4117 --no-password --no-owner --no-privileges --exit-on-error --single-transaction C:/Users/Akshada/AppData/Local/EDI5-Backups/ai_placement_platform_20261025T094836Z_phase7j_verified.dump

This command omits --create and --clean; it connects directly to the verified scratch database and does not drop objects. The archive is from the local source. No migration or application process will run against the scratch database.

## Restore and verification results

**Restore: PASS.** The recorded command exited 0 with no stderr output. It used --single-transaction --exit-on-error --no-owner --no-privileges, explicitly named localhost:5432 and the new scratch database, and omitted --create and --clean. The database remains intact.

| Validation | Result |
|---|---|
| Target after restore | PASS. Database edi5_restore_validation_20261025_022d4117, PostgreSQL 16.13, owner postgres, same verified local cluster system identifier 7612714455082792120; 39 public tables, 6,641 total rows. No other active sessions at final check. |
| Alembic revision | PASS. Source and scratch both add_faculty_practice_assignments. |
| Table inventory and row counts | PASS. All 39 tables and 6,641 rows, including one Alembic revision row, match the backup manifest and current source. No per-table count mismatches. |
| Full-row fingerprints | PASS. Deterministic SHA-256 fingerprints over row_to_json rows ordered by each table primary key (session timezone UTC) matched for 39/39 tables. Row values and row hashes were not printed or stored; only match results and counts were recorded. |
| Columns and indexes | PASS. All 395 column definitions and 151 index definitions match, including partial-index predicates and validity/readiness flags. Every public table has a primary key. No invalid unique indexes. |
| Constraints | PASS with a deparse note. Both sides have 136 constraints: 39 primary keys, 61 foreign keys, 17 unique constraints, and 19 check constraints; all are validated. Names, types, and validation flags match. Four check definitions deparse identically. Fifteen deparse with equivalent varchar-to-text casts; read-only expression checks over each allowed value plus a rejected sentinel confirmed matching behavior for all 15. See constraint_comparison.json and constraint_semantics_check.json. |
| Foreign keys and critical nulls | PASS. 61/61 foreign keys are validated; exact orphan count is zero on source and scratch. FK-column null totals match. Critical null counts match, including student_profiles.department=0, rl_attempt_log FK columns all zero, and coding_problems.blueprint_id=50 on both. |
| Sequences | PASS. All 37 sequence definitions, ownership mappings, last values, and called states match. The next value is above the owned-column maximum for all 37 sequences. |
| Extensions and other objects | PASS. plpgsql 1.0 matches; no public views, routines, or triggers on either side; large-object count is zero on both. Database encoding and collation match. No database-specific role settings were present on either database. |
| ACL/role restoration | NOT VERIFIED. The restore intentionally used --no-owner --no-privileges; object ACL parity and application-role access were not tested. No role or grant was created or changed. |
| Application behavior | NOT RUN. No application process, job, migration, or write test was run against the scratch database. |

### Table-by-table row-count comparison

| Table | Backup snapshot | Source | Scratch | Fingerprint |
|---|---:|---:|---:|---|
| public.admin_question_feedback | 0 | 0 | 0 | MATCH |
| public.advanced_proctoring_events | 425 | 425 | 425 | MATCH |
| public.alembic_version | 1 | 1 | 1 | MATCH |
| public.approved_question_pools | 56 | 56 | 56 | MATCH |
| public.aptitude_attempts | 263 | 263 | 263 | MATCH |
| public.aptitude_questions | 905 | 905 | 905 | MATCH |
| public.aptitude_round_questions | 360 | 360 | 360 | MATCH |
| public.aptitude_topics | 75 | 75 | 75 | MATCH |
| public.assessment_contexts | 183 | 183 | 183 | MATCH |
| public.assessment_policies | 245 | 245 | 245 | MATCH |
| public.assessment_rounds | 562 | 562 | 562 | MATCH |
| public.assessment_sessions | 365 | 365 | 365 | MATCH |
| public.coding_problems | 180 | 180 | 180 | MATCH |
| public.coding_submissions | 9 | 9 | 9 | MATCH |
| public.coding_test_cases | 418 | 418 | 418 | MATCH |
| public.company_blueprints | 45 | 45 | 45 | MATCH |
| public.company_historical_data | 51 | 51 | 51 | MATCH |
| public.company_patterns | 70 | 70 | 70 | MATCH |
| public.competency_evidence_mappings | 52 | 52 | 52 | MATCH |
| public.faculty_practice_assessment_rounds | 9 | 9 | 9 | MATCH |
| public.faculty_practice_assessments | 3 | 3 | 3 | MATCH |
| public.faculty_practice_assignments | 8 | 8 | 8 | MATCH |
| public.faculty_practice_round_attempts | 1 | 1 | 1 | MATCH |
| public.faculty_profiles | 31 | 31 | 31 | MATCH |
| public.generated_question_pools | 64 | 64 | 64 | MATCH |
| public.interview_sessions | 20 | 20 | 20 | MATCH |
| public.interview_turns | 9 | 9 | 9 | MATCH |
| public.mock_drives | 104 | 104 | 104 | MATCH |
| public.proctoring_events | 0 | 0 | 0 | MATCH |
| public.proctoring_violations | 0 | 0 | 0 | MATCH |
| public.refresh_tokens | 0 | 0 | 0 | MATCH |
| public.rl_attempt_log | 263 | 263 | 263 | MATCH |
| public.rl_q_table | 169 | 169 | 169 | MATCH |
| public.rl_sessions | 263 | 263 | 263 | MATCH |
| public.session_problems | 224 | 224 | 224 | MATCH |
| public.student_profiles | 474 | 474 | 474 | MATCH |
| public.tpo_profiles | 93 | 93 | 93 | MATCH |
| public.user_resumes | 41 | 41 | 41 | MATCH |
| public.users | 600 | 600 | 600 | MATCH |

Source snapshot counts are from the Phase 7J manifest captured at 2026-10-25 09:49:18.920890 UTC. Current source counts still match that snapshot, and all source/scratch full-row fingerprints match. This provides data equality evidence for the backup snapshot and the read-only source comparison snapshot.

### Preservation and scope

The October 10 and October 24 original backups still match their recorded size and SHA-256. The Phase 7J root-level - archive, zero-byte failed artifact, and manifests remain unchanged. The earlier populated edi5_restore_verify_20261025 database (39 tables/6,641 rows) was not reused or modified. Only the newly created edi5_restore_validation_20261025_022d4117 database received the restore.

No connection was made to Supabase. DATABASE_URL, .env, application source, external uploads, and app/data/kb.index were not changed. No migrations, cutover, or cleanup occurred. The scratch database is intentionally left intact.

## Tests, files, and final status

- python -m pytest -p no:cacheprovider tests/test_supabase_audit_config.py -q: **14 passed**.
- pg_restore --list and verbose TOC listing: exit 0; 442 unique IDs and no duplicate TOC IDs.
- git diff --check: passed; Git emitted only its existing line-ending warning for requirements.txt. Both audit reports have no trailing whitespace; all four audit JSON files parse successfully.
- No automated application or migration tests were run.

Files created or updated in Phase 7K:
- docs/audits/EDI5_PHASE_7K_SCRATCH_RESTORE_VALIDATION.md
- docs/audits/EDI5_PHASE_7K_20261025_022d4117/pre_restore.json
- docs/audits/EDI5_PHASE_7K_20261025_022d4117/verification.json
- docs/audits/EDI5_PHASE_7K_20261025_022d4117/constraint_comparison.json
- docs/audits/EDI5_PHASE_7K_20261025_022d4117/constraint_semantics_check.json
- docs/audits/EDI5_PHASE_7_LOCAL_TO_SUPABASE_MIGRATION_STATUS.md (Phase 7K section appended)

Initial Git modifications and untracked files were preserved. New Git-visible paths from this phase are the separate report and the Phase 7K audit directory; the Phase 7J root-level - archive was already present at Phase 7K start.

**Phase 7K decision: local backup restore and database schema/data integrity PASS, with the documented check-constraint deparse-only differences.** The October 25 candidate is now **RESTORE-VALIDATED IN LOCAL SCRATCH** for PostgreSQL schema and data. This does not validate Supabase compatibility, ACLs, application behavior, destination ownership, or cutover readiness. Recommended next phase: review Supabase data ownership and migration mapping, then validate against a separately approved isolated staging project. Do not restore to the existing Supabase destination or cut over without a separate explicit authorization.



### Pre-restore target verification (2026-10-25 10:07 UTC)

At the recorded pre-restore check, the new database had been created from template0 and reconnected to before any archive command. It reported database edi5_restore_validation_20261025_022d4117, PostgreSQL 16.13, server address ::1, port 5432, cluster system identifier 7612714455082792120, owner postgres, UTF8, and source-matching collation/ctype. The public schema contained zero tables and there were zero other sessions. This is the same verified local cluster as the source, but a distinct new database. The restore command above named only this target database.


### Final git status (2026-10-25)

The final git status is:

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

The entry for the Phase 7K directory and report are additions from this phase. Earlier modified/untracked paths were preserved; the root-level - archive was present at initial Phase 7K status. No changes were staged.
