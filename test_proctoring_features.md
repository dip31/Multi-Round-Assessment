# Proctoring Features Test Guide

## Quick Test Instructions

### 1. Start the Application

```powershell
# Terminal 1 - Backend
cd "D:\Projects\EDI 4\Multi-Round-Assesment-v8n"
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000

# Terminal 2 - Frontend
cd frontend
npm run dev
```

### 2. Start a Coding Round

1. Login to the application
2. Navigate to Dashboard
3. Click "Start Coding Round"
4. Grant camera and microphone permissions when prompted
5. The page should enter fullscreen mode automatically

### 3. Test Browser Event Detection

#### ✅ Tab Switching (WORKING - User Confirmed)
- Press `Alt + Tab` or click another browser tab
- **Expected:** Warning appears: "Tab switching is not allowed during the coding round"
- **Backend Log:** `EVENT_TYPES.TAB_SWITCH` logged to `/advanced-proctoring/log-event`

#### ✅ Fullscreen Exit
- Press `Esc` or `F11` to exit fullscreen
- **Expected:** Warning appears: "Fullscreen mode is required for the coding round"
- **Backend Log:** `EVENT_TYPES.FULLSCREEN_EXIT` logged

#### ✅ Copy/Paste Detection
- Try to copy text: `Ctrl + C`
- Try to paste text: `Ctrl + V`
- **Expected:** Event logged to backend (no UI warning by default)
- **Backend Log:** `EVENT_TYPES.COPY_PASTE` logged

#### ✅ Page Reload Detection
- Try to reload: `Ctrl + R` or `F5`
- **Expected:** Browser warning: "Are you sure you want to leave? Your session will be flagged."
- **Backend Log:** `EVENT_TYPES.PAGE_RELOAD` logged

#### ✅ Idle Activity Detection
- Don't move mouse or type for 60 seconds
- **Expected:** Event logged to backend
- **Backend Log:** `EVENT_TYPES.IDLE_ACTIVITY` logged

#### ✅ Network Disconnect
- Open Network settings and disable WiFi/Ethernet
- **Expected:** Event logged to backend
- **Backend Log:** `EVENT_TYPES.NETWORK_DISCONNECT` logged
- When reconnected: `EVENT_TYPES.NETWORK_RECONNECT` logged

#### ✅ Device Change
- Plug in or unplug a USB camera/microphone
- **Expected:** Event logged to backend
- **Backend Log:** `EVENT_TYPES.DEVICE_CHANGE` logged

### 4. Test Computer Vision Features

#### ✅ Face Detection
- Move your face out of camera view
- **Expected:** After 3 consecutive frames, warning appears: "Face not detected. Keep your face visible in the camera to continue."
- **Backend Log:** `EVENT_TYPES.FACE_NOT_VISIBLE` logged
- **Note:** This is a BLOCKING warning with Retry button

#### ✅ Multiple Person Detection
- Have another person appear in camera view
- **Expected:** CRITICAL violation logged
- **Backend Log:** `EVENT_TYPES.MULTIPLE_PERSON_DETECTED` with `face_count: 2`
- **Result:** May trigger immediate test termination (max_allowed: 0)

#### ✅ Head Turn Detection
- Turn your head significantly left or right
- **Expected:** After 5 consecutive frames, violation logged
- **Backend Log:** `EVENT_TYPES.HEAD_TURN_DETECTED` with head pose angles

#### ✅ Looking Away Detection
- Look away from the camera (up, down, left, right)
- **Expected:** Violation logged when gaze deviates > 0.3
- **Backend Log:** `EVENT_TYPES.LOOKING_AWAY` with gaze direction

#### ✅ Mouth Movement Detection
- Open your mouth or talk
- **Expected:** Violation logged when mouth opening > 0.05
- **Backend Log:** `EVENT_TYPES.MOUTH_MOVEMENT_DETECTED` with confidence score

