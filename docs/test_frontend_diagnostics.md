# Frontend Diagnostics Checklist

## Issue 1: Audio Overlap

### Root Cause Analysis
The audio overlap is likely caused by:
1. ✅ Multiple TTS calls - FIXED with `hasSpokenRef`
2. ✅ No audio stopping - FIXED with `stopCurrentAudio()`
3. ✅ React Strict Mode double render - FIXED with empty deps `[]`
4. ⚠️ Potential race condition in startup

### Current Implementation
- `useEffect` with empty deps `[]` at line 120
- `hasSpokenRef` check at line 212
- `stopCurrentAudio()` called before each playback
- `isPlayingRef` prevents concurrent calls

### Testing Steps
1. Open browser console
2. Start interview
3. Watch for console logs:
   - Should see ONE "synthesizeSpeech" call for intro
   - Should see ONE "synthesizeSpeech" call per question
4. Listen for overlapping audio
5. Check if intro plays twice

### Expected Behavior
- Intro plays ONCE
- Each question plays ONCE
- No overlapping voices

---

## Issue 2: Camera Stopping After 2-3 Seconds

### Root Cause Analysis
The camera stopping is likely caused by:
1. ✅ Advanced proctoring cleanup - FIXED by using `useBasicProctoring`
2. ✅ Re-render cleanup - FIXED by removing cleanup on deps change
3. ⚠️ Browser autoplay policy
4. ⚠️ Stream being stopped elsewhere

### Current Implementation
- Using `useBasicProctoring` hook (no advanced proctoring)
- Camera initialized once in useEffect with empty deps
- Stream stored in `streamRef`
- Cleanup only on unmount

### Testing Steps
1. Open browser console
2. Start interview
3. Watch camera feed
4. Check console for errors:
   - "Camera access failed"
   - "Track ended"
5. Verify camera stays on for entire interview

### Expected Behavior
- Camera starts immediately
- Camera stays on throughout interview
- Camera stops only when interview completes

---

## Issue 3: 422 Proctoring Errors

### Root Cause Analysis
The 422 errors were caused by:
1. ✅ Advanced proctoring API calls - FIXED by removing advanced proctoring
2. ✅ Invalid data format - FIXED by using basic proctoring only

### Current Implementation
- No advanced proctoring API calls
- No `/advanced-proctoring/log-event` calls
- Basic camera feed only

### Testing Steps
1. Open browser console
2. Start interview
3. Check Network tab for:
   - ❌ Should NOT see `/advanced-proctoring/log-event` calls
   - ✅ Should see `/interview/session/{id}/next` calls
   - ✅ Should see `/interview/session/{id}/respond` calls
4. Check console for 422 errors

### Expected Behavior
- NO 422 errors
- NO advanced proctoring API calls
- Only interview API calls

---

## Issue 4: STT Not Working

### Root Cause Analysis
STT might not be working due to:
1. ⚠️ Whisper model not loaded
2. ⚠️ Audio format issues
3. ⚠️ Empty transcript being returned
4. ✅ Evaluation engine is working (verified by backend test)

### Current Implementation
- Audio recorded as webm
- Sent to `/interview/stt` endpoint
- Whisper transcribes audio
- Transcript sent to `/interview/session/{id}/respond`
- Backend evaluates using Groq

### Testing Steps
1. Open browser console
2. Start interview
3. Answer a question
4. Check Network tab:
   - POST `/interview/stt` - check response for transcript
   - POST `/interview/session/{id}/respond` - check request body for transcript
5. Check if follow-up or next question appears

### Expected Behavior
- Audio is transcribed to text
- Text is sent to backend
- Backend evaluates and returns action (FOLLOWUP or NEXT)
- Follow-up appears if answer is SHORT/PARTIAL/IRRELEVANT
- Next question appears if answer is GOOD

---

## Manual Testing Checklist

### Before Starting
- [ ] Backend is running (`python -m uvicorn app.main:app --reload`)
- [ ] Frontend is running (`npm run dev` in frontend folder)
- [ ] Browser console is open
- [ ] Network tab is open

### During Interview
- [ ] Intro plays ONCE (not twice)
- [ ] Camera starts and stays on
- [ ] No 422 errors in console
- [ ] Each question plays ONCE
- [ ] No overlapping audio
- [ ] Recording indicator appears when speaking
- [ ] Transcript appears in network request
- [ ] Follow-up appears for short answers
- [ ] Next question appears for good answers

### After Interview
- [ ] Camera stops when interview completes
- [ ] Report is accessible
- [ ] No errors in console

---

## Quick Fix Summary

### What Was Fixed
1. ✅ Removed unused helper functions (`getEmotionColor`, `getMetricColor`)
2. ✅ Created `useBasicProctoring` hook (camera only, no API calls)
3. ✅ Updated `HumanLikeInterview.jsx` to use basic proctoring
4. ✅ Removed advanced proctoring initialization
5. ✅ Changed startup useEffect to empty deps `[]`
6. ✅ Added `hasSpokenRef` to prevent duplicate TTS calls
7. ✅ Added `stopCurrentAudio()` before each playback

### What Needs Testing
1. ⚠️ Audio overlap - verify intro plays once
2. ⚠️ Camera persistence - verify camera stays on
3. ⚠️ STT flow - verify transcription is working
4. ⚠️ Evaluation - verify follow-ups appear for short answers

---

## If Issues Persist

### Audio Still Overlapping
1. Check if `fetchNextQuestion` is being called multiple times
2. Add console.log in `playAudio` to track calls
3. Check if `hasSpokenRef` is being reset unexpectedly

### Camera Still Stopping
1. Check browser console for "Track ended" messages
2. Verify no other code is calling `stopCamera()`
3. Check if browser is blocking camera access

### STT Not Working
1. Check if Whisper model is loaded in backend
2. Verify audio format is compatible
3. Check if transcript is empty in network response

### 422 Errors Still Appearing
1. Search codebase for `/advanced-proctoring/log-event`
2. Verify `useBasicProctoring` is being used
3. Check if any other component is making advanced proctoring calls
