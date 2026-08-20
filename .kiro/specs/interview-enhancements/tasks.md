# Implementation Plan: Interview System Enhancements

## Overview

This implementation plan breaks down the interview system enhancements into discrete coding tasks. The plan follows a backend-first approach to ensure infrastructure is ready before frontend integration. Each task builds incrementally with validation checkpoints.

## Tasks

- [x] 1. Backend Infrastructure Setup
  - Install required Python packages (ultralytics, opencv-python-headless)
  - Add packages to requirements.txt
  - Verify YOLO model downloads successfully
  - _Requirements: 9.1, 9.4_

- [~] 2. Database Schema and Models
  - [x] 2.1 Create Alembic migration for proctoring_violations table
    - Create migration file: `alembic/versions/add_proctoring_violations.py`
    - Define table with columns: id, session_id, event_type, confidence_score, face_count, metadata, created_at
    - Add foreign key constraint to interview_sessions table
    - Create index on (session_id, created_at)
    - Run migration: `alembic upgrade head`
    - _Requirements: 7.1, 7.2_
  
  - [x] 2.2 Add ProctoringViolation model to app/models/interview.py
    - Define SQLAlchemy model matching migration schema
    - Add relationship to InterviewSession if needed
    - Import model in `app/models/__init__.py`
    - _Requirements: 7.1, 7.2_

- [~] 3. Phone Detection Service
  - [x] 3.1 Create app/services/phone_detection_service.py
    - Implement `get_yolo_model()` singleton function
    - Implement `detect_phones(image_bytes)` function
    - Use YOLOv8n model with COCO class 67 (cell phone)
    - Apply confidence threshold of 0.6
    - Return list of detections with confidence and bbox
    - Handle errors gracefully (return empty list, never raise)
    - Log warnings for slow processing (>500ms)
    - _Requirements: 5.3, 5.4, 9.4, 9.6, 9.7, 12.1, 12.2_
  
  - [ ] 3.2 Write property test for phone detection threshold filtering
    - **Property 4: Violation Threshold Filtering**
    - **Validates: Requirements 5.4**
    - Generate random confidence scores (0.0 to 1.0)
    - Verify detections above 0.6 are included, below are filtered
    - Use hypothesis library with 100 iterations
    - Tag: `Feature: interview-enhancements, Property 4: Violation Threshold Filtering`
  
  - [~] 3.3 Write unit tests for phone detection service
    - Test: Image with phone returns detection
    - Test: Image without phone returns empty list
    - Test: Invalid image bytes return empty list
    - Test: Processing >500ms returns empty list and logs warning
    - _Requirements: 5.3, 9.6, 12.2_

- [~] 4. Proctoring Logger Service
  - [~] 4.1 Create app/services/proctoring_logger.py
    - Implement `log_violation()` async function with retry logic
    - Retry delays: 0s, 1s, 2s (3 attempts)
    - Implement in-memory queue (deque with maxlen=50)
    - Implement `flush_queue()` function
    - Handle all database exceptions gracefully
    - _Requirements: 7.4, 7.5, 7.6, 7.7, 7.8, 7.9_
  
  - [~] 4.2 Write unit tests for proctoring logger
    - Test: Successful write returns True
    - Test: Failed write after 3 retries queues violation
    - Test: Queue flush on next successful write
    - Test: Queue overflow drops oldest entries
    - Test: Retry timing is correct (0s, 1s, 2s)
    - _Requirements: 7.5, 7.6, 7.7, 7.8, 7.9_
  
  - [~] 4.3 Write property test for violation record completeness
    - **Property 5: Violation Record Completeness**
    - **Validates: Requirements 5.5, 6.4, 7.2**
    - Generate random violation types and data
    - Verify all required fields present in database record
    - Use hypothesis library with 100 iterations
    - Tag: `Feature: interview-enhancements, Property 5: Violation Record Completeness`

