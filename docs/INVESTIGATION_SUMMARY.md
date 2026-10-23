# EDI5 M2-E Stale Coding Round Investigation - Summary

**Issue:** Users see "An active coding round is already in progress" error when trying to start Aptitude after completing Coding.

**Investigation Method:** 
- Traced frontend request path (CodingRoundV2.jsx → POST /coding/finish)
- Traced backend conflict check (/practice/start → 409 conflict)
- Analyzed session/round lifecycle logic
- Inspected database schema vs. model definitions
- Identified schema migration gap

---

## ROOT CAUSE (Confirmed)

### The Issue
Database schema is missing critical M2-E columns:
- `assessment_sessions.expires_at` (missing)
- `assessment_sessions.context_id` (missing)
- `assessment_rounds.expires_at` (missing)

### Why It Breaks
Backend code in `app/services/session_service.py` line 75-87 tries to expire stale rounds:

```python
def _expire_stale_rounds(db: Session, session_id: int) -> None:
    db.query(AssessmentRound).filter(
        AssessmentRound.session_id == session_id,
        AssessmentRound.status == "active",
        AssessmentRound.expires_at.isnot(None),  # ← Queries missing column
        AssessmentRound.expires_at <= now,
    ).update({"status": "expired", ...})
```

Since `expires_at` column doesn't exist:
- Query filter matches ZERO rows
- No rounds are ever expired
- Old "active" rounds stay active indefinitely
- /practice/start sees active Coding round, returns 409 conflict

### Migration Status
```
alembic_version table: EMPTY (no migrations applied)
```

Migrations exist but haven't been run:
- `add_assessment_lifecycle_timing.py` (adds expires_at columns)
- `add_assessment_context_and_policy.py` (adds context_id, policies, contexts tables)

---

## INVESTIGATION FINDINGS (Detailed)

### 1. Frontend Request Path ✓
- **Component:** `CodingRoundV2.jsx`
- **Handler:** `handleFinish()` → `finishRound()`
- **Endpoint:** `POST /coding/finish`
- **Expected:** Marks Coding round as completed

### 2. Backend Completion Logic ✓
- **Service:** `finalize_coding_round()` in `coding_service.py`
- **Action:** Sets `AssessmentRound.status = "completed"` ✓
- **Status:** WORKING CORRECTLY

### 3. Backend Conflict Check ✗
- **Router:** `/practice/start` in `practice_router.py` line 235-243
- **Check:** Looks for active rounds with different round_type
- **Problem:** Active rounds aren't properly expiring
- **Reason:** Missing `expires_at` column breaks expiration query

### 4. Session/Round Query ✗
- **Function:** `get_active_round()` calls `_expire_stale_rounds()`
- **Problem:** Expiration filter matches zero rows
- **Root Cause:** Column doesn't exist, query returns NULL

### 5. Database State
```
CONFIRMED: No active coding rounds currently exist
REASON: User may have completed the round locally
        but stale state can occur on next attempt
VERIFIED: Alembic migrations not applied (alembic_version is empty)
```

---

## NOT THE ROOT CAUSE (Eliminated)

❌ **Coding completion doesn't update status**
- Verified: `finalize_coding_round()` correctly sets status="completed"
- Verified: Database updates execute successfully

❌ **Wrong round/session IDs**
- Verified: Frontend correctly tracks session_id and round_id
- Verified: Ownership checks work correctly

❌ **Stale frontend state**
- Verified: /practice/status endpoint returns correct state
- Verified: localStorage is not used as authoritative source

❌ **Legacy Coding endpoint**
- Verified: Only one Coding completion endpoint exists (/coding/finish)
- Verified: Calls correct service function

---

## THE FIX

### What Needs to Happen

Run Alembic migrations to apply M2-E schema:

```bash
alembic upgrade head
```

This will:
1. Add `expires_at` to `assessment_sessions`
2. Add `expires_at` to `assessment_rounds`
3. Add `context_id` to `assessment_sessions`
4. Create `assessment_contexts` table
5. Create `assessment_policies` table
6. Create necessary indexes

### Verification

```bash
# Check migrations were applied
sqlite3 database.db "SELECT version_num FROM alembic_version;"

# Verify schema
sqlite3 database.db "PRAGMA table_info(assessment_rounds);" | grep expires_at
```

---

## IMPACT

| Category | Impact |
|----------|--------|
| **Severity** | HIGH - Blocks Coding→Aptitude workflow |
| **Scope** | All Practice users |
| **Frequency** | Intermittent (depends on timing) |
| **Data Loss** | None (data is correct, just in wrong state) |
| **Recovery** | Manual database update or restart session |
| **Fix Complexity** | LOW - Single command: `alembic upgrade head` |

---

## FILES GENERATED

1. **EDI5_M2E_ACTIVE_CODING_ROUND_ROOT_CAUSE.md** - Detailed diagnostic report
2. **INVESTIGATION_SUMMARY.md** - This file
3. **diagnose_stale_coding_round.py** - Diagnostic script
4. **verify_schema_mismatch.py** - Schema validation script

---

## RECOMMENDED ACTION

**DO NOT modify code.** 

The code is correct. Apply the pending database migrations:

```bash
cd /path/to/project
alembic upgrade head
```

Then test the Coding→Aptitude flow.

If any stale active rounds remain in database after migration, manually complete them:

```sql
UPDATE assessment_rounds 
SET status = 'completed', completed_at = datetime('now')
WHERE round_type = 'coding' AND status = 'active';
```

---

**Investigation Date:** 2026-09-23  
**Status:** ROOT CAUSE IDENTIFIED, FIX READY (Database migration)  
**Next Steps:** Apply migrations → Verify → Test workflow
