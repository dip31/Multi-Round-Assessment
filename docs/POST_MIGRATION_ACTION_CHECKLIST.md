# Post-Migration Action Checklist

## Immediate Actions Required

### 1. Restart Backend Server
```bash
# Stop the currently running backend
# (Ctrl+C if running locally)

# Restart the backend
uvicorn app.main:app --reload
# or if using different entry point:
python -m uvicorn app.main:app --reload
```

**Why:** New database connection must be established to see the migrated schema.

---

## 2. Test the Core Workflow

### 2.1 Test Coding → Aptitude Transition
```
Step 1: Open browser, go to Dashboard
Step 2: Select "Coding Practice"
Step 3: Click "Start Coding"
Step 4: Submit or finish the coding round
Step 5: Click "Finish" or navigate back to dashboard
Step 6: Select "Aptitude (MCQ)" 
Step 7: Expected: Success screen with aptitude questions
        NOT Expected: "An active coding round is already in progress"
```

**If Success ✓**
- The fix is working correctly
- The expiration logic is now functioning
- Proceed to "Verification Steps"

**If Failed ✗**
- Check application logs for errors
- Check database connectivity
- Review `/practice/start` response (should not be 409)
- See "Troubleshooting" section below

### 2.2 Test Full Practice Session
```
Step 1: Start Coding round
Step 2: Complete 2-3 problems
Step 3: Click "Finish Coding"
Step 4: Start Aptitude round
Step 5: Answer 2-3 questions
Step 6: Click "Finish Aptitude"
Step 7: Start Interview round
Step 8: Go through interview questions
Step 9: Complete interview
Step 10: View results
```

**Expected:** All transitions succeed without 409 conflicts

---

## 3. Verification Steps

### 3.1 Check Application Logs
```
When starting backend, you should see:
  ✓ Database connection successful
  ✓ No "column not found" errors
  ✓ No "table not found" errors
  ✗ DO NOT see: SQLAlchemy errors about expires_at
```

### 3.2 Database Query Check
```bash
sqlite3 database.db

# Run these queries:
SELECT COUNT(*) FROM alembic_version;
# Expected output: 2

SELECT expires_at FROM assessment_rounds LIMIT 1;
# Expected output: (NULL initially, will populate on new sessions)

SELECT context_id FROM assessment_sessions LIMIT 1;
# Expected output: 1 (or NULL for very old sessions)
```

### 3.3 Frontend Console Check
Open browser Developer Tools (F12) and check Console tab:
```
✓ No "404 Not Found" errors
✓ No "500 Internal Server Error"  
✓ No SQLAlchemy/database errors
✓ Network requests show 2xx status codes
```

### 3.4 API Endpoint Verification
```bash
# Test /practice/status endpoint
curl -H "Authorization: Bearer <your_token>" \
     http://localhost:8000/practice/status

# Should return 200 with session data
# NOT 500 or 404
```

---

## 4. Data Validation

### 4.1 Check Default Context
```sql
SELECT id, mode, purpose, policy_id, status 
FROM assessment_contexts 
WHERE id = 1;

-- Expected:
-- id: 1
-- mode: practice
-- purpose: legacy
-- policy_id: 1
-- status: active
```

### 4.2 Check Default Policies
```sql
SELECT id, name, progression_mode FROM assessment_policies;

-- Expected:
-- id: 1, name: Legacy Practice Policy, progression_mode: sequential
-- id: 2, name: Practice Policy, progression_mode: independent
```

### 4.3 Check Session Backfill
```sql
SELECT COUNT(*) FROM assessment_sessions WHERE context_id IS NOT NULL;

-- Should show all existing sessions have context_id = 1
```

---

## 5. Rollout Plan

### Phase 1: Local Testing (Immediate)
- [ ] Restart backend
- [ ] Run test workflow 2.1 (Coding → Aptitude)
- [ ] Verify no errors in logs
- [ ] Check database queries in 3.2

