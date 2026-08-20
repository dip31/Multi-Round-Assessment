# Interview System Enhancements — Design Document

## Overview

This document provides complete implementation design for two 
major enhancements to the existing AI interview platform:

1. **Timed Answer Recording** — Thinking timer with automatic 
   recording trigger and manual stop control
2. **Advanced Proctoring** — Mobile phone detection (YOLOv8n) 
   and multiple person detection (existing MediaPipe)

---

## CRITICAL: Read Before Implementation

### Existing System Context

The following already exist and MUST NOT be replaced:
frontend/src/hooks/useAdvancedProctoring.js
→ Already implements MediaPipe face detection
→ Already implements tab switch, fullscreen detection
→ Extend this hook — do not create a new one
frontend/src/components/AdvancedProctoringMonitor.jsx
→ Already renders proctoring status
→ Update to show new violation types
frontend/src/pages/HumanLikeInterview.jsx
→ Main interview page — modify carefully
→ Add timer and recording components here
app/modules/interview/routers/interview_router.py
→ Add new endpoints here
→ Do not break existing /respond, /next, /stt, /tts
app/models/interview.py
→ InterviewTurn, InterviewSession already exist
→ Add new proctoring model here

### What is NEW vs EXTENDED
NEW:
TimerComponent.jsx
RecordingManager.jsx
ViolationAlert.jsx
POST /advanced-proctoring/analyze-frame (backend)
POST /advanced-proctoring/log-event (backend)
YOLOv8n phone detection service
PhoneDetectionService (backend)
EXTENDED:
useAdvancedProctoring.js → add multi-person logic
HumanLikeInterview.jsx → integrate timer + recording
AdvancedProctoringMonitor.jsx → show new violations
interview_router.py → add proctoring endpoints
app/models/interview.py → add ProctoringViolation model

---

## Architecture Overview
┌─────────────────────────────────────────────────────┐
│                    FRONTEND                          │
│                                                      │
│  HumanLikeInterview.jsx                              │
│    ├── TimerComponent.jsx (NEW)                      │
│    │     └── Thinking timer → triggers recording     │
│    ├── RecordingManager.jsx (NEW)                    │
│    │     └── Audio capture → STT → submit            │
│    ├── ViolationAlert.jsx (NEW)                      │
│    │     └── Top-right warning overlay               │
│    └── useAdvancedProctoring.js (EXTENDED)           │
│          ├── Existing: tab/fullscreen/face detection │
│          ├── NEW: multi-person count check           │
│          └── NEW: frame capture → POST analyze-frame │
│                                                      │
└──────────────────────────┬──────────────────────────┘
│ HTTP
┌──────────────────────────▼──────────────────────────┐
│                    BACKEND                           │
│                                                      │
│  interview_router.py                                 │
│    ├── POST /analyze-frame (NEW)                     │
│    │     └── PhoneDetectionService → YOLOv8n         │
│    └── POST /log-event (NEW)                         │
│          └── ProctoringViolation → PostgreSQL        │
│                                                      │
│  PhoneDetectionService (NEW)                         │
│    └── YOLOv8n inference → cell phone class 67       │
│                                                      │
└─────────────────────────────────────────────────────┘

---

## PART 1: TIMER AND RECORDING SYSTEM

---

### 1.1 Timer Duration Rules

Timer duration is determined by question difficulty.
This value is passed as a prop to TimerComponent.

```javascript
const TIMER_DURATIONS = {
  EASY: 60,      // 60 seconds thinking time
  MEDIUM: 90,    // 90 seconds thinking time
  HARD: 120,     // 120 seconds thinking time
  DEFAULT: 90    // fallback for unknown difficulty
};

const MAX_RECORDING_SECONDS = 180; // 3 minutes hard cap
```

---

### 1.2 Interview State Machine

The interview room has these states in sequence.
Each question turn follows this exact flow:
LOADING
↓ (question fetched)
THINKING
↓ (timer reaches 0 OR candidate clicks "Start Early")
RECORDING
↓ (candidate clicks Stop OR 180s max reached)
PROCESSING
↓ (STT + /respond complete)
THINKING (next question) OR COMPLETE

State variable:
```javascript
const INTERVIEW_STATES = {
  LOADING: 'LOADING',
  THINKING: 'THINKING',
  RECORDING: 'RECORDING',
  PROCESSING: 'PROCESSING',
  COMPLETE: 'COMPLETE'
};
```

---

