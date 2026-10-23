# Debug Guide: Coding Run 400 Error & Proctoring Issues

## Issue 1: Coding Run Returns 400 Bad Request

### Symptoms
```
POST /api/v1/coding/run -> 400 Bad Request
```

### Possible Causes

#### 1. Problem Not Assigned to Round
**Error message:** `"problem not assigned to current round"`

**Root cause:** The `startRound()` didn't properly assign problems to `SessionProblem` table.

**Debug steps:**
```sql
-- Check if problems are assigned
SELECT sp.*, cr.id as round_id, cr.user_id, cr.started_at 
FROM session_problems sp
JOIN coding_rounds cr ON sp.round_id = cr.id
WHERE cr.user_id = <your_user_id>
ORDER BY sp.id DESC;
```

**Expected:** Should see rows with `round_id` and `problem_id`

**Fix if empty:** Check `startRound()` in `codingService.js` and backend endpoint

#### 2. No Active Coding Round
**Error message:** `"no active coding round"` (would be 404, not 400)

**Debug steps:**
```sql
-- Check active rounds
SELECT * FROM coding_rounds 
WHERE user_id = <your_user_id> 
AND completed_at IS NULL
ORDER BY started_at DESC;
```

**Expected:** Should have one row with `completed_at = NULL`

#### 3. Missing Payload Fields
**Check frontend browser console:**
```javascript
// Should log:
{
  problem_id: 1,
  code: "def solution()...",
  language: "python"
}
```

**Fix:** Ensure `current.id`, `currentCode`, and `language` are all populated

### Quick Fix Steps

1. **Open browser DevTools (F12) → Network tab**
2. **Click "Run Code" button**
3. **Find the `/coding/run` request**
4. **Check Request payload:**
   - Is `problem_id` present and a number?
   - Is `code` present and not empty?
   - Is `language` present? (python/javascript/java/cpp)
5. **Check Response:**
   - Look at the `detail` field for specific error message

### Backend Debug Mode

Add this to the coding router temporarily:

```python
@router.post("/run", response_model=CodingRunResponse)
def run_code(payload: CodingSubmissionRequest, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    print(f"[DEBUG] Run code request: problem_id={payload.problem_id}, language={payload.language}, code_len={len(payload.code)}")
    
    active_round = session_service.get_user_active_round(db, current_user.id, round_type="coding")
    print(f"[DEBUG] Active round: {active_round}")
    
    if active_round is None:
        raise HTTPException(status_code=404, detail="no active coding round")

    # ... rest of function
```

Check terminal for debug output.

---

## Issue 2: Proctoring Not Working

### Symptoms
- No video preview in bottom-right
- No violations logged when switching tabs
- Console errors about proctoring

### Debug Steps

#### Step 1: Check Browser Console (F12)
Look for these logs:
```
🚀 Initializing advanced proctoring system...
✅ Face detection initialized
✅ Face mesh initialized
✅ Camera initialized
✅ Audio monitoring initialized
✅ Advanced proctoring system initialized successfully
```

**If missing:** Proctoring didn't start

#### Step 2: Check Video Element
```javascript
// In browser console, run:
document.querySelector('video')
```

**Expected:** Should return the video element

**If null:** Video element not rendered (check `videoRef`)

#### Step 3: Check Session ID
```javascript
// In browser console:
localStorage.getItem('coding_round_id')
```

**Expected:** Should be a number (e.g., "42")

**If null:** Session not started properly

#### Step 4: Check Hook Return Values
Add temporary console log in `CodingRoundV2.jsx`:

```javascript
const { startMonitoring, stopMonitoring, isMonitoring, videoRef } = useAdvancedProctoring(sessionId, (violation) => {
  // ...
});

console.log('[Proctoring]', { 
  startMonitoring: typeof startMonitoring, 
  stopMonitoring: typeof stopMonitoring,
  isMonitoring,
  videoRef: !!videoRef?.current,
  sessionId 
});
```

**Expected output:**
```
[Proctoring] {
  startMonitoring: "function",
  stopMonitoring: "function", 
  isMonitoring: true,
  videoRef: true,
  sessionId: 42
}
```

#### Step 5: Check MediaPipe Loading
Look for CDN errors in Network tab:
```
https://cdn.jsdelivr.net/npm/@mediapipe/face_detection@...
https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh@...
```

**If 404:** MediaPipe version mismatch
**Fix:** Check versions in `useAdvancedProctoring.js`:
```javascript
const MEDIAPIPE_FACE_DETECTION_VERSION = '0.4.1646425229';
const MEDIAPIPE_FACE_MESH_VERSION = '0.4.1633559619';
```

#### Step 6: Check Camera Permissions
```javascript
// In browser console:
navigator.mediaDevices.getUserMedia({ video: true, audio: true })
  .then(() => console.log('✅ Permissions granted'))
  .catch(err => console.error('❌ Permission denied:', err));
```

**If denied:** User blocked camera/mic access

**Fix:** 
1. Click camera icon in address bar
2. Allow camera and microphone
3. Refresh page

---

## Common Issues & Solutions

### Issue: "startMonitoring is not a function"

**Cause:** Hook doesn't export `startMonitoring`

