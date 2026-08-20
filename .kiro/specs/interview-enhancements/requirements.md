# Requirements Document: Interview System Enhancements

## Introduction

This document specifies requirements for enhancing the existing interview system with two major features: timed answer recording with automatic recording triggers, and advanced proctoring capabilities for detecting mobile phones and multiple people in video frames. These enhancements improve interview workflow automation and strengthen assessment integrity.

## Glossary

- **Interview_System**: The existing FastAPI backend and React frontend application that conducts real-time audio/video interviews
- **Timer_Component**: UI component that displays countdown and manages timing state
- **Recording_Manager**: Component responsible for controlling audio recording state
- **Proctoring_Service**: Backend service that processes video frames and logs violations
- **Detection_Model**: Computer vision model that identifies objects and people in video frames
- **Violation_Log**: Database record of proctoring policy violations
- **Interview_Session**: A single interview instance with associated state and turns
- **Question_Turn**: A single question-answer cycle within an interview session
- **Thinking_Timer**: 2-minute countdown period before recording starts
- **Recording_State**: Current status of audio recording (idle, recording, stopped)

## Requirements

### Requirement 1: Thinking Timer Display

**User Story:** As a candidate, I want to see a countdown timer after a question is asked, so that I know how much thinking time remains before recording starts.

#### Acceptance Criteria

1. THE Timer_Component SHALL accept duration as a configurable parameter based on question difficulty
2. WHEN a question with difficulty "EASY" is presented, THE Timer_Component SHALL display a 60 second countdown
3. WHEN a question with difficulty "MEDIUM" is presented, THE Timer_Component SHALL display a 90 second countdown
4. WHEN a question with difficulty "HARD" is presented, THE Timer_Component SHALL display a 120 second countdown
5. WHEN the countdown is active, THE Timer_Component SHALL update the display every second
6. WHEN the countdown reaches zero, THE Timer_Component SHALL trigger a state change event
7. THE Timer_Component SHALL display time in MM:SS format
8. WHEN the timer is running, THE Timer_Component SHALL show a "Thinking Time" label

### Requirement 2: Automatic Recording Trigger

**User Story:** As a candidate, I want recording to start automatically when the thinking timer expires, so that I can focus on my answer without manual intervention.

#### Acceptance Criteria

1. WHEN the thinking timer reaches zero, THE Recording_Manager SHALL automatically start audio recording
2. WHEN recording starts automatically, THE Recording_Manager SHALL update the UI to show recording status
3. WHEN recording is active, THE Recording_Manager SHALL capture audio input from the candidate's microphone
4. THE Recording_Manager SHALL request microphone permissions before starting recording
5. IF microphone permissions are denied, THEN THE Recording_Manager SHALL display an error message and log a proctoring event
6. THE Recording_Manager SHALL automatically stop recording after a maximum of 180 seconds if the candidate does not manually stop
7. WHEN maximum recording time is reached, THE Recording_Manager SHALL submit the audio as-is and display a warning message

### Requirement 3: Manual Recording Control

**User Story:** As a candidate, I want to manually stop recording when I finish my answer, so that I can control when my response is submitted.

#### Acceptance Criteria

1. WHEN recording is active, THE Recording_Manager SHALL display a "Stop Recording" button
2. WHEN the candidate clicks "Stop Recording", THE Recording_Manager SHALL stop audio capture
3. WHEN recording stops, THE Recording_Manager SHALL process the captured audio for transcription
4. WHEN recording stops, THE Recording_Manager SHALL submit the response to the backend
5. THE Recording_Manager SHALL disable the stop button while processing the response

### Requirement 4: Recording Status Indicators

**User Story:** As a candidate, I want clear visual feedback about recording status, so that I know whether the system is capturing my answer.

#### Acceptance Criteria

1. WHEN recording is active, THE Timer_Component SHALL display a recording indicator icon
2. WHEN recording is active, THE Timer_Component SHALL show elapsed recording time
3. WHEN the thinking timer is active, THE Timer_Component SHALL show a different visual style than recording time
4. THE Timer_Component SHALL use distinct colors for thinking time (blue) and recording time (red)
5. WHEN recording stops, THE Timer_Component SHALL display a processing indicator

### Requirement 5: Mobile Phone Detection

**User Story:** As a proctor, I want the system to detect mobile phones in the video frame, so that I can identify potential cheating attempts.

#### Acceptance Criteria

1. THE frontend SHALL capture frames from webcam canvas at 320x240 resolution with 70% JPEG quality
2. THE frontend SHALL POST captured frames to /advanced-proctoring/analyze-frame every 2 seconds
3. WHEN a video frame is analyzed, THE Detection_Model SHALL identify mobile phone objects using YOLOv8n
4. WHEN a mobile phone is detected with confidence above 0.6, THE Proctoring_Service SHALL log a violation event
5. WHEN a mobile phone violation is logged, THE Proctoring_Service SHALL include confidence score and timestamp
6. WHEN multiple mobile phones are detected in a single frame, THE Proctoring_Service SHALL log each detection separately

### Requirement 6: Multiple Person Detection

**User Story:** As a proctor, I want the system to detect multiple people in the video frame, so that I can identify unauthorized assistance during interviews.

#### Acceptance Criteria