### 5. Test Phone Detection

#### ✅ YOLO-based Phone Detection
- Hold a cell phone in front of the camera
- **Expected:** Frame analysis every 2-5 seconds detects phone
- **Backend Log:** `MULTIPLE_PERSON_DETECTED` event with `phone_count` in metadata
- **Console Log:** Check browser console for frame analysis logs

**Note:** Phone detection uses adaptive rate limiting:
- Fast responses (< 400ms): continues at 2s interval
- Slow responses (> 400ms): increases to 5s interval
- Prevents backend overload

### 6. Test Audio Monitoring

#### ⚠️ Voice Activity Detection (Basic Implementation)
- Speak while taking the test
- **Expected:** Event logged when voice activity detected
- **Backend Log:** `EVENT_TYPES.VOICE_ACTIVITY_DETECTED`
- **Note:** Current VAD is simplified. Production should use Silero VAD.

### 7. Test Violation Thresholds

#### Test Threshold Enforcement
1. Trigger the same violation multiple times (e.g., switch tabs repeatedly)
2. **Expected:** Counter increments in warning messages
3. After exceeding threshold (e.g., 3 tab switches), test terminates
4. **Result:** Full-screen modal: "Test Terminated - You have exceeded the maximum limit for proctoring violations"

#### Violation Thresholds (from config):
```javascript
TAB_SWITCH: { max: 2, riskWeight: 0.4 }
FULLSCREEN_EXIT: { max: 2, riskWeight: 0.5 }
PAGE_RELOAD: { max: 1, riskWeight: 0.9 }
IDLE_ACTIVITY: { max: 3, riskWeight: 0.3 }
COPY_PASTE: { max: 1, riskWeight: 0.7 }
NETWORK_DISCONNECT: { max: 2, riskWeight: 0.8 }
DEVICE_CHANGE: { max: 1, riskWeight: 0.8 }
MULTIPLE_PERSON_DETECTED: { max: 0, riskWeight: 1.0 } // Immediate termination
FACE_NOT_VISIBLE: { max: 3, riskWeight: 0.8 }
MOUTH_MOVEMENT_DETECTED: { max: 3, riskWeight: 0.6 }
LOOKING_AWAY: { max: 5, riskWeight: 0.4 }
HEAD_TURN_DETECTED: { max: 3, riskWeight: 0.5 }
VOICE_ACTIVITY_DETECTED: { max: 2, riskWeight: 0.7 }
CAMERA_PERMISSION_DENIED: { max: 0, riskWeight: 1.0 } // Immediate termination
MICROPHONE_PERMISSION_DENIED: { max: 0, riskWeight: 0.8 }
```

### 8. Verify UI Components

#### ✅ Video Preview
- Check bottom-right corner of screen
- **Expected:** Small video preview (32x24) showing your webcam feed
- **Behavior:** Visible when monitoring active, fades out when stopped

#### ✅ Warning Display
- Trigger any violation
- **Expected:** Color-coded warning appears at top center of screen
- **Colors:**
  - Red: High severity (camera denied, multiple people, etc.)
  - Yellow: Medium severity
  - Blue: Low severity
- **Behavior:** Auto-dismisses after 5 seconds (or manual dismiss)

#### ✅ Termination Modal
- Exceed violation threshold
- **Expected:** Full-screen overlay with:
  - Red warning icon
  - "Test Terminated" heading
  - Explanation message
  - "Return to Dashboard" button

### 9. Check Backend Logs

Monitor the backend terminal for proctoring event logs:

```
2026-08-15 10:30:45 [app.modules.advanced_proctoring.routers] Proctoring event logged: TAB_SWITCH session_id=42
2026-08-15 10:30:46 [app.services.advanced_proctoring_service] Risk score calculated: 0.3 for event TAB_SWITCH
2026-08-15 10:31:15 [app.modules.advanced_proctoring.routers] Frame analysis: phone_count=1 session_id=42
```