**Check:**
```javascript
// In useAdvancedProctoring.js - should have:
return {
  // ...
  startMonitoring: initializeProctoring, // ← This line
  // ...
};
```

**Fix:** Already fixed in previous commits - verify file is saved

---

### Issue: Video preview not showing

**Cause 1:** Video element not rendered
```jsx
// Should be in CodingRoundV2.jsx:
<video
  ref={videoRef}
  autoPlay
  playsInline
  muted
  className={`fixed bottom-4 right-4 w-32 h-24 ...`}
/>
```

**Cause 2:** `isMonitoring` is false
- Check `sessionId` is set
- Check `startMonitoring()` was called
- Check for initialization errors

**Cause 3:** CSS hiding it
- Check `opacity-0` class only applies when NOT monitoring

---

### Issue: Tab switching not logging

**Cause 1:** Wrong API endpoint (ALREADY FIXED)
- Should use `/advanced-proctoring/log-event`
- Should use `/advanced-proctoring/analyze-frame`

**Cause 2:** Event handler not attached
```javascript
// Check browser console after 5 seconds:
document.hidden // false = visible, true = hidden
```

Then switch tabs and check again - should change to `true`

**Cause 3:** Event deduplication
- Tab switch events limited to once per 500ms
- Check backend logs for "EVENT_TYPES.TAB_SWITCH"

---

## Testing Checklist

### Test 1: Coding Run
- [ ] Start coding round → Problems load
- [ ] Write some code in editor
- [ ] Click "Run Code" button
- [ ] Should see "Running visible test cases..." 
- [ ] Should see test results (passed/failed)
- [ ] Network tab shows 200 OK response

### Test 2: Proctoring Initialization  
- [ ] Page loads and requests camera/mic permissions
- [ ] Grant permissions
- [ ] Video preview appears in bottom-right
- [ ] Console shows initialization logs
- [ ] No errors in console

### Test 3: Tab Switching
- [ ] Press Alt+Tab to switch tabs
- [ ] Should see warning banner at top
- [ ] Backend terminal shows log event
- [ ] Database has new row in `advanced_proctoring_events`

### Test 4: Face Detection
- [ ] Move face out of camera view
- [ ] After 3 seconds, warning should appear
- [ ] Move face back → warning disappears

---

## Quick Diagnostic Script

Run this in browser console on the coding round page:

```javascript
// Comprehensive proctoring diagnostic
(function() {
  console.log('=== PROCTORING DIAGNOSTIC ===');
  
  // Session ID
  const sessionId = localStorage.getItem('coding_round_id');
  console.log('Session ID:', sessionId || '❌ MISSING');
  
  // Video element
  const video = document.querySelector('video');
  console.log('Video element:', video ? '✅ Found' : '❌ Missing');
  if (video) {
    console.log('  - srcObject:', video.srcObject ? '✅ Stream attached' : '❌ No stream');
    console.log('  - readyState:', video.readyState);
  }
  
  // MediaPipe
  console.log('MediaPipe globals:');
  console.log('  - FaceDetection:', typeof window.FaceDetection !== 'undefined' ? '✅ Loaded' : '❌ Missing');
  console.log('  - FaceMesh:', typeof window.FaceMesh !== 'undefined' ? '✅ Loaded' : '❌ Missing');
  
  // Permissions
  navigator.permissions.query({ name: 'camera' }).then(result => {
    console.log('Camera permission:', result.state);
  });
  navigator.permissions.query({ name: 'microphone' }).then(result => {
    console.log('Microphone permission:', result.state);
  });
  
  // Test tab switch detection
  console.log('\nTest tab switching:');
  console.log('1. Open a new tab');
  console.log('2. Come back to this tab');
  console.log('3. Check if warning appears');
  
  console.log('\n=== END DIAGNOSTIC ===');
})();
```

---

## Emergency Fixes

### If proctoring completely broken:

1. **Disable proctoring temporarily:**
```jsx
// In CodingRoundV2.jsx, comment out:
// const { startMonitoring, ... } = useAdvancedProctoring(...);
// useEffect(() => { startMonitoring?.(); ... }, [sessionId]);
```

2. **Test coding functionality without proctoring:**
- Should still be able to run/submit code
- Round timer should still work
- Editor should function normally

### If coding run broken:

1. **Check backend is running:**
```powershell
curl http://localhost:8000/api/v1/coding/problems
```

Should return problem list (may need auth token)

2. **Check database connection:**
```sql
SELECT COUNT(*) FROM coding_problems;
```

Should return > 0

3. **Reset coding round:**
```sql
-- Mark current round as completed
UPDATE coding_rounds 
SET completed_at = NOW()
WHERE user_id = <your_user_id> 
AND completed_at IS NULL;
```

Then start a fresh round.

---

## Get More Help

If issues persist, provide:

1. **Browser console logs** (full output from page load)
2. **Backend terminal logs** (especially around the 400 error)
3. **Network tab** screenshot showing the failed request
4. **Database query results** from debug steps above
5. **Version info:**
   ```
   - Browser: Chrome/Edge/Firefox version
   - Node.js version: node --version
   - Python version: python --version
   ```

This will help identify the exact issue quickly.