1. THE Interview_System SHALL extend the existing useAdvancedProctoring hook for multiple person detection
2. WHEN a video frame is analyzed, THE Detection_Model SHALL count the number of distinct faces using existing MediaPipe face detection
3. WHEN more than one face is detected, THE Proctoring_Service SHALL log a multiple person violation
4. WHEN a multiple person violation is logged, THE Proctoring_Service SHALL include the face count and timestamp
5. THE Detection_Model SHALL use a confidence threshold of 0.7 for face detection
6. WHEN the same violation persists across consecutive frames, THE Proctoring_Service SHALL log only one event per 10-second window

### Requirement 7: Violation Logging and Storage

**User Story:** As a system administrator, I want all proctoring violations stored in the database, so that I can review candidate behavior after interviews complete.

#### Acceptance Criteria

1. WHEN a proctoring violation is detected, THE Proctoring_Service SHALL create a Violation_Log record
2. THE Violation_Log SHALL include session_id, event_type, confidence_score, timestamp, and metadata
3. WHEN storing violations, THE Proctoring_Service SHALL associate them with the active Interview_Session
4. THE Proctoring_Service SHALL persist violations to the database within 1 second of detection
5. WHEN database writes fail, THE Proctoring_Service SHALL retry with delays of 0 seconds, 1 second, and 2 seconds
6. IF all 3 retry attempts fail, THE Proctoring_Service SHALL store the violation in an in-memory queue
7. THE Proctoring_Service SHALL retry queued violations on the next successful database connection
8. THE in-memory queue SHALL have a maximum size of 50 violations
9. WHEN the queue exceeds 50 violations, THE Proctoring_Service SHALL drop the oldest entries

### Requirement 8: Real-time Violation Alerts

**User Story:** As a candidate, I want to see warnings when violations are detected, so that I can correct my behavior during the interview.

#### Acceptance Criteria

1. WHEN a mobile phone is detected, THE Interview_System SHALL display a warning message in the top-right corner
2. WHEN multiple people are detected, THE Interview_System SHALL display a warning message in the top-right corner
3. THE warning message SHALL use bg-red-900/90 background with border-red-500 border and text-red-100 text color
4. THE warning message SHALL display "⚠ Mobile phone detected" for phone violations
5. THE warning message SHALL display "⚠ Multiple people detected" for multiple person violations
6. THE warning message SHALL slide in from top-right using CSS animation
7. THE warning message SHALL auto-dismiss after 5 seconds
8. THE warning message SHALL NOT pause the timer or recording
9. THE warning message SHALL NOT require candidate acknowledgment
10. WHEN a new violation occurs during an active warning, THE Interview_System SHALL replace the current warning
11. THE warning message SHALL have z-index above video but below modal dialogs
12. THE warning message SHALL have max-w-xs width to fit in corner without blocking the question

### Requirement 9: Detection Model Integration

**User Story:** As a developer, I want to integrate a computer vision model for object and face detection, so that the system can identify violations automatically.

#### Acceptance Criteria

1. THE Detection_Model SHALL use YOLOv8n for mobile phone object detection
2. THE Detection_Model SHALL use OpenCV Haar cascades for face counting
3. THE Detection_Model SHALL use haarcascade_frontalface_default.xml for face detection
4. WHEN the Interview_System starts, THE Detection_Model SHALL load YOLOv8n model weights into memory
5. THE Detection_Model SHALL process video frames without blocking the main application thread
6. WHEN model inference fails, THE Detection_Model SHALL log the error and continue processing subsequent frames
7. THE Detection_Model SHALL detect "cell phone" class (COCO dataset class 67) for mobile phone violations

### Requirement 10: Timer State Management

**User Story:** As a developer, I want proper state management for timer and recording states, so that the UI remains synchronized with backend state.

#### Acceptance Criteria

1. THE Interview_System SHALL maintain timer state in React component state
2. WHEN a question is loaded, THE Interview_System SHALL initialize the thinking timer to 120 seconds
3. WHEN recording starts, THE Interview_System SHALL reset the recording timer to 0
4. THE Interview_System SHALL persist recording state across component re-renders
5. WHEN the user navigates away during recording, THE Interview_System SHALL stop recording and discard the audio

### Requirement 11: Backend API for Proctoring Events

**User Story:** As a frontend developer, I want API endpoints for logging proctoring events, so that I can send violation data to the backend.

#### Acceptance Criteria

1. THE Proctoring_Service SHALL expose a POST /advanced-proctoring/log-event endpoint
2. WHEN the endpoint receives a valid event, THE Proctoring_Service SHALL return a 200 status code
3. THE endpoint SHALL validate that session_id belongs to the authenticated user
4. THE endpoint SHALL accept event_type, confidence_score, and metadata fields
5. IF validation fails, THEN THE endpoint SHALL return a 400 status code with error details

### Requirement 12: Frame Processing Performance

**User Story:** As a system architect, I want frame processing to be efficient, so that detection does not impact interview performance.

#### Acceptance Criteria

1. THE Detection_Model SHALL process each frame in less than 500 milliseconds
2. WHEN frame processing exceeds 500ms, THE Detection_Model SHALL skip the frame and log a warning
3. THE Detection_Model SHALL use GPU acceleration when available
4. THE Interview_System SHALL limit frame analysis to 1 frame per 2 seconds by default
5. WHEN frame processing time exceeds 400ms for a single frame, THE Interview_System SHALL reduce frame analysis rate to 1 frame per 5 seconds
6. WHEN frame processing time returns below 200ms for 3 consecutive frames, THE Interview_System SHALL restore frame analysis rate to 1 frame per 2 seconds
7. THE Interview_System SHALL measure frame processing time using performance.now() for adaptive rate adjustment