- [~] 5. Backend API Endpoints
  - [~] 5.1 Add POST /advanced-proctoring/analyze-frame endpoint
    - Add to `app/modules/interview/routers/interview_router.py`
    - Accept UploadFile (frame) and session_id query parameter
    - Validate session belongs to authenticated user
    - Call `detect_phones()` service
    - Log each detection as separate violation
    - Return violations list and phone_count
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_
  
  - [~] 5.2 Add POST /advanced-proctoring/log-event endpoint
    - Add to `app/modules/interview/routers/interview_router.py`
    - Create LogEventRequest schema (session_id, event_type, confidence_score, face_count, metadata)
    - Validate session belongs to authenticated user
    - Call `log_violation()` service
    - Return status (logged or queued) and event_type
    - _Requirements: 7.1, 11.1, 11.2, 11.3, 11.4, 11.5_
  
  - [~] 5.3 Write property test for session authorization
    - **Property 11: Session Authorization**
    - **Validates: Requirements 11.3, 11.5**
    - Generate random user_id and session_owner_id pairs
    - Verify authorization succeeds when IDs match
    - Verify 400/403 error when IDs don't match
    - Use hypothesis library with 100 iterations
    - Tag: `Feature: interview-enhancements, Property 11: Session Authorization`
  
  - [~] 5.4 Write unit tests for API endpoints
    - Test: Valid analyze-frame request returns violations
    - Test: Valid log-event request returns 200 status
    - Test: Invalid session_id returns 400/403
    - Test: Missing required fields returns 400
    - _Requirements: 11.2, 11.3, 11.4, 11.5_

- [~] 6. Backend Startup Integration
  - [~] 6.1 Update app/main.py lifespan function
    - Add YOLO model warmup call to existing lifespan
    - Wrap in try-except (non-fatal if fails)
    - Log success: "[Startup] YOLOv8n model ready"
    - Log failure: "[Startup] YOLO warmup failed: {error}"
    - _Requirements: 9.4_

- [~] 7. Checkpoint - Backend Smoke Tests
  - Start backend: `uvicorn app.main:app --reload`
  - Verify startup logs show YOLO model ready
  - Test analyze-frame endpoint with curl
  - Test log-event endpoint with curl
  - Verify proctoring_violations table receives records
  - _Ensure all tests pass, ask the user if questions arise._

- [~] 8. Frontend Timer Component
  - [~] 8.1 Create frontend/src/components/TimerComponent.jsx
    - Accept props: duration, mode, onThinkingComplete, onEarlyStart, isRecording, recordingSeconds
    - Implement countdown logic for thinking mode
    - Implement count-up logic for recording mode
    - Implement formatTime(seconds) function (MM:SS format)
    - Render SVG circle with progress animation
    - Show "Start Answering Early" button in thinking mode
    - Show recording indicator (pulsing red dot) in recording mode
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 4.1, 4.2, 4.3, 4.4_
  
  - [~] 8.2 Write property test for timer duration mapping
    - **Property 1: Timer Duration Mapping**
    - **Validates: Requirements 1.2, 1.3, 1.4**
    - Generate random difficulty values (EASY, MEDIUM, HARD, unknown)
    - Verify correct duration returned (60, 90, 120, 90)
    - Use fast-check library with 100 iterations
    - Tag: `Feature: interview-enhancements, Property 1: Timer Duration Mapping`
  
  - [~] 8.3 Write property test for timer countdown accuracy
    - **Property 2: Timer Countdown Accuracy**
    - **Validates: Requirements 1.5, 1.7**
    - Generate random duration and elapsed time
    - Verify remaining time calculated correctly
    - Use fast-check library with 100 iterations
    - Tag: `Feature: interview-enhancements, Property 2: Timer Countdown Accuracy`
  
  - [~] 8.4 Write property test for time format consistency
    - **Property 13: Time Format Consistency**
    - **Validates: Requirements 1.7**
    - Generate random seconds (0 to 3600)
    - Verify formatTime returns MM:SS format
    - Verify parsed time equals input seconds
    - Use fast-check library with 100 iterations
    - Tag: `Feature: interview-enhancements, Property 13: Time Format Consistency`
  
  - [~] 8.5 Write unit tests for TimerComponent
    - Test: EASY question shows 01:00
    - Test: MEDIUM question shows 01:30
    - Test: HARD question shows 02:00
    - Test: Timer reaches 0 triggers onThinkingComplete
    - Test: Early start button triggers onEarlyStart
    - Test: "Thinking Time" label displays in thinking mode
    - Test: Recording indicator shows in recording mode
    - _Requirements: 1.2, 1.3, 1.4, 1.6, 1.8, 4.1_