### 10. Check Database Records

Query the database to verify events are being stored:

```sql
-- Check advanced proctoring events
SELECT * FROM advanced_proctoring_events 
WHERE session_id = <your_session_id> 
ORDER BY created_at DESC 
LIMIT 20;

-- Check violation counts by type
SELECT event_type, COUNT(*) as count 
FROM advanced_proctoring_events 
WHERE session_id = <your_session_id> 
GROUP BY event_type;

-- Check risk scores
SELECT event_type, confidence, 
       event_metadata->>'risk_score' as risk_score,
       created_at 
FROM advanced_proctoring_events 
WHERE session_id = <your_session_id> 
ORDER BY created_at DESC;
```

## Common Issues & Solutions

### Issue: Camera/Microphone not working
**Solution:** 
1. Check browser permissions (Settings > Site Settings > Camera/Microphone)
2. Make sure no other app is using camera/mic
3. Try refreshing and re-granting permissions

### Issue: Fullscreen keeps exiting
**Solution:** 
1. Use a supported browser (Chrome, Edge, Firefox)
2. Don't press Esc or F11
3. Some systems may not support fullscreen API

### Issue: No proctoring warnings appearing
**Solution:**
1. Check browser console for errors
2. Verify `sessionId` is set in localStorage
3. Check network tab for API calls to `/advanced-proctoring/log-event`
4. Verify backend is running and accessible

### Issue: Face detection not working
**Solution:**
1. Ensure good lighting
2. Position face clearly in camera view
3. Wait for MediaPipe to initialize (check console logs)
4. Check for any CORS/CDN issues with MediaPipe assets

### Issue: Phone detection not working
**Solution:**
1. Verify `yolov8n.pt` file exists in project root
2. Check backend logs for YOLO model loading
3. Ensure phone is clearly visible in camera
4. Wait 2-5 seconds for frame analysis

## Performance Notes

- Frame processing: 5 FPS (every 6th frame)
- Phone detection: Adaptive 2-5 seconds per frame
- Event deduplication: 500ms - 60s intervals depending on event type
- Database writes: Asynchronous, won't block UI

## API Endpoints for Testing

Use these endpoints to verify backend functionality:

```http
### Log a proctoring event
POST http://localhost:8000/api/v1/advanced-proctoring/log-event
Content-Type: application/json
Authorization: Bearer <your_token>

{
  "session_id": 42,
  "event_type": "TAB_SWITCH",
  "confidence": 1.0,
  "metadata": {
    "timestamp": 1640995200000,
    "userAgent": "Mozilla/5.0..."
  }
}

### Get session summary
GET http://localhost:8000/api/v1/advanced-proctoring/session/42/summary
Authorization: Bearer <your_token>

### Check violations
GET http://localhost:8000/api/v1/advanced-proctoring/session/42/violations
Authorization: Bearer <your_token>

### Analyze frame (phone detection)
POST http://localhost:8000/api/v1/advanced-proctoring/analyze-frame?session_id=42
Content-Type: multipart/form-data
Authorization: Bearer <your_token>

[Upload JPEG image file]
```

## Success Criteria

✅ All browser events trigger warnings/logs
✅ Face detection works with proper lighting
✅ Multiple person detection works
✅ Phone detection identifies phones in frame
✅ Violation counters increment correctly
✅ Test terminates when thresholds exceeded
✅ Video preview displays webcam feed
✅ Warnings appear and auto-dismiss
✅ Backend logs all events to database
✅ API endpoints return expected responses

## Next Steps

If all tests pass, the proctoring system is ready for production use in coding rounds.

Optional enhancements:
- Implement production-grade VAD (Silero VAD)
- Add emotion detection using additional CV models
- Implement suspicious behavior pattern detection
- Add admin dashboard for reviewing flagged sessions
- Create detailed violation reports with timestamps and screenshots
