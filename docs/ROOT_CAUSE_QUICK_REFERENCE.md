# EDI5 M2-E Stale Coding Round - Quick Reference

## THE PROBLEM
```
User Error: "An active coding round is already in progress. 
            Please complete or finish it before starting a aptitude round."
HTTP 409 on POST /practice/start
```

## ROOT CAUSE
Database schema missing M2-E columns → Round expiration logic broken → Rounds stay "active"

## PROOF
```bash
python verify_m2e_migration_status.py
# Output shows:
# ❌ MISSING COLUMNS: {'expires_at', 'context_id'} in assessment_sessions
# ❌ MISSING COLUMNS: {'expires_at'} in assessment_rounds
# ❌ NO MIGRATIONS APPLIED (alembic_version is empty)
```

## THE FIX
```bash
alembic upgrade head
```

That's it. One command applies all pending migrations.

## WHY IT BROKE
1. M2-E code uses `expires_at` column for round expiration
2. M2-E code written but database not migrated
3. Expiration query in `_expire_stale_rounds()` filters on missing column
4. Filter matches zero rows
5. Stale rounds never expire
6. /practice/start sees stale "active" coding round → 409 conflict

## CODE LOCATION
- **Query (broken):** `app/services/session_service.py` line 75-87
- **Check (broken):** `app/modules/practice/routers/practice_router.py` line 235-243

## VERIFICATION
After running `alembic upgrade head`, verify:

```bash
# Check schema has expires_at
sqlite3 database.db "PRAGMA table_info(assessment_rounds);" | grep expires_at

# Should output:
# 8|expires_at|DATETIME|0||0
```

## NOT A CODE BUG
- ✓ Completion endpoint works correctly (finalize_coding_round)
- ✓ Practice start logic is correct
- ✓ Frontend code is correct
- ❌ Database schema hasn't been migrated

## MIGRATION FILES
- `alembic/versions/add_assessment_lifecycle_timing.py` (adds expires_at)
- `alembic/versions/add_assessment_context_and_policy.py` (adds context_id, tables)

## STATUS
- **Investigation:** ✓ COMPLETE - Root cause identified
- **Fix:** ✓ READY - Just run migration
- **Testing:** Pending - After migration applied
- **Code Changes:** ✗ NONE NEEDED - Schema only
- **Data Loss:** ✗ NONE - Backward compatible

---

**TL;DR:** Run `alembic upgrade head`. No code changes needed.