- [~] 9. Frontend Recording Manager
  - [~] 9.1 Create frontend/src/components/RecordingManager.jsx
    - Use useRef for mediaRecorder, audioChunks, stream, timers
    - Expose startRecording() and stopRecording() via useImperativeHandle
    - Request microphone permission in startRecording()
    - Handle permission denied error
    - Create MediaRecorder and collect audio chunks
    - Set max recording timer (180 seconds)
    - Stop recording and create audio blob in stopRecording()
    - Call onRecordingComplete(audioBlob, responseTimeSec)
    - Render "Stop Recording" button
    - Clean up timers and tracks on unmount
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 3.1, 3.2, 3.3, 3.4, 3.5_
  
  - [~] 9.2 Write unit tests for RecordingManager
    - Test: startRecording() requests microphone permission
    - Test: stopRecording() creates audio blob
    - Test: Max timer (180s) auto-stops recording
    - Test: Permission denied shows error message
    - Test: Permission denied logs proctoring event
    - Test: Stop button visible during recording
    - Test: Stop button disabled during processing
    - _Requirements: 2.4, 2.5, 2.6, 2.7, 3.1, 3.5_

- [~] 10. Frontend Violation Alert Component
  - [~] 10.1 Create frontend/src/components/ViolationAlert.jsx
    - Accept props: violation, onDismiss
    - Implement slide-in animation from top-right
    - Auto-dismiss after 5 seconds
    - Replace current alert when new violation arrives
    - Display correct message for each violation type
    - Apply correct styling (bg-red-900/90, border-red-500, text-red-100)
    - Position: fixed top-4 right-4 z-50
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 8.9, 8.10, 8.11, 8.12_
  
  - [~] 10.2 Write unit tests for ViolationAlert
    - Test: Phone violation shows "⚠ Mobile phone detected"
    - Test: Multiple person violation shows "⚠ Multiple people detected"
    - Test: Alert auto-dismisses after 5 seconds
    - Test: New violation replaces current alert
    - Test: Alert positioned top-right corner
    - Test: Alert uses correct styling
    - _Requirements: 8.4, 8.5, 8.7, 8.10, 8.11, 8.12_

- [~] 11. Frontend Interview Service Functions
  - [~] 11.1 Add functions to frontend/src/services/interviewService.js
    - Implement `analyzeFrame(sessionId, frameBlob)` function
    - Implement `logProctoringEvent(sessionId, eventType, options)` function
    - Use FormData for frame upload
    - Handle API errors gracefully
    - _Requirements: 5.1, 5.2, 11.1_

- [~] 12. Frontend Proctoring Hook Extension
  - [~] 12.1 Extend frontend/src/hooks/useAdvancedProctoring.js
    - Add frame capture interval (default 2 seconds)
    - Implement `captureAndAnalyzeFrame()` function
    - Capture frame at 320x240 resolution, 70% JPEG quality
    - POST frame to /advanced-proctoring/analyze-frame
    - Trigger onViolation callback for phone detections
    - Implement adaptive rate adjustment based on processing time
    - Implement `adjustFrameRate()` function (>400ms → 5s, <200ms for 3 frames → 2s)
    - Add multiple person detection to existing MediaPipe callback
    - Implement 10-second deduplication window
    - Log multiple person violations to backend
    - Clean up intervals on unmount
    - _Requirements: 5.1, 5.2, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 12.4, 12.5, 12.6, 12.7_
  
  - [~] 12.2 Write property test for face count detection
    - **Property 7: Face Count Detection**
    - **Validates: Requirements 6.2, 6.3**
    - Generate random face counts (0 to 10)
    - Verify violation logged only when count > 1
    - Use fast-check library with 100 iterations
    - Tag: `Feature: interview-enhancements, Property 7: Face Count Detection`
  
  - [~] 12.3 Write property test for violation deduplication
    - **Property 8: Violation Deduplication**
    - **Validates: Requirements 6.6**
    - Generate random time intervals (0 to 20000ms)
    - Verify second violation logged only if >10 seconds apart
    - Use fast-check library with 100 iterations
    - Tag: `Feature: interview-enhancements, Property 8: Violation Deduplication`
  
  - [~] 12.4 Write unit tests for proctoring hook extension
    - Test: Frame captured at 320x240 resolution
    - Test: Frame posted every 2 seconds by default
    - Test: Phone detection triggers onViolation callback
    - Test: Multiple person detection triggers onViolation callback
    - Test: Deduplication prevents logging within 10 seconds
    - Test: Adaptive rate reduces to 5s when slow
    - Test: Adaptive rate restores to 2s when fast
    - _Requirements: 5.1, 5.2, 6.3, 6.6, 12.4, 12.5, 12.6_

