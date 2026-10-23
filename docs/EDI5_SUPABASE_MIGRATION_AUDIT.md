# EDI5 Supabase Migration Audit Report

**Date:** 2026-10-21  
**Repository:** D:\Projects\EDI 4\Multi-Round-Assesment-v8n  
**Auditor:** Senior Backend Engineer / PostgreSQL Migration Specialist

---

## 1. Executive Summary

This audit examines the current database configuration, migration history, and schema state to determine the correct path for migrating from the current local database setup to Supabase PostgreSQL.

**Key Finding:** The project has **multiple database configurations in use**:
- **Production/Development default:** PostgreSQL (configured in `.env` and `alembic.ini`)
- **Local testing fallback:** SQLite (`database.db`) with only 2 of ~30 migrations applied
- **Historical backup:** PostgreSQL dump from 2026-09-16 (`EDI5_phase0_baseline_2026-09-16.dump`)

**Recommendation:** Use the **Alembic migration chain** as the authoritative schema source and apply it to a fresh Supabase PostgreSQL database. The SQLite database is not the source of truth. The PostgreSQL backup is outdated and should not be restored.

---

## 2. Current Database Configuration Analysis

### 2.1 Environment Configuration (`.env`)

```ini
DATABASE_URL=postgresql://postgres:Firstiqoo%402023@localhost/ai_placement_platform
```

- **Type:** PostgreSQL
- **Host:** localhost
- **Database:** ai_placement_platform
- **Authentication:** Password-based

### 2.2 Alembic Configuration (`alembic.ini`)

```ini
sqlalchemy.url = postgresql://postgres:password@localhost/ai_placement_platform
```

- Fallback URL (overridden at runtime by `alembic/env.py` using `settings.DATABASE_URL`)
- Target: PostgreSQL

### 2.3 Settings (`app/config/settings.py`)

```python
DATABASE_URL: str = "postgresql://postgres:password@localhost/ai_placement_platform"
```

- Default points to local PostgreSQL
- Overridden by `.env` at runtime

### 2.4 SQLite Database (`database.db`)

- **Size:** 262,144 bytes
- **Tables:** 24 tables (missing many from full schema)
- **Alembic versions applied:** Only 2 (`add_assessment_lifecycle_timing`, `add_context_policy_m2e`)
- **State:** Incomplete, used only for local testing fallback

### 2.5 PostgreSQL Backup (`EDI5_phase0_baseline_2026-09-16.dump`)

- **Size:** 216,950 bytes
- **Format:** PostgreSQL custom dump (pg_dump)
- **Date:** 2026-09-16
- **Contents:** Complete schema with functions, triggers, and data
- **Status:** **Outdated** - predates many migrations (baseline is 2026-09-24)

---

## 3. Migration History Analysis

### 3.1 Alembic Revision Graph

The migration history has **multiple merge points and branches**:

```
20260924_baseline (orphaned baseline) ──┐
                                         ├── becbadd33c98 (merge) ── add_dynamic_interviewers_table ── 529895692ee9 ── ac810655180b ── f4e2a1b8c3d5 ── f1ded62ef3b4 (HEAD)
add_proctoring_events ── ... ── 545b4e6f20d4 (merge) ──┬── 7b404c6a0d4f ── ...
                                                      └── add_practice_type_rounds ── ...
```

**Current HEAD:** `f1ded62ef3b4` (add_transcript_finalization_fields_to_interview_sessions)

**Total migrations:** ~30 migration files in `alembic/versions/`

### 3.2 Key Migration Branches

1. **Baseline branch:** `20260924_baseline` - Consolidated schema creation (orphaned)
2. **Incremental chain:** `add_proctoring_events` → ... → `f1ded62ef3b4` (current head)
3. **Merge points:** Multiple merges to resolve parallel development branches

### 3.3 SQLite Migration State

The SQLite database has only **2 migrations applied** from the incremental chain:
- `add_assessment_lifecycle_timing` (expires_at columns)
- `add_context_policy_m2e` (assessment_policies, assessment_contexts tables)

This confirms SQLite is **not the production database** and is significantly behind.

---

## 4. Schema Source of Truth

### 4.1 Authoritative Source: SQLAlchemy Models + Alembic Migrations