### Phase 2: Full Testing (Next 30 minutes)
- [ ] Run full session test 2.2
- [ ] Test with multiple users if available
- [ ] Test multiple consecutive sessions
- [ ] Verify frontend shows no errors

### Phase 3: Deployment (If applicable)
- [ ] Backup production database: `cp database.db database.db.backup`
- [ ] Run migrations on production database
- [ ] Restart production backend
- [ ] Monitor logs for errors
- [ ] Have rollback plan ready

---

## 6. Troubleshooting

### Issue: Still getting 409 conflict when starting Aptitude
**Possible Causes:**
1. Backend not restarted (still using old schema)
2. Database connection pool not refreshed
3. User session still has stale "active" coding round in old part of code

**Solutions:**
```bash
# Force restart backend (kill all Python processes if needed)
pkill -f "uvicorn"
sleep 2
uvicorn app.main:app --reload

# OR on Windows:
Get-Process python | Stop-Process -Force
python -m uvicorn app.main:app --reload
```

### Issue: Database errors like "no such column: expires_at"
**Cause:** Migration didn't apply correctly

**Solution:**
```bash
# Check what was applied
python verify_m2e_migration_status.py

# If migrations weren't applied:
python apply_migrations_sqlite.py

# Restart backend
```

### Issue: Foreign key constraint errors
**Cause:** Context not assigned to existing sessions

**Solution:**
```sql
UPDATE assessment_sessions SET context_id = 1 WHERE context_id IS NULL;
```

### Issue: "Assessment context table does not exist"
**Cause:** Incomplete migration

**Solution:**
```bash
python apply_migrations_sqlite.py
# Then restart backend
```

---

## 7. Performance Considerations

The new schema includes indexes that improve query performance:
- `one_active_session_per_user`: Speeds up user session lookups
- `one_active_round_per_session`: Speeds up active round detection

These indexes also enforce data integrity (unique constraints on active sessions/rounds).

---

## 8. Monitoring

### Watch For
- [ ] Unusual database query times (queries should be <100ms)
- [ ] Memory usage (shouldn't increase significantly)
- [ ] Error rates in application logs
- [ ] Users reporting 409 conflicts

### Log Patterns to Check
```
✓ Expected: "GET /practice/status 200"
✓ Expected: "POST /practice/start 201"
✗ NOT Expected: "POST /practice/start 409"
✗ NOT Expected: "SQLAlchemy" errors
✗ NOT Expected: "database.db is locked"
```

---

## 9. Rollback Plan (Emergency Only)

If severe issues occur:

```bash
# 1. Stop backend
# 2. Restore database backup
cp database.db.backup database.db

# 3. Restart backend
uvicorn app.main:app --reload

# 4. This rolls back to pre-migration state
```

**Note:** Rollback will lose any new data created after migration.

---

## 10. Success Criteria

✓ User completes Coding round  
✓ User starts Aptitude round (no 409 conflict)  
✓ User completes Aptitude round  
✓ User starts Interview round  
✓ No database errors in logs  
✓ All API endpoints return 2xx responses  
✓ Frontend displays no console errors  

---

## Timeline

| Phase | Time | Action |
|-------|------|--------|
| Immediate | 5 min | Restart backend |
| Quick Test | 10 min | Test workflow 2.1 |
| Full Test | 20 min | Test workflow 2.2 |
| Verify | 5 min | Run checks section 3 & 4 |
| **Total** | **~40 min** | Complete verification |

---

## Sign-Off Checklist

- [ ] Backend restarted successfully
- [ ] Database migration verified (2 migrations applied)
- [ ] Coding → Aptitude transition works
- [ ] Full practice session completes
- [ ] No errors in application logs
- [ ] API endpoints respond correctly
- [ ] Database queries execute properly
- [ ] Frontend has no console errors
- [ ] Ready for user testing

---

**Migration Status:** ✓ APPLIED  
**Testing Status:** 🔄 IN PROGRESS  
**Ready for Deployment:** Pending verification  

**Next Step:** Run tests in Section 2 and verify all checks in Section 3.
