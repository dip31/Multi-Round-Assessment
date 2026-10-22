# EDI5 Phase E — Read-Only Database Verification and Schema Drift Audit

- **Audit date:** 2026-10-10
- **Auditor:** EDI5 Phase E read-only audit
- **Repository branch / commit:** `feature/divesh` @ `6c870ed7b8b635b0f07dcdfadae15ab6c024b38e`
- **Scope:** read-only verification of the development database, backup integrity, migration graph, ORM/schema consistency, Phase 4 competency mapping schema, and Phase D test isolation.
- **Constraints honored:** no schema changes, no migration execution, no data modification, no database creation/drop/restore, no file edits outside this report, no credential disclosure.

---

## A. Executive summary

The development database, its verified backup, and the Alembic migration graph are in good health:

- The live database identity matches the baseline exactly: **PostgreSQL 16.13**, database `ai_placement_platform`, revision **`add_competency_mapping_status_4g`**, **35 tables**, **4,978 rows** — identical to the Phase A/B/backup baseline.
- The Alembic graph is **valid**: 31 revision files, 31 unique revision IDs, a single root (`20260924_baseline`), a single head (`add_competency_mapping_status_4g`), no missing parents, no cycles, no duplicate IDs. The Phase 4 chain `add_question_pool_generation_4e → add_competency_evidence_map_4f → add_competency_mapping_status_4g` is present and correctly parented.
- The backup file exists and is structurally intact (`pg_restore --list` succeeds; 35 `TABLE DATA` entries) and its table inventory matches the live DB **exactly (35/35)**.
- Phase 4 competency mapping schema is present and matches intent (table, unique constraint, FKs, lifecycle columns).
- Phase D test isolation is **functionally correct**: normal runtime is unchanged; tests bind to an isolated DB or fail fast; the guard blocks the development database by name; teardown cannot drop the dev/prod DB.

**Most important risks are operational drift, not data loss:**

1. **[HIGH] Large, accumulated model↔database schema drift.** The ORM models and the migration-built database disagree on JSON vs JSONB types (≥9 columns), column nullability (~15 columns), index names (~40 indexes), one foreign key (`coding_problems.blueprint_id`), and several unique constraints. The consequence is that a future `alembic revision --autogenerate` will emit a large, partially destructive churn diff, and the `create_all`-based test database is **not** schema-identical to the development database.
2. **[MEDIUM] Test-isolation hardening gaps.** `EDI5_TESTING` is set with `setdefault` (not forced); the guard is database-**name**-only (cannot detect a differently named production DB); parallel test runs share one fixed test-DB name; and the isolated test DB is built by `create_all`, so it omits `alembic_version`/`refresh_tokens` and carries the drifted model definitions.
3. **[LOW–INFORMATIONAL]** `refresh_tokens` has no ORM model; placeholder credentials remain in tracked config; the legacy 0-byte `database.db` remains in the repo.

No critical (data-loss / corruption / accidental-production-write) issue was found.

---

## B. Environment and identity

| Item | Verified value | Evidence |
|---|---|---|
| DBMS | PostgreSQL 16.13 | `SHOW server_version` |
| Database | `ai_placement_platform` | `SELECT current_database()` |
| Host / port | localhost / 5432 | `inet_server_port()`, settings |
| User (no secret shown) | `postgres` | `SELECT current_user()` |
| Live schema revision | `add_competency_mapping_status_4g` | `SELECT version_num FROM alembic_version`; `alembic current` |
| Repo heads | 1 — `add_competency_mapping_status_4g (head)` | `alembic heads` |
| Application tables | 35 (`public`, BASE TABLE) | `information_schema.tables` |
| Total rows (exact) | 4,978 | exact `count(*)` across all tables |
| Connection config | `app/config/settings.py` → `settings.DATABASE_URL` (`.env`, not committed); engine bound in `app/database/db.py` | file inspection |

Row counts matched the backup manifest exactly per table (e.g. `users=588`, `assessment_contexts=162`, `aptitude_questions=515`, `assessment_rounds=520`, `mock_drives=91`, `company_blueprints=29`, `competency_evidence_mappings=0`).

No discrepancy from the reported baseline. The baseline is confirmed.

---

## C. Backup verification