The **SQLAlchemy ORM models** in `app/models/` define the current expected schema:
- `user.py` - Users, roles
- `assessment.py` - Sessions, rounds, contexts, policies
- `interview.py` - Interview sessions, turns, conversations, messages, competencies
- `coding.py` - Problems, test cases, submissions, session_problems
- `aptitude.py` - Topics, questions, attempts, RL sessions
- `proctoring.py` - Basic proctoring events
- `advanced_proctoring.py` - Advanced proctoring with CV/audio
- `rl.py` - Q-table, attempt log
- `profile.py` - Student/faculty/TPO profiles, resumes
- `session_problem.py` - Session-problem assignments
- `admin_question_feedback.py` - Question review workflow

### 4.2 Baseline Migration vs Incremental Chain

The `20260924_baseline_complete_schema.py` migration creates **all tables in one step** and matches the current SQLAlchemy models closely. However, it's an **orphaned branch** (no downstream migrations connect to it properly).

The **incremental chain** (from `add_proctoring_events` to `f1ded62ef3b4`) is the **actual applied history** for PostgreSQL environments.

### 4.3 create_database_schema.sql

This SQL file appears to be a **manual dump** of the expected schema (generated from models). It includes:
- All tables with proper constraints
- Triggers for `updated_at`
- Default data (assessment policy)
- Sequence resets

**Verdict:** Useful as a reference but not authoritative. The Alembic incremental chain + models are authoritative.

---

## 5. Migration Compatibility Assessment

### 5.1 PostgreSQL-Specific Features Used

| Feature | Used In | Compatible with Supabase |
|---------|---------|-------------------------|
| `postgresql.JSONB` | Many tables | ✅ Yes |
| `postgresql.ARRAY` | `coding_problems.tags` | ✅ Yes |
| `postgresql.UUID` | Not used | N/A |
| `GIN indexes` | `advanced_proctoring_events.event_metadata` | ✅ Yes |
| `Partial indexes` | `assessment_sessions` (one active per user) | ✅ Yes |
| `CHECK constraints` | Multiple tables | ✅ Yes |
| `Triggers` | `update_updated_at_column()` | ✅ Yes |
| `PL/pgSQL functions` | `calculate_session_risk_score` | ✅ Yes |
| `SERIAL/IDENTITY` | All primary keys | ✅ Yes |

### 5.2 SQLite-Only Operations in Migrations

**Found in `apply_migrations_sqlite.py` (manual script, not Alembic):**
- `DATETIME` type instead of `TIMESTAMP WITH TIME ZONE`
- `JSON` type instead of `JSONB`
- Partial index syntax differences
- No foreign key enforcement by default

**Alembic migrations:** All use PostgreSQL-compatible SQLAlchemy constructs. No raw SQLite-only SQL found in Alembic migrations.

### 5.3 Missing Dependencies / Unsafe Operations

| Migration | Issue | Severity |
|-----------|-------|----------|
| `rebuild_interview_pipeline` | Raw `ALTER COLUMN ... TYPE JSONB USING ...` | Medium - PostgreSQL-specific cast |
| `ac810655180b` | Creates `student_competencies` without unique constraint initially | Low - fixed in `f4e2a1b8c3d5` |
| `20260924_baseline` | Uses `sa.text('NOW()')` for server_default | Low - works in PG |
| Several migrations | Use `postgresql.JSONB(astext_type=sa.Text())` | Low - deprecated but functional |

---

## 6. Required PostgreSQL Extensions

Based on schema analysis:

1. **`uuid-ossp`** - Referenced in `create_database_schema.sql` but not used in models
2. **`pg_trgm`** - Referenced in `create_database_schema.sql` but not used in models
3. **No extensions strictly required** by current SQLAlchemy models

**Recommendation:** Enable `uuid-ossp` and `pg_trgm` in Supabase for future flexibility.

---

## 7. Migration Heads and Consistency

### 7.1 Current State

- **Single HEAD:** `f1ded62ef3b4` ✅
- **No active multiple heads** (merged via `becbadd33c98`)
- **Baseline branch orphaned** but not conflicting

### 7.2 ORM vs Migration Consistency

