# Requirements Document: Interview Enhancement

## Introduction

This document specifies requirements for enhancing the existing interview system with two key capabilities: (1) a timed answer recording flow that gives candidates thinking time before automatically starting audio recording, and (2) interview proctoring that detects mobile phones and multiple people in the video frame. These enhancements integrate with the existing Python FastAPI backend and React frontend interview infrastructure.

## Glossary

- **Interview_System**: The existing interview module at app/modules/interview/ that manages interview sessions, questions, and responses
- **Proctoring_System**: The existing proctoring infrastructure in app/modules/proctoring/ and app/modules/advanced_proctoring/ that logs and tracks violations
- **Candidate**: The user being interviewed who answers questions
- **Interviewer**: The system that asks questions and evaluates responses
- **Thinking_Period**: The 2-minute countdown period after a question is asked, before recording begins
- **Recording_Session**: The audio capture period when the candidate is speaking their answer
- **Video_Frame**: A single frame from the candidate's webcam feed used for computer vision analysis
- **Mobile_Phone**: A handheld device (smartphone or tablet) detected in the video frame
- **Multi_Person_Detection**: Computer vision detection of more than one human face in the video frame
- **Proctoring_Event**: A logged violation or suspicious behavior during the interview
- **Computer_Vision_Service**: The service that analyzes video frames for object and face detection
- **Audio_Recording_Service**: The service that captures and processes candidate audio responses

## Requirements

### Requirement 1: Timed Thinking Period

**User Story:** As a candidate, I want a 2-minute thinking period after each question is asked, so that I can organize my thoughts before speaking.

#### Acceptance Criteria

1. WHEN a question is presented to the candidate, THE Interview_System SHALL start a 2-minute countdown timer
2. WHEN the countdown timer is active, THE Interview_System SHALL display the remaining time to the candidate
3. WHEN the countdown timer reaches zero, THE Interview_System SHALL automatically trigger the recording start
4. WHEN the thinking period is active, THE Interview_System SHALL prevent the candidate from manually starting the recording early
5. WHEN the thinking period completes, THE Interview_System SHALL provide visual feedback that recording has begun

### Requirement 2: Automatic Recording Trigger

**User Story:** As a candidate, I want the recording to start automatically after my thinking time, so that I don't have to manually click a button.

#### Acceptance Criteria

1. WHEN the 2-minute thinking period expires, THE Interview_System SHALL automatically begin audio recording
2. WHEN automatic recording begins, THE Audio_Recording_Service SHALL capture audio from the candidate's microphone
3. WHEN recording starts automatically, THE Interview_System SHALL update the UI to show recording status
4. WHEN automatic recording is triggered, THE Interview_System SHALL log the timestamp of recording start
5. WHEN the recording is active, THE Interview_System SHALL display a visual indicator that recording is in progress

### Requirement 3: Manual Recording Stop

**User Story:** As a candidate, I want to manually stop the recording when I finish my answer, so that I control when my response ends.

#### Acceptance Criteria

1. WHEN the candidate clicks the stop recording button, THE Interview_System SHALL immediately stop audio capture
2. WHEN recording is stopped, THE Audio_Recording_Service SHALL finalize and save the audio data
3. WHEN recording stops, THE Interview_System SHALL submit the recorded audio for transcription
4. WHEN the stop button is clicked, THE Interview_System SHALL disable the stop button to prevent duplicate submissions
5. WHEN recording is stopped, THE Interview_System SHALL transition to processing the candidate's response

### Requirement 4: Mobile Phone Detection

**User Story:** As a proctoring administrator, I want to detect when a mobile phone appears in the video frame, so that I can identify potential cheating attempts.

#### Acceptance Criteria

1. WHEN a video frame is captured during the interview, THE Computer_Vision_Service SHALL analyze the frame for mobile phone objects
2. WHEN a mobile phone is detected in the video frame, THE Computer_Vision_Service SHALL return a confidence score for the detection
3. WHEN the confidence score exceeds 0.7, THE Proctoring_System SHALL log a proctoring event with type "MOBILE_PHONE_DETECTED"
4. WHEN a mobile phone detection event is logged, THE Proctoring_System SHALL include the confidence score in the event metadata
5. WHEN a mobile phone is detected, THE Proctoring_System SHALL include a timestamp and frame reference in the event log

### Requirement 5: Multiple Person Detection

