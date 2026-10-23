# Quick Fix: Coding Run 400 & Proctoring Not Working

## Issue 1: POST /api/v1/coding/run -> 400 Bad Request

### Most Likely Cause: Problem Not Assigned

The 400 error happens when the problem you're trying to run is not in the `session_problems` table for your active round.

### Quick Fix:

**Option A: Restart the round (Recommended)**

1. Go back to dashboard
2. Click "Start Coding Round" again
3. Backend will reuse existing round and return assigned problems
4. Try clicking "Run Code" again

**Option B: Clear and restart**

If Option A doesn't work:

```sql
-- In PostgreSQL, mark your current round as completed
UPDATE coding_rounds 
SET completed_at = NOW()
WHERE user_id = <your_user_id>
AND completed_at IS NULL;
```

Then start a fresh round from dashboard.

### Debug What's Happening:

**Step 1: Check browser Network tab (F12)**
- Find the `/coding/run` POST request
- Click on it
- Look at "Response" tab
- Should show exact error: `{"detail": "problem not assigned to current round"}` or `{"detail": "coding round has expired"}`

**Step 2: Check browser Console**
- Press F12
- Go to Console tab
- Look for errors when clicking "Run Code"
- May show validation errors or network errors

**Step 3: Verify problems loaded**
```javascript
// In browser console on coding round page:
console.log('Current problem:', document.querySelector('.problem-title')?.textContent);
```

Should show the problem title. If empty, problems didn't load.

### Root Cause Analysis:

The backend checks:
1. User has an active coding round ✅
2. The problem_id is assigned to that round in `session_problems` table ❌ (This is likely failing)
3. The round hasn't expired ✅

The assignment should happen in `startRound()` but might not be persisting correctly.

**Check if `startRound()` is actually being called:**

1. Open browser DevTools → Network tab
2. Refresh the coding round page
3. Look for `/coding/start` or `/coding/start-after-aptitude` request
4. Check if it returns `200 OK` with problems array
5. Check response includes `assigned` array with problem assignments

**Example good response:**
```json
{
  "round": { "id": 42, "user_id": 1, ... },
  "assigned": [
    { "id": 1, "round_id": 42, "problem_id": 101, "problem_order": 1 },
    { "id": 2, "round_id": 42, "problem_id": 102, "problem_order": 2 }
  ],
  "problems": [ ... ]
}
```

---

## Issue 2: Proctoring Not Working

### Symptoms:
- No video preview
- Tab switching doesn't show warnings
- No proctoring initialization logs

### Quick Checks:

**1. Is the video element rendered?**
```javascript
// Browser console:
document.querySelector('video')
```
Should return: `<video ...>` element
If `null`: Video element not being rendered

**2. Is sessionId set?**
```javascript
// Browser console:
localStorage.getItem('coding_round_id')
```
Should return: a number like "42"
If `null`: Session not initialized

**3. Are permissions granted?**
- Look for browser permission prompt (camera icon in address bar)
- Click Allow for camera and microphone
- Refresh page

**4. Check console for initialization**
Press F12 → Console tab
Look for:
```
🚀 Initializing advanced proctoring system...
✅ Face detection initialized
✅ Face mesh initialized  
✅ Camera initialized
✅ Advanced proctoring system initialized successfully
```

If you see errors instead, that's the problem.

### Common Fixes:

**Fix 1: Camera permissions denied**
1. Click camera/mic icon in browser address bar
2. Change to "Allow"
3. Refresh page
4. Grant permissions when prompted

**Fix 2: sessionId not set**

```javascript
// Set manually in console (temporary):
localStorage.setItem('coding_round_id', '42'); // Use your actual round ID
```

Then refresh page.

**Fix 3: MediaPipe loading failed**
- Open Network tab (F12)
- Look for failed requests to `cdn.jsdelivr.net`
- If you see 404 errors for MediaPipe assets, the CDN version is wrong
- This was already fixed in previous updates

**Fix 4: Hook not initialized**

Check if this code exists in `CodingRoundV2.jsx`:

```javascript
const { startMonitoring, stopMonitoring, isMonitoring, videoRef } = useAdvancedProctoring(sessionId, (violation) => {
  // ...
});

useEffect(() => {
  if (!sessionId) return;
  startMonitoring?.();
  return () => stopMonitoring?.();
}, [sessionId]);
```

Should be around line 42 and line 74.

### Test Proctoring Works:

Once video preview appears in bottom-right:

1. **Test tab switching:**
   - Press `Alt + Tab` to switch to another app
   - Switch back
   - Should see warning banner at top

2. **Test face detection:**
   - Move your face out of camera view
   - Wait 3-5 seconds
   - Should see "Face not visible" warning

3. **Test fullscreen:**
   - Press `Esc` to exit fullscreen
   - Should see "Fullscreen mode required" warning

---

## Emergency Workaround: Disable Proctoring

If proctoring is completely broken and blocking coding:

**Edit: `frontend/src/pages/CodingRoundV2.jsx`**

Comment out these lines:

```javascript
// TEMPORARILY DISABLED FOR DEBUGGING
/*
const { startMonitoring, stopMonitoring, isMonitoring, videoRef } = useAdvancedProctoring(sessionId, (violation) => {
  // ...
});

useEffect(() => {
  if (!sessionId) return;
  startMonitoring?.();
  return () => stopMonitoring?.();
}, [sessionId]);
*/

// Add dummy values:
const startMonitoring = () => {};
const stopMonitoring = () => {};
const isMonitoring = false;
const videoRef = { current: null };
```

Also comment out the video element and proctoring warnings:

```javascript
/*
<video
  ref={videoRef}
  ...
/>
*/

/*
{proctoringWarnings.length > 0 && ...}
*/
```

Save, refresh browser. Now coding should work without proctoring.

**Remember to re-enable proctoring after fixing the issue!**

---

## Still Not Working?

Provide these details:

1. **Exact error message from browser Network tab Response**
2. **Browser console logs** (full output)
3. **Backend terminal logs** around the 400 error
4. **Database query results** from `debug_coding_round.sql`

Run this in browser console and share output:

```javascript
// Diagnostic
console.log('=== DIAGNOSTIC ===');
console.log('sessionId:', localStorage.getItem('coding_round_id'));
console.log('video element:', !!document.querySelector('video'));
console.log('current URL:', window.location.href);
console.log('problems loaded:', !!document.querySelector('.problem-title'));

// Try to call API directly
fetch('/api/v1/coding/problems', {
  headers: { 'Authorization': 'Bearer ' + localStorage.getItem('token') }
})
.then(r => r.json())
.then(d => console.log('Problems API:', d))
.catch(e => console.error('Problems API error:', e));
```

This will help identify the exact issue.
