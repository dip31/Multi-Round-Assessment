# Quick Start After Implementation

## 1️⃣ Apply Database Migration

```bash
# Option A: Using Alembic (recommended)
cd /path/to/project
alembic upgrade head

# Option B: Manual SQL
psql -U postgres -d ai_placement_platform
```

```sql
ALTER TABLE interview_sessions ADD COLUMN status VARCHAR(20) DEFAULT 'ACTIVE' NOT NULL;
ALTER TABLE interview_sessions ADD COLUMN completion_reason VARCHAR(30);
ALTER TABLE interview_sessions ADD COLUMN completed_at TIMESTAMP;
```

---

## 2️⃣ Verify Backend Changes

### Start Backend with Debug Logging
```bash
uvicorn app.main:app --reload --log-level debug
```

### Watch for Sarvam TTS Logs
Look for these log messages when TTS is called:
```
INFO: Sarvam client ready: True, key set: True
INFO: TTS request: text_len=42
INFO: TTS success: audios_count=1, bytes=24576, latency=1.23s
```

### Test Coding Endpoints
```bash
# Run (visible test cases only)
curl -X POST http://localhost:8000/coding/run \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"problem_id": 1, "code": "def solution(n): return n", "language": "python"}'

# Expected response: CodingRunResponse with test_case_results array

# Submit (all test cases, persisted)
curl -X POST http://localhost:8000/coding/submit \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"problem_id": 1, "code": "def solution(n): return n", "language": "python"}'

# Expected response: CodingSubmissionResponse with submission_id, submitted_at, score
# NO hidden test inputs/outputs should be present
```

### Test Interview Complete Endpoint
```bash
curl -X POST http://localhost:8000/interview/session/1/complete \
  -H "Authorization: Bearer YOUR_TOKEN"

# Expected response:
# {
#   "status": "COMPLETED",
#   "completion_reason": "USER_SUBMITTED",
#   "questions_attempted": 5,
#   "questions_total": 10,
#   "performance_score": 0.78,
#   "completion_ratio": 0.5
# }
```

---

## 3️⃣ Verify Frontend Changes

### Start Frontend
```bash
cd frontend
npm install  # if not done already
npm run dev
```

### Test Flow

1. **Login** → Dashboard

2. **Start Interview**
   - Check browser console for: `Interview ID found: 123`
   - Should NOT see: `NaN` in proctoring event logs

3. **During Interview**
   - TTS should play audio (or show toast: "Audio unavailable")
   - Browser console should show readable TTS errors if it fails
   - "Submit Interview" button visible in top bar

4. **Click Submit Interview**
   - Confirmation dialog shows progress: `5 out of 10 questions answered`
   - After confirm, redirects to `/interview/report/123`
   - Backend logs should show: `POST /interview/session/123/complete`

5. **Interview Report**
   - Check browser DevTools Network tab
   - Response should include:
     - `completion_reason: "USER_SUBMITTED"`
     - `completion_ratio: 0.5`
     - `intent_score: 0.78`

6. **Verify Media Cleanup**
   - Open DevTools → More Tools → Media
   - After interview ends, NO active camera/mic streams should remain

---

## 4️⃣ Pytest Verification

```bash
# Should collect without errors
pytest tests/test_smoke.py -v

# If you see "extra fields not permitted" for OPENAI_API_KEY:
# Check that app/config/settings.py includes:
# OPENAI_API_KEY: Optional[str] = None
```

---

## 5️⃣ Common Issues & Fixes

### Issue: "submitted_at cannot be null"
**Cause:** `/submit` endpoint not refreshing submission from DB  
**Fix:** Already implemented - checks for `submission.submitted_at` after commit

### Issue: TTS shows "Audio unavailable" immediately
**Causes:**
1. Sarvam API key not set: Check `.env` for `SARVAM_API_KEY`
2. Rate limit: Wait 60 seconds
3. Network issue: Check backend logs for error details

**Fixed:** Error messages now readable in browser console

### Issue: Proctoring events fail with 500
**Cause:** `session_id` is NaN  
**Fix:** Already implemented - `parseInt(interviewId, 10)` before hook call

### Issue: Camera doesn't stop after interview
**Cause:** Missing cleanup in unmount  
**Fix:** Already implemented - `proctoring.stopMonitoring()` in useEffect cleanup

### Issue: Submit Interview does nothing
**Causes:**
1. Migration not applied: Run `alembic upgrade head`
2. `handleSubmitInterview` not imported: Already defined in component

---

## 6️⃣ Rollback Plan (if needed)

If implementation causes issues:

```bash
# Rollback database migration
alembic downgrade -1

# Or manual SQL:
psql -U postgres -d ai_placement_platform
```

```sql
ALTER TABLE interview_sessions DROP COLUMN completed_at;
ALTER TABLE interview_sessions DROP COLUMN completion_reason;
ALTER TABLE interview_sessions DROP COLUMN status;
```

Then revert code changes:
```bash
git checkout HEAD~1 -- app/ frontend/
```

---

## 7️⃣ Performance Checks

### Backend Response Times
- `/coding/run`: < 2s (mock mode)
- `/coding/submit`: < 3s (mock mode)
- `/interview/tts`: < 3s (first call), < 50ms (cached)
- `/interview/session/{id}/complete`: < 100ms

### Frontend Metrics
- TTS playback starts within 2s of question display
- Submit Interview completes within 1s
- No memory leaks (check DevTools Memory tab)

---

## 8️⃣ Monitoring

### Backend Logs to Watch
```
✅ "Sarvam client ready: True"
✅ "TTS success: audios_count=1, bytes=24576, latency=1.23s"
✅ "Interview completed: {'status': 'COMPLETED', ...}"
❌ "Sarvam TTS failed: type=Exception, status=503"
❌ "Interview not found" (404)
```

### Frontend Console (Production)
Should be clean - no errors. Only warnings acceptable:
```
⚠️ "TTS failed, retrying once..."
```

---

## 9️⃣ Success Criteria

- [ ] Coding run shows per-case results
- [ ] Coding submit returns submission_id + submitted_at
- [ ] No hidden test data in submit response
- [ ] TTS errors are readable
- [ ] Proctoring events have integer session_id
- [ ] Camera stops after interview ends
- [ ] Submit Interview button works
- [ ] Report shows completion_reason
- [ ] Pytest collects successfully
- [ ] No 500 errors in any endpoint

---

**All systems green? You're ready for demo! 🚀**