**User Story:** As a proctoring administrator, I want to detect when more than one person appears in the video frame, so that I can identify unauthorized assistance.

#### Acceptance Criteria

1. WHEN a video frame is captured during the interview, THE Computer_Vision_Service SHALL count the number of human faces in the frame
2. WHEN more than one face is detected, THE Computer_Vision_Service SHALL return the face count and confidence scores
3. WHEN multiple faces are detected with confidence above 0.7, THE Proctoring_System SHALL log a proctoring event with type "MULTIPLE_PERSON_DETECTED"
4. WHEN a multiple person event is logged, THE Proctoring_System SHALL include the face count in the event metadata
5. WHEN multiple people are detected, THE Proctoring_System SHALL include bounding box coordinates for each detected face in the metadata

### Requirement 6: Proctoring Event Integration

**User Story:** As a system administrator, I want proctoring violations to integrate with the existing proctoring infrastructure, so that all violations are tracked consistently.

#### Acceptance Criteria

1. WHEN a mobile phone or multiple person violation is detected, THE Proctoring_System SHALL use the existing advanced proctoring event logging endpoint
2. WHEN a proctoring event is logged, THE Proctoring_System SHALL calculate a risk score based on violation type and confidence
3. WHEN events are logged, THE Proctoring_System SHALL associate them with the current interview session ID
4. WHEN violations occur, THE Proctoring_System SHALL increment violation counters for the session
5. WHEN the interview completes, THE Proctoring_System SHALL include violation counts in the interview report

### Requirement 7: Real-Time Video Frame Processing

**User Story:** As a system architect, I want video frames to be processed efficiently in real-time, so that detection does not impact interview performance.

#### Acceptance Criteria

1. WHEN video frames are captured, THE Computer_Vision_Service SHALL process frames at a maximum rate of 1 frame per 2 seconds
2. WHEN frame processing is in progress, THE Computer_Vision_Service SHALL skip additional frames until processing completes
3. WHEN processing fails, THE Computer_Vision_Service SHALL log the error and continue with the next frame
4. WHEN the interview is active, THE Computer_Vision_Service SHALL run detection asynchronously without blocking the UI
5. WHEN detection completes, THE Computer_Vision_Service SHALL return results within 500 milliseconds

### Requirement 8: Frontend Timer Display

**User Story:** As a candidate, I want to see a clear countdown timer during my thinking period, so that I know how much time remains.

#### Acceptance Criteria

1. WHEN the thinking period starts, THE Interview_System SHALL display a countdown timer in MM:SS format
2. WHEN the timer is counting down, THE Interview_System SHALL update the display every second
3. WHEN 30 seconds remain, THE Interview_System SHALL change the timer color to indicate urgency
4. WHEN 10 seconds remain, THE Interview_System SHALL display a warning message
5. WHEN the timer reaches zero, THE Interview_System SHALL hide the countdown and show recording status

### Requirement 9: Computer Vision Model Integration

**User Story:** As a developer, I want to use pre-trained computer vision models for detection, so that I don't need to train custom models.

#### Acceptance Criteria

1. WHEN the Computer_Vision_Service initializes, THE Computer_Vision_Service SHALL load a pre-trained object detection model for phone detection
2. WHEN the Computer_Vision_Service initializes, THE Computer_Vision_Service SHALL load a pre-trained face detection model for person counting
3. WHEN models are loaded, THE Computer_Vision_Service SHALL verify model availability and log initialization status
4. WHEN a model fails to load, THE Computer_Vision_Service SHALL raise an error and prevent interview start
5. WHEN detection is requested, THE Computer_Vision_Service SHALL use the loaded models for inference

### Requirement 10: Audio Recording State Management

**User Story:** As a developer, I want clear state management for the recording flow, so that the UI and backend stay synchronized.

#### Acceptance Criteria

1. THE Interview_System SHALL maintain recording state with values: "WAITING", "THINKING", "RECORDING", "PROCESSING"
2. WHEN a question is asked, THE Interview_System SHALL transition state from "WAITING" to "THINKING"
3. WHEN the thinking period expires, THE Interview_System SHALL transition state from "THINKING" to "RECORDING"
4. WHEN recording is stopped, THE Interview_System SHALL transition state from "RECORDING" to "PROCESSING"
5. WHEN response processing completes, THE Interview_System SHALL transition state back to "WAITING"