### 1.3 TimerComponent.jsx (NEW FILE)
File: frontend/src/components/TimerComponent.jsx
Props:
duration: number          // seconds (from TIMER_DURATIONS)
mode: 'thinking'|'recording'
onThinkingComplete: fn    // called when thinking timer hits 0
onEarlyStart: fn          // called when candidate clicks early start
isRecording: boolean      // true when recording is active
recordingSeconds: number  // elapsed recording time
Behavior:
THINKING MODE (mode='thinking'):
Count DOWN from duration to 0
Display: MM:SS format
Label: "Thinking Time"
Color: blue (text-blue-400, ring-blue-500)
Show "Start Answering Early" button below timer
When countdown hits 0: call onThinkingComplete()
"Start Answering Early" button:
px-4 py-2 rounded-xl bg-blue-600/20 text-blue-400
border border-blue-600/30 text-sm
hover:bg-blue-600/30 transition-colors
On click: call onEarlyStart()
RECORDING MODE (mode='recording'):
Count UP from 0
Display: MM:SS elapsed recording time
Label: "Recording"
Color: red (text-red-400, ring-red-500)
Show pulsing red dot indicator
No early start button in this mode
Timer circle visual:
SVG circle with stroke-dasharray progress
Circle dims: w-24 h-24 (96px)
Stroke width: 6px
Background ring: stroke-slate-700
Progress ring: stroke-blue-500 (thinking)
stroke-red-500 (recording)
Animates smoothly each second
SVG implementation:
radius = 36
circumference = 2 * π * 36 = ~226
strokeDashoffset = circumference * (1 - progress)
progress for thinking = secondsRemaining / duration
progress for recording = min(recordingSeconds / 180, 1)
Time format function:
const formatTime = (seconds) => {
const m = Math.floor(seconds / 60);
const s = seconds % 60;
return ${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')};
};
Internal state:
const [secondsLeft, setSecondsLeft] = useState(duration);
useEffect(() => {
if (mode !== 'thinking') return;
if (secondsLeft <= 0) {
onThinkingComplete();
return;
}
const timer = setTimeout(() => {
setSecondsLeft(prev => prev - 1);
}, 1000);
return () => clearTimeout(timer);
}, [secondsLeft, mode]);
// Reset when duration changes (new question)
useEffect(() => {
setSecondsLeft(duration);
}, [duration]);

---

### 1.4 RecordingManager.jsx (NEW FILE)
File: frontend/src/components/RecordingManager.jsx
Props:
onRecordingComplete: fn(audioBlob, responseTimeSec)
isDisabled: boolean  // true during processing
maxSeconds: number   // 180
Internal state:
mediaRecorderRef = useRef(null)
audioChunksRef = useRef([])
startTimeRef = useRef(null)
recordingTimerRef = useRef(null)
maxRecordingTimerRef = useRef(null)
streamRef = useRef(null)
Exposed methods via useImperativeHandle:
startRecording()   // called by parent when thinking ends
stopRecording()    // called by Stop button or max timer
startRecording():

Request microphone permission:
stream = await navigator.mediaDevices.getUserMedia(
{audio: true, video: false}
)
If permission denied:
Show error: "Microphone access denied.
Please allow microphone access
and refresh the page."
Log proctoring event: event_type="mic_denied"
Return early
Store stream reference:
streamRef.current = stream
Create MediaRecorder:
mediaRecorderRef.current = new MediaRecorder(stream)
audioChunksRef.current = []
Collect audio chunks:
mediaRecorderRef.current.ondataavailable = (e) => {
if (e.data.size > 0) {
audioChunksRef.current.push(e.data);
}
}
Start recording:
startTimeRef.current = Date.now()
mediaRecorderRef.current.start(1000) // 1s chunks
Set maximum recording timer:
maxRecordingTimerRef.current = setTimeout(() => {
stopRecording(true) // true = auto-stopped
}, maxSeconds * 1000)

stopRecording(autoStopped = false):

Clear max recording timer:
clearTimeout(maxRecordingTimerRef.current)
Stop MediaRecorder:
if mediaRecorderRef.current?.state !== 'inactive':
mediaRecorderRef.current.stop()
Stop all tracks:
streamRef.current?.getTracks()
.forEach(track => track.stop())
Wait for onstop:
mediaRecorderRef.current.onstop = () => {
const audioBlob = new Blob(
audioChunksRef.current,
{type: 'audio/webm'}
)
const responseTimeSec =
(Date.now() - startTimeRef.current) / 1000
if (autoStopped) {
showToast(
"Maximum recording time reached.
Submitting your answer."
)
}
onRecordingComplete(audioBlob, responseTimeSec)
}

Cleanup on unmount:
useEffect(() => {
return () => {
clearTimeout(maxRecordingTimerRef.current)
streamRef.current?.getTracks()
.forEach(track => track.stop())
}
}, [])
UI rendered by RecordingManager:
ONLY the "Stop Recording" button
(Timer display is handled by TimerComponent)
Button:
Visible only when recording is active
px-8 py-3 rounded-xl bg-slate-700
hover:bg-slate-600 text-white font-semibold
flex items-center gap-3
Square stop icon (16px) + "Done Speaking"
Disabled + spinner during processing

---

### 1.5 HumanLikeInterview.jsx Integration
File: frontend/src/pages/HumanLikeInterview.jsx
[MODIFY] — add timer and recording to existing interview room
New state variables to add:
const [interviewState, setInterviewState] =
useState(INTERVIEW_STATES.LOADING);
const [recordingSeconds, setRecordingSeconds] =
useState(0);
const recordingManagerRef = useRef(null);
const recordingCounterRef = useRef(null);
New refs:
const recordingManagerRef = useRef(null);
Timer duration calculation:
const getTimerDuration = (difficulty) => {
return TIMER_DURATIONS[difficulty?.toUpperCase()]
?? TIMER_DURATIONS.DEFAULT;
};
When question loads (in fetchNextQuestion success):
setInterviewState(INTERVIEW_STATES.THINKING);
// TimerComponent auto-starts with new duration
When thinking timer completes (onThinkingComplete):
const handleThinkingComplete = async () => {
setInterviewState(INTERVIEW_STATES.RECORDING);
setRecordingSeconds(0);
// Start recording counter
recordingCounterRef.current = setInterval(() => {
  setRecordingSeconds(prev => prev + 1);
}, 1000);

// Start actual recording
await recordingManagerRef.current?.startRecording();
};
When early start clicked (onEarlyStart):
// Same as handleThinkingComplete
// Timer stops, recording begins immediately
handleThinkingComplete();
When recording complete (onRecordingComplete):
const handleRecordingComplete = async (
audioBlob,
responseTimeSec
) => {
// Stop recording counter
clearInterval(recordingCounterRef.current);
setInterviewState(INTERVIEW_STATES.PROCESSING);

// Existing STT + submit flow
await stopAndSubmit(audioBlob, responseTimeSec);
};
After submit completes:
// If action === NEXT: set state back to THINKING
// If action === COMPLETE: set state to COMPLETE
Layout changes in interview room RIGHT COLUMN:
QUESTION CARD (existing, no change)
TIMER + CONTROL BAR (replaces old control bar):
{interviewState === INTERVIEW_STATES.THINKING && (
<div className="bg-slate-900 rounded-2xl 
                 border border-slate-800 p-6
                 flex items-center justify-between">
<div>
<TimerComponent
       duration={getTimerDuration(currentDifficulty)}
       mode="thinking"
       onThinkingComplete={handleThinkingComplete}
       onEarlyStart={handleThinkingComplete}
       isRecording={false}
       recordingSeconds={0}
     />
</div>
<div className="text-slate-400 text-sm max-w-xs">
Take your time to think. Recording will start
automatically when the timer ends.
</div>
</div>
)}
{interviewState === INTERVIEW_STATES.RECORDING && (
<div className="bg-slate-900 rounded-2xl 
                 border border-slate-800 p-6
                 flex items-center justify-between">
<TimerComponent
     duration={MAX_RECORDING_SECONDS}
     mode="recording"
     isRecording={true}
     recordingSeconds={recordingSeconds}
   />
<RecordingManager
     ref={recordingManagerRef}
     onRecordingComplete={handleRecordingComplete}
     isDisabled={false}
     maxSeconds={MAX_RECORDING_SECONDS}
   />
</div>
)}
{interviewState === INTERVIEW_STATES.PROCESSING && (
<div className="bg-slate-900 rounded-2xl 
                 border border-slate-800 p-6
                 flex items-center justify-center gap-3">
<div className="w-5 h-5 border-2 border-slate-700 
                   border-t-blue-500 rounded-full 
                   animate-spin" />
<span className="text-slate-300 text-sm">
Analyzing your response...
</span>
</div>
)}
TOP BAR update — state indicator pill:
LOADING    → gray "Loading"
THINKING   → blue "Thinking Time"
RECORDING  → red pulsing "Recording"
PROCESSING → yellow "Processing"
COMPLETE   → green "Complete"

---

## PART 2: ADVANCED PROCTORING SYSTEM

---

### 2.1 Architecture Decision
CLEAR SEPARATION (do not mix these):
FRONTEND (useAdvancedProctoring.js):
Handles: face counting (multiple person detection)
Uses: existing MediaPipe (already implemented)
Reports to: POST /advanced-proctoring/log-event
BACKEND (PhoneDetectionService):
Handles: mobile phone detection only
Uses: YOLOv8n model
Called by: POST /advanced-proctoring/analyze-frame
Internally calls: violation logging to database
These are TWO separate detection paths.
Frontend does NOT run YOLO.
Backend does NOT run MediaPipe.

---

### 2.2 Installation Requirements
Backend (add to requirements.txt):
ultralytics          # YOLOv8n model
opencv-python-headless  # frame processing
Frontend:
No new packages needed
MediaPipe already installed
Canvas API is built-in browser API

---

### 2.3 Database Schema
File: alembic/versions/add_proctoring_violations.py
New table: proctoring_violations
op.create_table('proctoring_violations',
sa.Column('id', sa.Integer(), primary_key=True),
sa.Column('session_id', sa.Integer(),
sa.ForeignKey('interview_sessions.id',
ondelete='CASCADE'),
nullable=False),
sa.Column('event_type', sa.String(50), nullable=False),
# Values: 'mobile_phone', 'multiple_persons',
#         'tab_switch', 'fullscreen_exit', 'mic_denied'
sa.Column('confidence_score', sa.Float(), nullable=True),
sa.Column('face_count', sa.Integer(), nullable=True),
# For multiple_persons events
sa.Column('metadata', sa.JSON(), nullable=True),
sa.Column('created_at', sa.DateTime(),
server_default=sa.func.now())
)
op.create_index(
'idx_violations_session',
'proctoring_violations',
['session_id', 'created_at']
)
Run: alembic upgrade head

File: app/models/interview.py
[ADD] new model:
class ProctoringViolation(Base):
tablename = "proctoring_violations"
id = Column(Integer, primary_key=True)
session_id = Column(
    Integer,
    ForeignKey("interview_sessions.id", ondelete="CASCADE"),
    nullable=False
)
event_type = Column(String(50), nullable=False)
confidence_score = Column(Float, nullable=True)
face_count = Column(Integer, nullable=True)
metadata = Column(JSON, nullable=True)
created_at = Column(
    DateTime,
    server_default=func.now()
)

---

### 2.4 Backend: Phone Detection Service
File: app/services/phone_detection_service.py (NEW)
from ultralytics import YOLO
import numpy as np
import cv2
import logging
from typing import list
logger = logging.getLogger(name)
CELL_PHONE_CLASS_ID = 67  # COCO dataset class index
PHONE_CONFIDENCE_THRESHOLD = 0.6
Module-level singleton — load ONCE at startup
_model = None
def get_yolo_model() -> YOLO:
global _model
if _model is None:
logger.info("[YOLO] Loading YOLOv8n model...")
_model = YOLO("yolov8n.pt")
# Downloads automatically on first run (~6MB)
logger.info("[YOLO] Model loaded")
return _model
def detect_phones(image_bytes: bytes) -> list[dict]:
"""
Detect mobile phones in image bytes.
  Returns list of detections:
    [{"confidence": 0.85, "bbox": [x1,y1,x2,y2]}, ...]
  
  Returns empty list on any failure — never raises.
  
  Performance target: <500ms per frame
  If inference exceeds 500ms: skip and log warning
  """
  import time
  
  try:
      model = get_yolo_model()
      
      # Decode image bytes to numpy array
      nparr = np.frombuffer(image_bytes, np.uint8)
      frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
      
      if frame is None:
          logger.warning("[YOLO] Could not decode frame")
          return []
      
      # Run inference with timing
      start = time.time()
      results = model(
          frame,
          verbose=False,
          classes=[CELL_PHONE_CLASS_ID]
      )
      elapsed = time.time() - start
      
      if elapsed > 0.5:
          logger.warning(
              f"[YOLO] Frame processing slow: {elapsed:.2f}s"
          )
          return []
      
      # Extract phone detections above threshold
      detections = []
      for result in results:
          for box in result.boxes:
              confidence = float(box.conf[0])
              class_id = int(box.cls[0])
              
              if (class_id == CELL_PHONE_CLASS_ID and
                  confidence >= PHONE_CONFIDENCE_THRESHOLD):
                  
                  bbox = box.xyxy[0].tolist()
                  detections.append({
                      "confidence": round(confidence, 3),
                      "bbox": [round(x, 1) for x in bbox]
                  })
      
      return detections
  
  except Exception as e:
      logger.error(f"[YOLO] Inference failed: {e}")
      return []

---

### 2.5 Backend: Violation Logger with Retry
File: app/services/proctoring_logger.py (NEW)
import asyncio
import logging
from collections import deque
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.interview import ProctoringViolation
logger = logging.getLogger(name)
In-memory queue for failed DB writes
maxlen=50 automatically drops oldest on overflow
_violation_queue = deque(maxlen=50)
async def log_violation(
db: Session,
session_id: int,
event_type: str,
confidence_score: float = None,
face_count: int = None,
metadata: dict = None
) -> bool:
"""
Persist violation to database with retry logic.
  Retry delays: 0s, 1s, 2s (3 attempts total)
  On all failures: queue for later retry.
  Returns True if saved, False if queued.
  Never raises — always returns.
  """
  violation_data = {
      "session_id": session_id,
      "event_type": event_type,
      "confidence_score": confidence_score,
      "face_count": face_count,
      "metadata": metadata or {},
      "created_at": datetime.utcnow()
  }
  
  delays = [0, 1, 2]  # seconds between retries
  
  for attempt, delay in enumerate(delays):
      if delay > 0:
          await asyncio.sleep(delay)
      
      try:
          violation = ProctoringViolation(
              **violation_data
          )
          db.add(violation)
          db.commit()
          
          # On success: try to flush queue
          await flush_queue(db)
          return True
      
      except Exception as e:
          logger.warning(
              f"[ViolationLog] Attempt {attempt+1} "
              f"failed: {e}"
          )
          db.rollback()
  
  # All retries failed — queue it
  logger.error(
      f"[ViolationLog] All retries failed. "
      f"Queuing violation: {event_type}"
  )
  _violation_queue.append(violation_data)
  return False
async def flush_queue(db: Session):
"""
Attempt to save queued violations to DB.
Called after every successful DB write.
"""
if not _violation_queue:
return
  saved = []
  for violation_data in list(_violation_queue):
      try:
          violation = ProctoringViolation(
              **violation_data
          )
          db.add(violation)
          db.commit()
          saved.append(violation_data)
      except Exception:
          db.rollback()
          break  # stop on first failure
  
  for item in saved:
      try:
          _violation_queue.remove(item)
      except ValueError:
          pass
  
  if saved:
      logger.info(
          f"[ViolationLog] Flushed {len(saved)} "
          f"queued violations"
      )

---

### 2.6 Backend: New Endpoints
File: app/modules/interview/routers/interview_router.py
[ADD] these two new endpoints.
Do not modify any existing endpoints.
Required imports to add:
from app.services.phone_detection_service import detect_phones
from app.services.proctoring_logger import log_violation
from fastapi import UploadFile, File
import asyncio
─── ENDPOINT 1: analyze-frame ───
POST /interview/advanced-proctoring/analyze-frame
Purpose: Receive frame from frontend, run YOLO,
log phone violations, return results.
     This is the ONLY path for phone detections.
     Frontend does NOT separately call log-event
     for phone violations.
@router.post("/advanced-proctoring/analyze-frame")
async def analyze_frame(
frame: UploadFile = File(...),
session_id: int = Query(...),
db: Session = Depends(get_db),
current_user = Depends(get_current_user)
):
# Validate session belongs to user
session = db.query(InterviewSession).filter(
InterviewSession.id == session_id
).first()
if not session:
raise HTTPException(status_code=404,
detail="Session not found")
# Read frame bytes
frame_bytes = await frame.read()

# Run YOLO phone detection
detections = detect_phones(frame_bytes)

# Log each phone detection as separate violation
violations_logged = []
for detection in detections:
    await log_violation(
        db=db,
        session_id=session_id,
        event_type="mobile_phone",
        confidence_score=detection["confidence"],
        metadata={
            "bbox": detection["bbox"],
            "frame_size": "320x240"
        }
    )
    violations_logged.append({
        "type": "mobile_phone",
        "confidence": detection["confidence"]
    })

return {
    "violations": violations_logged,
    "phone_count": len(detections)
}
─── ENDPOINT 2: log-event ───
POST /interview/advanced-proctoring/log-event
Purpose: Receive violation events from frontend
for non-vision violations (tab switch,
fullscreen exit, multiple persons,
microphone denied).
Schema:
class LogEventRequest(BaseModel):
session_id: int
event_type: str
# Values: 'tab_switch', 'fullscreen_exit',
#         'multiple_persons', 'mic_denied',
#         'idle'
confidence_score: float = None
face_count: int = None
metadata: dict = None
@router.post("/advanced-proctoring/log-event")
async def log_proctoring_event(
request: LogEventRequest,
db: Session = Depends(get_db),
current_user = Depends(get_current_user)
):
# Validate session belongs to user
session = db.query(InterviewSession).filter(
InterviewSession.id == request.session_id,
InterviewSession.session_id.in_(
# subquery: sessions belonging to user
db.query(AssessmentSession.id).filter(
AssessmentSession.user_id == current_user.id
)
)
).first()
if not session:
    raise HTTPException(
        status_code=400,
        detail="Invalid session_id for this user"
    )

success = await log_violation(
    db=db,
    session_id=request.session_id,
    event_type=request.event_type,
    confidence_score=request.confidence_score,
    face_count=request.face_count,
    metadata=request.metadata
)

return {
    "status": "logged" if success else "queued",
    "event_type": request.event_type
}

---

### 2.7 Backend: Startup Warmup
File: app/main.py
[MODIFY] Add YOLO warmup to existing lifespan:
@asynccontextmanager
async def lifespan(app: FastAPI):
# Existing warmup (embedding model, KB index)
# ... keep as-is ...
  # NEW: Warm up YOLO model
  try:
      from app.services.phone_detection_service import (
          get_yolo_model
      )
      get_yolo_model()
      print("[Startup] YOLOv8n model ready")
  except Exception as e:
      print(f"[Startup] YOLO warmup failed: {e}")
      print("[Startup] Phone detection unavailable")
      # Non-fatal — interview works without YOLO
  
  yield

---

### 2.8 Frontend: useAdvancedProctoring.js Extension
File: frontend/src/hooks/useAdvancedProctoring.js
[MODIFY] — extend existing hook.
Do NOT rewrite the entire hook.
ADD these pieces to the existing implementation.
── 2.8.1 Add frame capture for phone detection ──
Add new ref at top of hook:
const frameIntervalRef = useRef(null);
const frameProcessingTimeRef = useRef([]); // last 3 times
const frameIntervalMs = useRef(2000); // adaptive rate
Add frame capture function:
const captureAndAnalyzeFrame = async () => {
if (!videoRef?.current) return;
const start = performance.now();

try {
  // Draw video frame to offscreen canvas
  const canvas = document.createElement('canvas');
  canvas.width = 320;
  canvas.height = 240;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(videoRef.current, 0, 0, 320, 240);
  
  // Convert to blob (70% JPEG quality)
  const blob = await new Promise(resolve => {
    canvas.toBlob(resolve, 'image/jpeg', 0.7);
  });
  
  if (!blob) return;
  
  // POST to analyze-frame
  const formData = new FormData();
  formData.append('frame', blob, 'frame.jpg');
  
  const response = await api.post(
    `/interview/advanced-proctoring/analyze-frame` +
    `?session_id=${sessionId}`,
    formData,
    {headers: {'Content-Type': 'multipart/form-data'}}
  );
  
  // Trigger violation alert if phones detected
  if (response.data.phone_count > 0) {
    onViolation?.({
      type: 'mobile_phone',
      count: response.data.phone_count,
      violations: response.data.violations
    });
  }
  
} catch (err) {
  console.warn('[Proctoring] Frame analysis failed:', err);
}

// Adaptive rate adjustment
const elapsed = performance.now() - start;
frameProcessingTimeRef.current.push(elapsed);
if (frameProcessingTimeRef.current.length > 3) {
  frameProcessingTimeRef.current.shift();
}

adjustFrameRate(elapsed);
};
const adjustFrameRate = (latestMs) => {
const times = frameProcessingTimeRef.current;
// Slow: latest frame > 400ms → reduce to 5s
if (latestMs > 400) {
  if (frameIntervalMs.current !== 5000) {
    frameIntervalMs.current = 5000;
    restartFrameInterval();
    console.warn('[Proctoring] Slow frame, reducing rate');
  }
  return;
}

// Fast: all last 3 frames < 200ms → restore to 2s
if (times.length === 3 && times.every(t => t < 200)) {
  if (frameIntervalMs.current !== 2000) {
    frameIntervalMs.current = 2000;
    restartFrameInterval();
    console.info('[Proctoring] Fast frames, restoring rate');
  }
}
};
const restartFrameInterval = () => {
clearInterval(frameIntervalRef.current);
frameIntervalRef.current = setInterval(
captureAndAnalyzeFrame,
frameIntervalMs.current
);
};
Start frame capture when interview is active:
// Add to existing useEffect that starts proctoring:
frameIntervalRef.current = setInterval(
captureAndAnalyzeFrame,
2000
);
Stop frame capture on cleanup:
// Add to existing cleanup return:
clearInterval(frameIntervalRef.current);
── 2.8.2 Extend multiple person detection ──
In existing MediaPipe face detection callback,
add person count check:
// Find the existing onResults callback for MediaPipe
// It already processes face landmarks
// ADD this after existing face detection logic:
const faceCount = results.multiFaceLandmarks?.length ?? 0;
if (faceCount > 1) {
// Check 10-second deduplication window
const now = Date.now();
const lastMultiPerson = lastViolationTimeRef.current
?.multiple_persons ?? 0;
if (now - lastMultiPerson > 10000) {
  lastViolationTimeRef.current = {
    ...lastViolationTimeRef.current,
    multiple_persons: now
  };
  
  // Log to backend
  api.post('/interview/advanced-proctoring/log-event', {
    session_id: sessionId,
    event_type: 'multiple_persons',
    face_count: faceCount,
    metadata: {detected_at: new Date().toISOString()}
  }).catch(err => 
    console.warn('[Proctoring] Log failed:', err)
  );
  
  // Trigger alert
  onViolation?.({
    type: 'multiple_persons',
    count: faceCount
  });
}
}
Add lastViolationTimeRef:
const lastViolationTimeRef = useRef({});

---

### 2.9 Frontend: ViolationAlert.jsx (NEW FILE)
File: frontend/src/components/ViolationAlert.jsx
Props:
violation: {type: string, count?: number} | null
onDismiss: fn
Behavior:
When violation prop changes to non-null:
Slide in from top-right
Auto-dismiss after 5 seconds
New violation replaces current (not stacked)
Position: fixed, top-4 right-4, z-50
Never blocks interview content
State:
const [visible, setVisible] = useState(false);
const dismissTimerRef = useRef(null);
useEffect(() => {
if (!violation) return;
// Clear existing timer
clearTimeout(dismissTimerRef.current);

// Show alert
setVisible(true);

// Auto-dismiss after 5 seconds
dismissTimerRef.current = setTimeout(() => {
  setVisible(false);
  onDismiss?.();
}, 5000);

return () => clearTimeout(dismissTimerRef.current);
}, [violation]);
Messages:
const getMessage = (type) => {
switch(type) {
case 'mobile_phone':
return '⚠ Mobile phone detected';
case 'multiple_persons':
return '⚠ Multiple people detected';
default:
return '⚠ Proctoring violation';
}
};
JSX:
return (
<div className={      fixed top-4 right-4 z-50       transform transition-all duration-300 ease-out       ${visible          ? 'translate-x-0 opacity-100'          : 'translate-x-full opacity-0'       }    }>
{violation && (
<div className="
       bg-red-900/90 border border-red-500
       text-red-100 px-4 py-3 rounded-xl
       shadow-lg max-w-xs
       flex items-center gap-2
     ">
<span className="text-sm font-medium">
{getMessage(violation.type)}
</span>
{violation.count > 1 && (
<span className="text-red-300 text-xs">
({violation.count} detected)
</span>
)}
</div>
)}
</div>
);
Cleanup:
useEffect(() => {
return () => clearTimeout(dismissTimerRef.current);
}, []);

---

### 2.10 Frontend: HumanLikeInterview.jsx Proctoring Integration
File: frontend/src/pages/HumanLikeInterview.jsx
[MODIFY] — add violation alert state and handler
New state:
const [activeViolation, setActiveViolation] = useState(null);
Violation handler (passed to useAdvancedProctoring):
const handleViolation = (violation) => {
setActiveViolation(violation);
};
Pass to existing proctoring hook:
const proctoring = useAdvancedProctoring({
idleThreshold: 30,
roundType: "INTERVIEW",
sessionId: interviewId,
onViolation: handleViolation  // ADD THIS
});
Add ViolationAlert to JSX (inside interview room layout):
import ViolationAlert from '../components/ViolationAlert';
// Add inside interview room return, as first child:
<ViolationAlert
violation={activeViolation}
onDismiss={() => setActiveViolation(null)}
/>
// This renders fixed-positioned, does not affect layout
Update useAdvancedProctoring hook signature to accept:
sessionId: string|number  (used for API calls)
onViolation: function     (callback for violations)

---

## PART 3: SERVICES FILE
File: frontend/src/services/interviewService.js
[ADD] these two functions:
export const analyzeFrame = (sessionId, frameBlob) => {
const formData = new FormData();
formData.append('frame', frameBlob, 'frame.jpg');
return api.post(
/interview/advanced-proctoring/analyze-frame +
?session_id=${sessionId},
formData,
{headers: {'Content-Type': 'multipart/form-data'}}
);
};
export const logProctoringEvent = (
sessionId,
eventType,
options = {}
) => {
return api.post(
'/interview/advanced-proctoring/log-event',
{
session_id: sessionId,
event_type: eventType,
confidence_score: options.confidenceScore ?? null,
face_count: options.faceCount ?? null,
metadata: options.metadata ?? {}
}
);
};

---

## PART 4: BUILD ORDER
Follow this exact sequence.
Verify each step before proceeding.
── BACKEND FIRST ──
Step 1: Install packages
pip install ultralytics opencv-python-headless
Add to requirements.txt
Step 2: Create alembic migration
File: alembic/versions/add_proctoring_violations.py
Run: alembic upgrade head
Verify: proctoring_violations table exists in DB
Step 3: Add ProctoringViolation model
File: app/models/interview.py
Import in app/models/init.py
Step 4: Create phone detection service
File: app/services/phone_detection_service.py
Test: python -c "
from app.services.phone_detection_service
import get_yolo_model
m = get_yolo_model()
print('YOLO loaded:', m is not None)
"
Expected: downloads yolov8n.pt, prints True
Step 5: Create proctoring logger
File: app/services/proctoring_logger.py
Step 6: Add new endpoints to interview_router.py
POST /advanced-proctoring/analyze-frame
POST /advanced-proctoring/log-event
Step 7: Update main.py lifespan
Add YOLO warmup
Step 8: Backend smoke tests
Start: uvicorn app.main:app --reload
Check logs:
"[Startup] YOLOv8n model ready"
"[Startup] Embedding model ready"
Test analyze-frame endpoint:
curl -X POST 
"http://localhost:8000/interview/advanced-proctoring/analyze-frame?session_id=1" 
-H "Authorization: Bearer {token}" 
-F "frame=@test_frame.jpg"
Expected: {"violations": [], "phone_count": 0}
Test log-event endpoint:
curl -X POST 
"http://localhost:8000/interview/advanced-proctoring/log-event" 
-H "Authorization: Bearer {token}" 
-H "Content-Type: application/json" 
-d '{"session_id": 1, "event_type": "tab_switch"}'
Expected: {"status": "logged", "event_type": "tab_switch"}
── FRONTEND SECOND ──
Step 9: Create TimerComponent.jsx
Test: render with difficulty EASY → shows 01:00 countdown
Test: countdown reaches 0 → onThinkingComplete fires
Test: "Start Answering Early" button fires onEarlyStart
Step 10: Create RecordingManager.jsx
Test: startRecording() requests mic permission
Test: stopRecording() creates audio blob
Test: maxSeconds=5 auto-stops after 5 seconds
Step 11: Create ViolationAlert.jsx
Test: violation prop set → alert slides in
Test: after 5 seconds → alert slides out
Test: new violation during alert → replaces current
Step 12: Add to interviewService.js
analyzeFrame()
logProctoringEvent()
Step 13: Extend useAdvancedProctoring.js
Add frame capture interval
Add multi-person detection logging
Add onViolation callback support
Step 14: Update HumanLikeInterview.jsx
Add INTERVIEW_STATES state machine
Add TimerComponent integration
Add RecordingManager integration
Add ViolationAlert
Pass onViolation to proctoring hook
── INTEGRATION TESTS ──
Step 15: Full end-to-end test:
□ Question loads → "Thinking Time" timer starts
□ EASY question → 01:00 timer shows
□ MEDIUM question → 01:30 timer shows
□ HARD question → 02:00 timer shows
□ Timer reaches 0 → recording starts automatically
□ "Start Answering Early" → recording starts immediately
□ Recording indicator shows (red pulsing dot)
□ "Stop Recording" button visible during recording
□ Click Stop → processing spinner shows
□ After 180s → auto-stops with toast warning
□ Response submits → next question loads with timer
□ Hold phone to camera → red alert slides in top-right
□ Alert: "⚠ Mobile phone detected"
□ Alert auto-dismisses after 5 seconds
□ Second person enters frame → "⚠ Multiple people detected"
□ Same violation within 10s → NOT logged again
□ Different violation during alert → replaces current
□ proctoring_violations table has entries after test

---

## PART 5: HARD CONSTRAINTS
TIMER:
✔ Duration configurable by difficulty (60/90/120s)
✔ "Start Answering Early" button always visible during thinking
✔ Max recording time 180 seconds — never exceeded
✔ Auto-stop submits audio as-is with toast warning
✔ Timer resets on every new question
DETECTION:
✔ Frontend runs MediaPipe ONLY (face counting)
✔ Backend runs YOLOv8n ONLY (phone detection)
✔ No duplicate face detection systems
✔ YOLO loads ONCE at startup — never per request
✔ Frame size 320x240, JPEG 70% quality
✔ Frame interval starts at 2s, adapts based on latency
ADAPTIVE RATE:
✔ Single frame >400ms → reduce to 5s interval
✔ Three consecutive frames <200ms → restore to 2s
✔ Measured with performance.now()
VIOLATIONS:
✔ Multiple person: deduplicated per 10-second window
✔ Phone detection: each phone logged separately
✔ DB retry: 0s, 1s, 2s delays
✔ Failed violations: queued in memory (max 50)
✔ Queue flushed on next successful DB write
ALERTS:
✔ Position: fixed top-4 right-4 z-50
✔ Auto-dismiss: 5 seconds
✔ No pause to timer or recording
✔ No candidate acknowledgment required
✔ New violation replaces current (not stacked)
EXISTING CODE:
✔ useAdvancedProctoring.js extended, not replaced
✔ All existing proctoring behavior preserved
✔ /respond, /next, /stt, /tts endpoints untouched
✔ All coding module files untouched
✔ All aptitude files untouched

---

## PART 6: WHAT TO SAY TO GUIDE/EXAMINER
On the timer system:
"We implemented a difficulty-adaptive thinking timer
that gives candidates 60, 90, or 120 seconds based on
question difficulty. Recording starts automatically
when thinking time expires, or candidates can skip
ahead with early start. A hard cap of 180 seconds
prevents unbounded recording."
On phone detection:
"Mobile phone detection uses YOLOv8n, a lightweight
6MB model that detects COCO class 67 (cell phone)
with 60% confidence threshold. The model loads once
at startup and processes 320x240 compressed frames
every 2 seconds. Frame rate adapts automatically:
if processing exceeds 400ms, rate drops to 5 seconds
until performance recovers."
On multi-person detection:
"Multiple person detection extends our existing
MediaPipe face detection — we count faces per frame
rather than just detecting one. Violations are
deduplicated with a 10-second window to prevent
log flooding from a persistent violation."
On violation logging:
"All violations persist to PostgreSQL with exponential
retry: 0, 1, and 2 second delays. Failed writes queue
in memory up to 50 entries and flush on the next
successful database connection."



---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Timer Duration Mapping

*For any* question difficulty level (EASY, MEDIUM, HARD, or unknown), the timer component should initialize with the correct duration: 60 seconds for EASY, 90 seconds for MEDIUM, 120 seconds for HARD, and 90 seconds (default) for any unknown difficulty value.

**Validates: Requirements 1.2, 1.3, 1.4**

### Property 2: Timer Countdown Accuracy

*For any* initial timer duration and any elapsed time less than that duration, after waiting the elapsed time, the timer display should show the remaining time (duration minus elapsed time) in MM:SS format.

**Validates: Requirements 1.5, 1.7**

### Property 3: Recording Time Counting

*For any* elapsed recording time, when the recording manager is in recording mode, the displayed elapsed time should accurately reflect the number of seconds since recording started.

**Validates: Requirements 4.2**

### Property 4: Violation Threshold Filtering

*For any* detection with a confidence score, if the confidence is above the threshold (0.6 for phones, 0.7 for faces), then a violation should be logged; if below the threshold, no violation should be logged.

**Validates: Requirements 5.4, 6.5**

### Property 5: Violation Record Completeness

*For any* logged violation, the database record should contain all required fields: session_id, event_type, timestamp, and type-specific fields (confidence_score for phone detections, face_count for multiple person violations).

**Validates: Requirements 5.5, 6.4, 7.2**

### Property 6: Multiple Detection Logging

*For any* frame containing N detected objects (where N > 1), the system should create N separate violation log entries, one for each detected object.

**Validates: Requirements 5.6**

### Property 7: Face Count Detection

*For any* video frame, the system should count the number of distinct faces and log a multiple person violation if and only if the count is greater than 1.

**Validates: Requirements 6.2, 6.3**

### Property 8: Violation Deduplication

*For any* violation type, if the same violation is detected multiple times within a 10-second window, only the first occurrence should be logged to the database.

**Validates: Requirements 6.6**

### Property 9: Violation Persistence

*For any* detected violation, a corresponding record should be created in the proctoring_violations table with the correct session_id associating it to the active interview session.

**Validates: Requirements 7.1, 7.3**

### Property 10: Database Write Latency

*For any* violation detection, the time between detection and successful database persistence should be less than 1 second under normal conditions.

**Validates: Requirements 7.4**

### Property 11: Session Authorization

*For any* API request to log a proctoring event, if the session_id in the request does not belong to the authenticated user, the request should be rejected with a 400 or 403 status code.

**Validates: Requirements 11.3, 11.5**

### Property 12: Frame Processing Performance

*For any* video frame submitted for analysis, the detection model should complete processing in less than 500 milliseconds, or skip the frame and log a warning if processing exceeds this threshold.

**Validates: Requirements 12.1, 12.2**

### Property 13: Time Format Consistency

*For any* number of seconds (0 to 3600), the formatTime function should return a string in MM:SS format where MM is zero-padded minutes and SS is zero-padded seconds.

**Validates: Requirements 1.7**

---

## Error Handling

### Timer and Recording Errors

**Microphone Permission Denied:**
- Display user-friendly error message: "Microphone access denied. Please allow microphone access and refresh the page."
- Log proctoring event with event_type="mic_denied"
- Do not crash or block interview flow
- Allow user to retry by refreshing

**Recording Timeout:**
- Auto-stop recording at 180 seconds
- Display toast notification: "Maximum recording time reached. Submitting your answer."
- Submit audio as-is without requiring user action
- Continue to next question normally

**MediaRecorder API Failure:**
- Catch and log all MediaRecorder errors
- Display error message to user
- Provide manual retry option
- Fall back to text input if audio fails repeatedly

### Detection Model Errors

**YOLO Model Load Failure:**
- Log error during startup: "[Startup] YOLO warmup failed: {error}"
- Continue application startup (non-fatal)
- Phone detection unavailable but interview continues
- Log warning on each frame analysis attempt

**Frame Processing Failure:**
- Catch all inference exceptions
- Log error: "[YOLO] Inference failed: {error}"
- Return empty detections list
- Continue processing subsequent frames
- Never crash the detection service

**MediaPipe Face Detection Failure:**
- Catch all MediaPipe exceptions
- Log error to console
- Skip face counting for that frame
- Continue with next frame
- Preserve existing proctoring functionality

### Database and Network Errors

**Database Write Failure:**
- Retry with delays: 0s, 1s, 2s (3 attempts total)
- On all failures: add to in-memory queue (max 50 items)
- Queue uses FIFO eviction when full
- Flush queue on next successful write
- Never block interview flow

**Network Timeout:**
- Set reasonable timeouts for all API calls (5 seconds)
- Display user-friendly error messages
- Provide retry mechanisms
- Cache violations locally if backend unreachable
- Sync when connection restored

**Frame Upload Failure:**
- Log warning: "[Proctoring] Frame analysis failed: {error}"
- Skip the failed frame
- Continue with next frame interval
- Do not alert user (silent failure)
- Maintain adaptive rate adjustment

### State Management Errors

**Component Unmount During Recording:**
- Clean up all timers and intervals
- Stop MediaRecorder and release tracks
- Discard incomplete audio
- Do not submit partial recordings
- Prevent memory leaks

**Invalid State Transitions:**
- Validate state transitions before applying
- Log invalid transition attempts
- Recover to last known good state
- Display error message if recovery fails
- Provide manual reset option

---

## Testing Strategy

### Dual Testing Approach

This feature requires both **unit tests** and **property-based tests** for comprehensive coverage:

- **Unit tests**: Verify specific examples, edge cases, error conditions, and UI interactions
- **Property tests**: Verify universal properties across randomized inputs

### Unit Testing Focus

Unit tests should cover:

1. **Timer Component:**
   - Specific example: EASY question shows 01:00
   - Specific example: MEDIUM question shows 01:30
   - Specific example: HARD question shows 02:00
   - Edge case: Timer reaches 0 triggers callback
   - Edge case: Early start button triggers callback
   - UI: "Thinking Time" label displays correctly
   - UI: Recording indicator shows during recording mode

2. **Recording Manager:**
   - Example: startRecording() requests microphone permission
   - Example: stopRecording() creates audio blob
   - Example: Max timer (180s) auto-stops recording
   - Error: Permission denied shows error message
   - Error: Permission denied logs proctoring event
   - Integration: Audio blob sent to STT endpoint
   - Integration: Response submitted to /respond endpoint

3. **Violation Alert:**
   - Example: Phone violation shows "⚠ Mobile phone detected"
   - Example: Multiple person violation shows "⚠ Multiple people detected"
   - Example: Alert auto-dismisses after 5 seconds
   - Example: New violation replaces current alert
   - UI: Alert positioned top-right corner
   - UI: Alert uses correct styling (red background, border)

4. **Phone Detection Service:**
   - Example: Image with phone returns detection
   - Example: Image without phone returns empty list
   - Example: Multiple phones return multiple detections
   - Edge case: Invalid image bytes return empty list
   - Edge case: Processing >500ms skips frame and logs warning
   - Integration: YOLO model loads at startup

5. **Proctoring Logger:**
   - Example: Successful write returns True
   - Example: Failed write after 3 retries queues violation
   - Example: Queue flush on next successful write
   - Edge case: Queue overflow drops oldest entries
   - Error: Database exception triggers retry logic

6. **API Endpoints:**
   - Example: Valid analyze-frame request returns violations
   - Example: Valid log-event request returns 200 status
   - Error: Invalid session_id returns 400/403
   - Error: Missing required fields returns 400
   - Integration: Violations persisted to database

### Property-Based Testing Configuration

**Library Selection:**
- **Python backend**: Use `hypothesis` library
- **JavaScript frontend**: Use `fast-check` library

**Test Configuration:**
- Minimum **100 iterations** per property test
- Each test tagged with: `Feature: interview-enhancements, Property {N}: {property_text}`
- Use appropriate generators for each property

**Property Test Implementation:**

1. **Property 1: Timer Duration Mapping**
   ```python
   @given(difficulty=st.sampled_from(['EASY', 'MEDIUM', 'HARD', 'UNKNOWN', None]))
   def test_timer_duration_mapping(difficulty):
       expected = {'EASY': 60, 'MEDIUM': 90, 'HARD': 120}.get(difficulty, 90)
       actual = get_timer_duration(difficulty)
       assert actual == expected
   ```
   Tag: `Feature: interview-enhancements, Property 1: Timer Duration Mapping`

2. **Property 2: Timer Countdown Accuracy**
   ```javascript
   fc.assert(
     fc.property(
       fc.integer({min: 60, max: 180}), // duration
       fc.integer({min: 0, max: 179}),  // elapsed
       (duration, elapsed) => {
         fc.pre(elapsed < duration);
         const remaining = duration - elapsed;
         const formatted = formatTime(remaining);
         const [mm, ss] = formatted.split(':').map(Number);
         return mm * 60 + ss === remaining;
       }
     ),
     { numRuns: 100 }
   );
   ```
   Tag: `Feature: interview-enhancements, Property 2: Timer Countdown Accuracy`

3. **Property 4: Violation Threshold Filtering**
   ```python
   @given(
       confidence=st.floats(min_value=0.0, max_value=1.0),
       violation_type=st.sampled_from(['phone', 'face'])
   )
   def test_violation_threshold_filtering(confidence, violation_type):
       threshold = 0.6 if violation_type == 'phone' else 0.7
       should_log = confidence >= threshold
       result = should_log_violation(confidence, violation_type)
       assert result == should_log
   ```
   Tag: `Feature: interview-enhancements, Property 4: Violation Threshold Filtering`

4. **Property 5: Violation Record Completeness**
   ```python
   @given(
       event_type=st.sampled_from(['mobile_phone', 'multiple_persons']),
       confidence=st.floats(min_value=0.6, max_value=1.0),
       face_count=st.integers(min_value=2, max_value=10)
   )
   def test_violation_record_completeness(event_type, confidence, face_count):
       violation = create_violation_record(
           session_id=1,
           event_type=event_type,
           confidence_score=confidence if event_type == 'mobile_phone' else None,
           face_count=face_count if event_type == 'multiple_persons' else None
       )
       assert violation.session_id is not None
       assert violation.event_type is not None
       assert violation.created_at is not None
       if event_type == 'mobile_phone':
           assert violation.confidence_score is not None
       if event_type == 'multiple_persons':
           assert violation.face_count is not None
   ```
   Tag: `Feature: interview-enhancements, Property 5: Violation Record Completeness`

5. **Property 6: Multiple Detection Logging**
   ```python
   @given(detection_count=st.integers(min_value=2, max_value=10))
   def test_multiple_detection_logging(detection_count):
       detections = [
           {'confidence': 0.8, 'bbox': [0, 0, 100, 100]}
           for _ in range(detection_count)
       ]
       violations = log_detections(detections, session_id=1)
       assert len(violations) == detection_count
   ```
   Tag: `Feature: interview-enhancements, Property 6: Multiple Detection Logging`

6. **Property 7: Face Count Detection**
   ```python
   @given(face_count=st.integers(min_value=0, max_value=10))
   def test_face_count_detection(face_count):
       should_log = face_count > 1
       result = should_log_multiple_persons(face_count)
       assert result == should_log
   ```
   Tag: `Feature: interview-enhancements, Property 7: Face Count Detection`

7. **Property 8: Violation Deduplication**
   ```python
   @given(
       time_between_ms=st.integers(min_value=0, max_value=20000),
       event_type=st.sampled_from(['mobile_phone', 'multiple_persons'])
   )
   def test_violation_deduplication(time_between_ms, event_type):
       first_logged = log_violation_with_dedup(event_type, timestamp=0)
       second_logged = log_violation_with_dedup(
           event_type,
           timestamp=time_between_ms
       )
       should_log_second = time_between_ms > 10000
       assert first_logged == True
       assert second_logged == should_log_second
   ```
   Tag: `Feature: interview-enhancements, Property 8: Violation Deduplication`

8. **Property 11: Session Authorization**
   ```python
   @given(
       user_id=st.integers(min_value=1, max_value=100),
       session_owner_id=st.integers(min_value=1, max_value=100)
   )
   def test_session_authorization(user_id, session_owner_id):
       is_authorized = user_id == session_owner_id
       try:
           validate_session_ownership(user_id, session_owner_id)
           assert is_authorized
       except HTTPException as e:
           assert not is_authorized
           assert e.status_code in [400, 403]
   ```
   Tag: `Feature: interview-enhancements, Property 11: Session Authorization`

9. **Property 12: Frame Processing Performance**
   ```python
   @given(
       frame_data=st.binary(min_size=1000, max_size=50000)
   )
   def test_frame_processing_performance(frame_data):
       start = time.time()
       result = detect_phones(frame_data)
       elapsed = time.time() - start
       
       # Either completes in <500ms or returns empty (skipped)
       if elapsed > 0.5:
           assert result == []
       # If it completes fast, result can be anything
   ```
   Tag: `Feature: interview-enhancements, Property 12: Frame Processing Performance`

10. **Property 13: Time Format Consistency**
    ```javascript
    fc.assert(
      fc.property(
        fc.integer({min: 0, max: 3600}),
        (seconds) => {
          const formatted = formatTime(seconds);
          const regex = /^\d{2}:\d{2}$/;
          if (!regex.test(formatted)) return false;
          
          const [mm, ss] = formatted.split(':').map(Number);
          return mm * 60 + ss === seconds && ss < 60;
        }
      ),
      { numRuns: 100 }
    );
    ```
    Tag: `Feature: interview-enhancements, Property 13: Time Format Consistency`

### Integration Testing

Integration tests should verify:

1. **End-to-End Timer Flow:**
   - Question loads → thinking timer starts
   - Timer reaches 0 → recording starts automatically
   - Recording active → stop button works
   - Stop clicked → audio submitted → next question loads

2. **End-to-End Proctoring Flow:**
   - Frame captured → sent to backend
   - Backend detects phone → violation logged
   - Frontend receives response → alert displays
   - Alert auto-dismisses after 5 seconds

3. **Database Integration:**
   - Violation logged → record in database
   - Retry logic → queued violations flushed
   - Session association → correct foreign keys

4. **Error Recovery:**
   - Database down → violations queued
   - Database restored → queue flushed
   - Model failure → graceful degradation

### Performance Testing

Performance tests should verify:

1. Frame processing completes in <500ms (95th percentile)
2. Database writes complete in <1 second (95th percentile)
3. Timer updates render without jank (60fps)
4. Adaptive rate adjustment responds within 3 frames
5. Memory usage stable over 30-minute interview

### Manual Testing Checklist

- [ ] EASY question shows 01:00 timer
- [ ] MEDIUM question shows 01:30 timer
- [ ] HARD question shows 02:00 timer
- [ ] Timer counts down correctly
- [ ] Timer reaches 0 → recording starts
- [ ] "Start Answering Early" button works
- [ ] Recording indicator shows (red pulsing dot)
- [ ] Recording timer counts up
- [ ] Stop button stops recording
- [ ] Max 180s auto-stops with toast
- [ ] Hold phone to camera → alert shows
- [ ] Alert: "⚠ Mobile phone detected"
- [ ] Alert auto-dismisses after 5 seconds
- [ ] Second person → "⚠ Multiple people detected"
- [ ] Same violation within 10s → not logged again
- [ ] New violation during alert → replaces current
- [ ] Database has violation records after test
- [ ] Interview continues normally with violations
- [ ] Microphone denied → error message shows
- [ ] Frame processing adapts to slow performance