| Table | In Models | In Baseline Migration | In Incremental Chain | Status |
|-------|-----------|----------------------|---------------------|--------|
| users | ✅ | ✅ | ✅ (via baseline ref) | Consistent |
| student_profiles | ✅ | ✅ | ✅ (7b404c6a0d4f) | Consistent |
| assessment_sessions | ✅ | ✅ | ✅ | Consistent |
| assessment_rounds | ✅ | ✅ | ✅ | Consistent |
| interview_sessions | ✅ | ✅ | ✅ | Consistent |
| interview_turns | ✅ | ✅ | ✅ | Consistent |
| interview_conversations | ✅ | ✅ | ✅ (ac810655180b) | Consistent |
| interview_messages | ✅ | ✅ | ✅ (ac810655180b) | Consistent |
| interview_question_analysis | ✅ | ✅ | ✅ (ac810655180b) | Consistent |
| student_competencies | ✅ | ✅ | ✅ (ac810655180b + f4e2a1b8c3d5) | Consistent |
| competency_evidence | ✅ | ✅ | ✅ (ac810655180b) | Consistent |
| dynamic_interviewers | ✅ | ✅ | ✅ (add_dynamic_interviewers_table) | Consistent |
| proctoring_violations | ✅ | ✅ | ✅ (add_proctoring_violations) | Consistent |
| advanced_proctoring_events | ✅ | ✅ | ✅ (add_advanced_proctoring_events) | Consistent |
| coding_problems | ✅ | ✅ | ✅ | Consistent |
| session_problems | ✅ | ✅ | ✅ (add_session_problems) | Consistent |
| rl_q_table | ✅ | ✅ | ✅ (baseline) | Consistent |
| rl_attempt_log | ✅ | ✅ | ✅ (baseline) | Consistent |

**Verdict:** Models and incremental migration chain are consistent. The baseline migration is a snapshot that matches current models.

---

## 8. Backup Relevance Assessment

### 8.1 PostgreSQL Backup (`EDI5_phase0_baseline_2026-09-16.dump`)

- **Date:** 2026-09-16
- **Schema version:** Pre-dates baseline migration (2026-09-24)
- **Contains:** Functions (`calculate_session_risk_score`), triggers, complete schema
- **Data:** Likely contains test/development data

**Assessment:** 
- ❌ **Not suitable as migration source** - older than current schema
- ❌ **Cannot restore directly** - would downgrade schema
- ✅ **Useful for reference** - contains PG functions not in Alembic migrations
- ⚠️ **If data migration needed:** Extract data only, not schema

---

## 9. Blockers and Risks

### 9.1 Identified Blockers

| Blocker | Description | Resolution |
|---------|-------------|------------|
| Supabase credentials not configured | No Supabase DATABASE_URL in `.env` | User must provide Supabase connection string |
| Multiple merge points in history | Complex migration graph | Use incremental chain from `add_proctoring_events` to HEAD |
| Orphaned baseline migration | `20260924_baseline` not connected to main chain | Ignore; use incremental chain |
| PG functions in backup not in migrations | `calculate_session_risk_score`, `update_updated_at_column` | Add to migration or create post-migration |

### 9.2 Risks

1. **Alembic version table conflict** - If Supabase DB has existing `alembic_version`, must resolve
2. **Partial index syntax** - Supabase supports but verify
3. **Trigger/function migration** - Not in Alembic, need manual handling
4. **Sequence values** - Must reset after data import if applicable

---

## 10. Recommended Migration Path

### Phase A: Audit (COMPLETE)
✅ This document

### Phase B: Preparation
1. **Verify Alembic chain can run cleanly** on empty PostgreSQL
2. **Create test migration** on local PostgreSQL to validate
3. **Extract PG functions** from backup into a new migration
4. **Prepare Supabase-specific migration** for extensions if needed

### Phase C: Supabase Prerequisites
1. Create Supabase project
2. Get connection string (direct connection for migrations)
3. Configure `.env.supabase` with Supabase DATABASE_URL
4. **Do not use transaction pooler** for migrations (use direct connection)

### Phase D: Target Verification
1. Connect to Supabase, verify empty database
2. Confirm `public` schema is target
3. Verify no existing `alembic_version` table

### Phase E: Schema Migration
1. Run `alembic upgrade head` against Supabase
2. Verify all tables created
3. Apply PG functions migration (from backup)
4. Verify `alembic_version` shows `f1ded62ef3b4`

### Phase F: Data Migration (if required)
- **Scope clarification needed:** Fresh schema only, or data transfer?
- If data transfer: Use `pg_dump --data-only` from local PG → `pg_restore` to Supabase
- **Do not use SQLite as source**

### Phase G: Backend Configuration
1. Update `.env.example` with Supabase placeholders
2. Document local vs Supabase switching
3. Keep SQLAlchemy/alembic unchanged

### Phase H: Verification
1. Backend startup test
2. ORM model import test
3. CRUD operations test
4. Run existing test suite