- [~] 13. Frontend Interview Page Integration
  - [~] 13.1 Update frontend/src/pages/HumanLikeInterview.jsx
    - Add INTERVIEW_STATES constant (LOADING, THINKING, RECORDING, PROCESSING, COMPLETE)
    - Add interviewState, recordingSeconds, activeViolation state variables
    - Add recordingManagerRef and recordingCounterRef refs
    - Implement `getTimerDuration(difficulty)` function
    - Implement `handleThinkingComplete()` function
    - Implement `handleRecordingComplete(audioBlob, responseTimeSec)` function
    - Integrate TimerComponent with conditional rendering
    - Integrate RecordingManager with ref
    - Integrate ViolationAlert component
    - Pass onViolation callback to useAdvancedProctoring hook
    - Update state machine transitions (THINKING → RECORDING → PROCESSING → THINKING/COMPLETE)
    - Add state indicator pill to top bar
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 3.2, 3.3, 3.4, 4.5, 8.1, 8.2, 10.1, 10.2, 10.3, 10.4, 10.5_
  
  - [~] 13.2 Write integration tests for interview page
    - Test: Question loads → thinking timer starts
    - Test: Timer reaches 0 → recording starts automatically
    - Test: Early start button → recording starts immediately
    - Test: Stop button → recording stops and submits
    - Test: Max 180s → auto-stops with toast
    - Test: Phone violation → alert displays
    - Test: Multiple person violation → alert displays
    - Test: State transitions work correctly
    - _Requirements: 1.6, 2.1, 2.6, 2.7, 3.2, 8.1, 8.2_

- [~] 14. Final Integration and Testing
  - [~] 14.1 End-to-end manual testing
    - Test full interview flow with timer and recording
    - Test phone detection with real phone in frame
    - Test multiple person detection with two people
    - Test violation alerts display and dismiss correctly
    - Test adaptive frame rate under load
    - Test database records violations correctly
    - Test error handling (mic denied, network failure)
    - _Ensure all tests pass, ask the user if questions arise._
  
  - [~] 14.2 Write property test for frame processing performance
    - **Property 12: Frame Processing Performance**
    - **Validates: Requirements 12.1, 12.2**
    - Generate random frame data (1KB to 50KB)
    - Verify processing completes in <500ms or returns empty
    - Use hypothesis library with 100 iterations
    - Tag: `Feature: interview-enhancements, Property 12: Frame Processing Performance`
  
  - [~] 14.3 Write property test for violation persistence
    - **Property 9: Violation Persistence**
    - **Validates: Requirements 7.1, 7.3**
    - Generate random violations
    - Verify database record created with correct session_id
    - Use hypothesis library with 100 iterations
    - Tag: `Feature: interview-enhancements, Property 9: Violation Persistence`
  
  - [~] 14.4 Write property test for database write latency
    - **Property 10: Database Write Latency**
    - **Validates: Requirements 7.4**
    - Generate random violations
    - Measure time from detection to database write
    - Verify <1 second under normal conditions
    - Use hypothesis library with 100 iterations
    - Tag: `Feature: interview-enhancements, Property 10: Database Write Latency`

## Notes

- All tasks are required for comprehensive implementation
- Backend tasks (1-7) should be completed before frontend tasks (8-14)
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties with 100 iterations
- Unit tests validate specific examples and edge cases
- Integration tests verify end-to-end flows