Backup directory: `D:\Git Projects\Multi-Round-Assessment-backups\`

| Artifact | Size | Status |
|---|---|---|
| `ai_placement_platform_dev_20261010_231634.dump` | 373,132 bytes | exists |
| `database_db_empty_20261010_231634.sqlite` | 0 bytes | exists (record of empty legacy `database.db`) |
| `MANIFEST_ai_placement_platform_dev_20261010_231634.md` | 2,540 bytes | reviewed |

**What was checked (non-destructive):**
- File exists with the size recorded in the manifest.
- `pg_restore --list` **succeeded** (407 output lines; **396 TOC entries, 35 `TABLE DATA` entries** — consistent with the manifest).
- Dump table inventory vs live DB: **35/35 exact match** (no table present in one and absent in the other).
- Manifest content: records source identity, revision, per-table row counts, and a Phase C restore-verification result (`PASS`, restored into a temporary DB that was subsequently dropped).

**What was NOT checked (deliberately):**
- No restore was performed during this audit. The audit instructions permit a deeper restore comparison only with an explicitly authorized, disposable verification database; that authorization was not present, so no database was created. **Row-count consistency and true data equality against the backup were not independently re-verified in this phase**; the manifest documents a prior Phase C restore verification that is taken as reported evidence, not independently reconfirmed here.

**Distinction:**
- **File integrity:** VERIFIED (listable, well-formed custom-format archive).
- **Schema consistency (table/object inventory):** VERIFIED (dump table set == live table set).
- **Row-count consistency:** not independently re-verified this audit (documented in manifest only).
- **Data equality:** **not** verified and **not** claimed. Table-count equality is not data equality.

---

## D. Migration graph

Parsed from `alembic/versions/*.py` (31 files).

| Check | Result |
|---|---|
| Revision files | 31 |
| Unique revision IDs | 31 |
| Roots | 1 — `20260924_baseline` |
| Heads | **1** — `add_competency_mapping_status_4g` |
| Missing parents | none |
| Cycles | none |
| Duplicate IDs | none |
| Parse errors | none |
| DB current revision in repo | yes |
| DB at head | yes |

**Phase 4 chain (verified):**

```
add_competency_mapping_status_4g
  ← add_competency_evidence_map_4f   (file add_competency_evidence_mapping.py)
  ← add_question_pool_generation_4e  (file add_question_pool_generation.py)
  ← mock_drive_round_configs_4d      (file add_mock_drive_round_configurations.py)
  ← add_blueprint_snapshots_4c → add_blueprint_mock_drive_4c → add_company_blueprint_4b
  ← add_company_data_4a → add_mock_drive_ctx_001 → add_mock_drive_001 → fix_role_check_001
  ← add_personalization_001 → b78ed14a3c15 (merge) → add_context_policy_m2e
  ← add_assessment_lifecycle_timing → 7b404c6a0d4f → 545b4e6f20d4 (merge)
  ← add_interview_completion → rebuild_interview_pipeline → add_followup_columns
  ← add_interview_tables → add_advanced_proctoring_events → add_proctoring_events
  ← 20260924_baseline
```

Two merge revisions combine branches: `545b4e6f20d4` (`(add_interview_completion, merge_sp_violations)`) and `b78ed14a3c15` (`(add_context_policy_m2e, add_practice_type_rounds)`), and `mock_drive_round_configs_4d` folds `(add_blueprint_snapshots_4c, aptitude_round_assignments_4c)`. The `aptitude_round_assignments_4c` branch is fully absorbed; it is **not** a second head.

**Upgrade/downgrade review:** No destructive operations found in any `upgrade()` (no `TRUNCATE`, no `DELETE FROM`, no table drops outside `downgrade()`). Destructive-looking calls (`op.drop_table`, `op.drop_column`) occur only in `downgrade()` functions. Data-touching upgrades are additive/backfill only (`add_assessment_context_and_policy.py` seeds policies/context and backfills `assessment_sessions.context_id=1`; `rebuild_interview_pipeline.py` backfills `rl_state` JSON keys).

**Verdict:** migration graph valid; repository head status consistent; database current-revision status consistent. No unresolved graph issue.

---

## E. Model / schema comparison

Comparison method: imported `Base.metadata` (same import surface as Alembic/CONFTEST) and diffed against the live `information_schema`/`pg_catalog` inventory.

**Table set:** model tables = 33; live DB tables = 35.
- In model, not in DB: **none**.
- In DB, not in model: `alembic_version`, `refresh_tokens` (both created by the baseline migration; neither has an ORM model).

**Discrepancy table (representative; aggregate follows):**

| Area | Model / migration | Live DB | Severity | Impact |
|---|---|---|---|---|
| JSON type | `JSONB` (e.g. `assessment_policies.progression_config`, `student_profiles.portfolio_data`, `student_profiles.skills_json`, `user_resumes.parsed_projects/parsed_skills`, `approved_question_pools.extracted_projects/extracted_skills/question_pool`, `interview_turns.behavioral_snapshot`, `proctoring_violations.metadata`) | `json` | Medium | jsonb vs json semantics (operators, indexing, key ordering); autogenerate churn; test DB (create_all) uses jsonb |
| JSON/text type | `Text` (`proctoring_events.event_metadata`, `rl_sessions.q_values`) | `json` | Medium | Model expects text; DB stores json. Serialization/type expectations differ |
| Type | `users.password_hash` `String()` (varchar) | `text` | Low | Affinity only; both unbounded text-like |
| Nullability | Model `NOT NULL` on `created_at`/`updated_at`/`uploaded_at`/`started_at` (users, profiles, assessment_policies, assessment_contexts, assessment_rounds, assessment_sessions, proctoring_events, user_resumes) | DB `nullable = YES` (default `now()`) | Medium | Model stricter than DB; autogenerate churn; test DB differs |
| Nullability | `competency_evidence_mappings.created_at` model nullable | DB `NOT NULL DEFAULT now()` | Low | Opposite direction; inserts still succeed via default |
| Foreign key | `coding_problems.blueprint_id` → `company_blueprints.id` (ondelete SET NULL) present in model | **no FK** in DB (index `ix_coding_problems_blueprint_id` exists) | Medium | Referential integrity not enforced in dev DB; delete of a blueprint won't null the column |
| Index naming | Model default names `ix_<table>_<col>` | DB mostly `idx_<...>` (plus some `ix_`) | Medium | ~40 model indexes not found by name in DB; autogenerate churn |
| Duplicate/overlapping indexes | — | e.g. `assessment_contexts` has both `idx_assessment_contexts_student_id` and `ix_assessment_contexts_student_id` | Low | Redundant index storage/write overhead |
| Unique constraints in DB not in model | — | `aptitude_attempts (round_id, attempt_number)`, `rl_q_table (action, state, user_id)`, `rl_sessions (round_id, step_number)` | Low–Medium | Test DB won't enforce them; behavior divergence |
| Functional/partial unique index | — | `advanced_proctoring_events` (`date_trunc('second', created_at)`), `assessment_rounds` (partial on active status) | Low | DB-only constructs not represented in models |

**Aggregate:** 29 type/nullability differences + ~40 index-name mismatches + 1 missing FK + several DB-only unique constraints/functional indexes.

**Primary risk:** These are not merely cosmetic. Because the test database is created from `Base.metadata.create_all` while the development database is built by migrations, the two schemas are **not equivalent** (different index names/counts, JSONB vs json, FK presence, unique-constraint sets). Tests therefore do not fully validate the production schema. Additionally, a future `--autogenerate` revision will propose a large set of type/index/FK/constraint changes that requires careful human review to avoid unintended destructive DDL.

**Intentional vs defect:** The json-vs-JSONB and index-naming differences are plausibly intentional historical artifacts (baseline migration written by hand with `idx_` names and `sa.JSON`), but they are inconsistent with the current models and should be reconciled deliberately. The missing `coding_problems.blueprint_id` FK is most likely an oversight (the model and a later migration both imply it). This audit does not assert intent; it records the divergence with evidence.

---

## F. Phase 4 verification

| Item | Result |
|---|---|
| `generated_question_pools` table | present; `blueprint_id` FK → `company_blueprints` (CASCADE), unique `(blueprint_id, blueprint_version, round_type)`, `content` jsonb |
| Generated-provenance columns on `aptitude_questions` / `coding_problems` | present (`source`, `source_batch`, `company_name`, `target_role`, `blueprint_id`, `blueprint_version`) |
| Blueprint snapshots | `mock_drives.blueprint_snapshot`, `assessment_contexts.blueprint_snapshot` present |
| Mock Drive round configs | `mock_drives.round_configurations` jsonb present |
| `competency_evidence_mappings` table | present |
| Intended unique constraint `(evidence_type, evidence_id, competency_id)` | present as `uq_competency_evidence_mapping` |
| Mapping columns (candidate/context/session/round/source/blueprint_version/raw_metric) | present; `raw_metric` jsonb NOT NULL; FKs `candidate_id`/`context_id`/`session_id`/`round_id` all CASCADE as intended |
| Lifecycle fields on `assessment_contexts` | `competency_mapping_status` varchar(20) NULL, `competency_mapping_error` text NULL, `competency_mapping_attempted_at` timestamp NULL, `competency_mapping_completed_at` timestamp NULL — all match the `4g` migration |
| Aggregate lifecycle status counts | `NULL`=158, `not_applicable`=4; no `pending`/`completed`/`failed` rows |
| `competency_evidence_mappings` rows | 0 |

Only minor note: `competency_evidence_mappings.created_at` model nullability (True) differs from DB (`NOT NULL`), a display-level drift with no runtime effect.

No candidate personal data was inspected or reported.

---

## G. Test isolation review

Reviewed: `app/database/db.py`, `tests/conftest.py`, `tests/test_db_isolation_guard.py`, `docs/DATABASE_WORKFLOW.md`, `.gitignore`.

| # | Check | Result |
|---|---|---|
| 1 | `EDI5_TESTING=1` set early enough | **Partially.** Set at `conftest.py` import (before app imports) — good. But uses `os.environ.setdefault`, so a pre-set `EDI5_TESTING` value (e.g. `0`) would not be overridden. |
| 2 | Test config requires explicit `TEST_DATABASE_URL` | Yes for any DB-touching test (bound via env); SQLite-override tests legitimately need none. |
| 3 | Missing config fails fast | Yes — guarded `SessionLocal` raises `RuntimeError` with actionable guidance (verified). |
| 4 | Name/identity guard blocks dev DB | Yes for the known name `ai_placement_platform` (verified). **Name-only** — a differently named production DB would not be rejected. |
| 5 | All engine/session paths respect guard | Yes within the app: the only application engine is in `app/database/db.py`; `alembic/env.py` is not used at test time. No test references `settings.DATABASE_URL`. |
| 6 | No silent fallback to dev | Yes — guard path raises; no code path defaults to `settings.DATABASE_URL` under testing. |
| 7 | Teardown cannot drop dev/prod | Yes — teardown re-asserts `assert_isolated_test_database(test_url)` before `DROP DATABASE ... WITH (FORCE)`, and only drops `database_name(test_url)`. |
| 8 | Parallel runs cannot share/drop the same test DB | **No.** The test DB name is fixed (`ai_placement_platform_test`); concurrent runs (e.g. xdist) would drop/recreate each other's DB. No worker-unique naming. |
| 9 | No bypass via direct engine/session | Yes — every test-created engine in `tests/` is SQLite in-memory; direct `SessionLocal` imports resolve to the test-bound factory. |
| 10 | Normal runtime unchanged | Yes — with `EDI5_TESTING` unset, engine resolves to `ai_placement_platform` @ localhost (verified). |

**Test-DB fidelity gap:** the isolated DB is built from `Base.metadata.create_all`, yielding **33 tables** vs the dev DB's **35** (missing `alembic_version` and `refresh_tokens`) and carrying the drifted model definitions (JSONB, model index names, model-declared FK). This is a fidelity limitation, not an isolation failure.

---

## H. Findings and remediation plan

Severity: Critical / High / Medium / Low / Informational.

### High

**H-1 — Accumulated model↔database schema drift.**
- Evidence: 29 type/nullability differences, ~40 index-name mismatches, 1 missing FK (`coding_problems.blueprint_id`), DB-only unique/functional indexes (Section E).
- Risk: a future `alembic revision --autogenerate` produces a large, partially destructive diff; the `create_all` test database is not schema-equivalent to the development database, so tests under-validate production schema.
- Recommended action: reconcile in a dedicated, reviewed migration effort — decide the canonical type (json vs jsonb), align nullable/defaults, standardize index names, restore the missing FK, and represent DB-only constraints in models. Verify with `alembic check` before/after. Do **not** autogenerate blindly.
- Follow-up: new phase (schema reconciliation), after owner confirmation of intended types.

### Medium

**M-1 — `EDI5_TESTING` not forced.** `os.environ.setdefault` allows a pre-existing value to disable isolation.
- Action: set `os.environ["EDI5_TESTING"] = "1"` unconditionally in `conftest.py`.
- Follow-up: Phase D follow-up (small).

**M-2 — Guard is name-only.** Cannot detect a production DB whose name differs from the dev name; no host/port/identity pinning.
- Action: optionally reject known non-test hosts or require an explicit `EDI5_ALLOW_TEST_DB` acknowledgement; document that the guard is name-based.
- Follow-up: Phase D follow-up.

**M-3 — Parallel test DB collision.** Fixed test-DB name; concurrent runs clobber each other.
- Action: derive a per-run/worker suffix (e.g. `ai_placement_platform_test_<pid>`), or guard against concurrent use.
- Follow-up: Phase D follow-up.

**M-4 — Nullable/type drift on timestamp columns** (models NOT NULL vs DB nullable; `competency_evidence_mappings.created_at` inverse).
- Action: fold into H-1 reconciliation.
- Follow-up: schema reconciliation.

**M-5 — Test-DB fidelity gap** (`create_all` omits `alembic_version`/`refresh_tokens`, uses model JSONB/index names).
- Action: prefer running migrations against the isolated test DB (or apply `create_all` plus a post-step to add migration-only objects) so tests exercise the migrated schema.
- Follow-up: Phase D follow-up / schema reconciliation.

### Low

**L-1 — `refresh_tokens` has no ORM model.** Created by the baseline migration; referenced only in a docstring; not used by auth code (access-token-only login). Test DB lacks it.
- Action: confirm it is intentionally model-less/unused; either add a model or document/remove intentionally.

**L-2 — Placeholder credentials in tracked config.** `alembic.ini` and `settings.py` ship `postgresql://postgres:password@localhost/...`. `.env.example` contains the same placeholder pattern.
- Action: acceptable as placeholders, but consider removing working-url defaults to avoid accidental use.

**L-3 — Legacy `database.db` (0 bytes) remains in the repo root** (now gitignored, untracked). Referenced only by legacy root scripts.
- Action: leave (history-preserving) or delete in a separate cleanup task; do not touch during audit.

**L-4 — DB-only unique/functional indexes not represented in models** (`aptitude_attempts`, `rl_q_table`, `rl_sessions`, `advanced_proctoring_events`, `assessment_rounds` partial).
- Action: fold into H-1.

### Informational

- **I-1:** `dynamic_interviewers` (named in the audit brief) does not exist in the database or the codebase. Likely renamed or never implemented; not a defect.
- **I-2:** Backup restore-verification is documented in the manifest (Phase C PASS); it was **not** independently reproduced during this audit (no restoration permitted to avoid side effects).
- **I-3:** `alembic/env.py` imports a subset of model modules but relies on the `app.models` package `__init__` (executed on first submodule import) to populate `Base.metadata`; current behavior is correct but implicit.
- **I-4:** The working tree is heavily modified (108 changed/untracked entries, pre-existing plus Phase D). This audit made no changes to those files.

---

## I. Verification limitations

- **Backup data equality / row-count equality were not independently re-verified.** Re-verification would require restoring into a disposable database; per the strict constraints this was not authorized, so only file integrity (`pg_restore --list`) and table-inventory equality were confirmed. The manifest's Phase C restore results are relied upon as recorded evidence.
- **The isolation guard cannot be proven to block a differently named production database** (name-only comparison). Confirming this would require a policy change, not an audit action.
- **Parallel-run collision is reasoned from configuration**, not reproduced (running it would create/drop databases beyond the single isolated test DB).
- **`alembic current` opened a read-only connection** to the development database to read `alembic_version`; no write occurred.
- **Intent of schema drift items (json vs jsonb, index naming) is unconfirmed** and requires owner/architecture input before remediation.
- No ORM models, services, routers, tests, or configuration files were modified; no schema, migration, or data changes were made; the verified backup and manifest were not modified.

---

### Evidence appendix (read-only commands / scripts used)

- `git rev-parse`, `git status --short`, `git diff` (preflight) — no writes.
- Raw SQLAlchemy read-only inventory of the dev DB (`information_schema`, `pg_catalog`, exact `count(*)`) — temp script only.
- `alembic heads`, `alembic current` (read-only).
- `pg_restore --list` on the backup (no DB connection).
- Static parse of `alembic/versions/*.py` for the revision graph.
- Metadata-vs-DB diff via `Base.metadata` (read-only).
- Config inspection: `app/config/settings.py`, `app/database/db.py`, `alembic/env.py`, `alembic.ini`, `tests/conftest.py`, `.gitignore`, `.env.example`, `docs/DATABASE_WORKFLOW.md`.

**No remediation was performed. Awaiting separate approval before any fix.**