### Phase I: Documentation
1. Create `EDI5_SUPABASE_MIGRATION_REPORT.md`
2. Document rollback procedures

---

## 11. Next Steps

**Immediate action required from user:**
1. ✅ Create Supabase project
2. ✅ Provide Supabase **direct connection string** (not pooler) for migrations
3. ✅ Confirm: **Fresh schema only** or **full data migration**?

**Local work I can complete now:**
1. Validate Alembic chain on local PostgreSQL (if available)
2. Create migration for PG functions from backup
3. Prepare `.env.example` updates
4. Write verification scripts

---

## Appendix: Migration File Inventory

| File | Revision | Parent | Description |
|------|----------|--------|-------------|
| `20260924_baseline_complete_schema.py` | `20260924_baseline` | (base) | Consolidated baseline (orphaned) |
| `add_proctoring_events.py` | `add_proctoring_events` | (base) | Basic proctoring events |
| `add_advanced_proctoring_events.py` | `add_advanced_proctoring_events` | `add_proctoring_events` | Advanced proctoring |
| `add_interview_tables.py` | `add_interview_tables` | `add_advanced_proctoring_events` | Interview core tables |
| `add_followup_columns.py` | `add_followup_columns` | `add_interview_tables` | Follow-up support |
| `rebuild_interview_pipeline.py` | `rebuild_interview_pipeline` | `add_followup_columns` | RL state, final_score, etc. |
| `add_admin_question_feedback.py` | `add_admin_question_feedback` | `rebuild_interview_pipeline` | Question review |
| `add_session_problems.py` | `add_session_problems` | `rebuild_interview_pipeline` | Coding assignments |
| `add_proctoring_violations.py` | `add_proctoring_violations` | `add_interview_tables` | Interview violations |
| `add_role_detection.py` | `add_role_detection` | `rebuild_interview_pipeline` | Role detection field |
| `merge_heads_add_session_problems_and_violations.py` | `merge_sp_violations` | (merge) | Merge violations + session_problems |
| `add_interview_completion_fields.py` | `add_interview_completion` | `rebuild_interview_pipeline` | Status, completion fields |
| `545b4e6f20d4_merge_heads.py` | `545b4e6f20d4` | (merge) | Merge completion + violations |
| `add_practice_type_to_rounds.py` | `add_practice_type_rounds` | `545b4e6f20d4` | Practice type field |
| `7b404c6a0d4f_add_profile_tables_and_resume_columns.py` | `7b404c6a0d4f` | `545b4e6f20d4` | Profile tables + resume cols |
| `add_assessment_lifecycle_timing.py` | `add_assessment_lifecycle_timing` | `7b404c6a0d4f` | Expires_at, unique indexes |
| `add_assessment_context_and_policy.py` | `add_context_policy_m2e` | `add_assessment_lifecycle_timing` | Context/policy tables |
| `b78ed14a3c15_merge_practice_type_and_context_policy.py` | `b78ed14a3c15` | (merge) | Merge practice + context |
| `add_personalization_fields.py` | `add_personalization_001` | `b78ed14a3c15` | Personalization metadata |
| `fix_users_role_check_constraint.py` | `fix_role_check_001` | `add_personalization_001` | Role check constraint |
| `link_interviews_to_assessment_rounds.py` | `link_interview_rounds` | `fix_role_check_001` | Round FK on interview_sessions |
| `add_interviewer_id_to_interview_sessions.py` | `add_interviewer_id_001` | `link_interview_rounds` | Interviewer persona |
| `becbadd33c98_merge_heads.py` | `becbadd33c98` | (merge) | Merge baseline + interviewer |
| `add_dynamic_interviewers_table.py` | `add_dynamic_interviewers_table` | `becbadd33c98` | Dynamic interviewer table |
| `529895692ee9_fix_tables.py` | `529895692ee9` | `add_dynamic_interviewers_table` | Fix tables |
| `ac810655180b_add_question_id_to_interview_turns_and_.py` | `ac810655180b` | `529895692ee9` | Question ID + analysis tables |
| `f4e2a1b8c3d5_add_unique_constraint_to_student_competencies.py` | `f4e2a1b8c3d5` | `ac810655180b` | Unique constraint |
| `f1ded62ef3b4_add_transcript_finalization_fields_to_.py` | `f1ded62ef3b4` | `f4e2a1b8c3d5` | Transcript finalization (HEAD) |

---

**End of Audit Report**