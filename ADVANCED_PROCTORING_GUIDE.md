# Advanced AI-Based Online Proctoring System

## 🎯 Overview

This advanced proctoring system extends the basic monitoring capabilities with **AI-powered computer vision**, **audio analysis**, and **real-time violation detection** using MediaPipe and modern web technologies.

## 🏗️ System Architecture

```
Candidate Browser
      ↓
┌─────────────────────────────────────┐
│        Monitoring Modules           │
│  ├ Browser Behavior Monitoring     │
│  ├ Webcam Video Monitoring         │
│  ├ Microphone Audio Monitoring     │
└─────────────────────────────────────┘
      ↓
┌─────────────────────────────────────┐
│      Behavior Detection Engine     │
│  ├ MediaPipe Face Detection        │
│  ├ MediaPipe Face Mesh Analysis    │
│  ├ Voice Activity Detection        │
│  ├ Risk Assessment Algorithm       │
└─────────────────────────────────────┘
      ↓
┌─────────────────────────────────────┐
│        Violation Detection          │
│  ├ Multiple Person Detection       │
│  ├ Face Visibility Analysis        │
│  ├ Mouth Movement Detection        │
│  ├ Eye Gaze Tracking              │
│  ├ Head Pose Estimation           │
│  ├ Voice Activity Monitoring       │
└─────────────────────────────────────┘
      ↓
┌─────────────────────────────────────┐
│      Backend Logging API           │
│  ├ FastAPI Advanced Proctoring    │
│  ├ Confidence Scoring             │
│  ├ Risk Assessment               │
│  ├ Violation Thresholds          │
└─────────────────────────────────────┘
      ↓
┌─────────────────────────────────────┐
│     Proctoring Event Database      │
│  ├ Advanced Events Table          │
│  ├ JSONB Metadata Storage         │
│  ├ Risk Score Calculations        │
│  ├ High-Risk Session Views        │
└─────────────────────────────────────┘
      ↓
┌─────────────────────────────────────┐
│        Admin Dashboard             │
│  ├ Real-time Monitoring           │
│  ├ Risk Assessment Analytics      │
│  ├ Violation Timeline             │
│  ├ Session Review Tools           │
└─────────────────────────────────────┘
```

## 🚀 Key Features

### Computer Vision Monitoring
- **Multiple Person Detection**: Detects if more than one person is in camera view
- **Face Visibility Analysis**: Tracks facial landmark presence and visibility
- **Mouth Movement Detection**: Identifies suspicious speaking patterns
- **Eye Gaze Tracking**: Monitors if candidate is looking away from screen
- **Head Pose Estimation**: Detects excessive head turning

### Audio Monitoring
- **Voice Activity Detection**: Identifies speaking during assessment
- **Amplitude Analysis**: Measures voice levels and duration
- **Silence Detection**: Tracks periods of no audio activity

### Browser Behavior Monitoring
- **Tab Switch Detection**: Monitors browser tab changes
- **Fullscreen Enforcement**: Ensures test remains in fullscreen mode
- **Page Reload Protection**: Detects and prevents page refresh attempts
- **Idle Activity Monitoring**: Tracks user inactivity periods

### Risk Assessment System
- **Confidence Scoring**: AI model confidence for each detection
- **Risk Weighting**: Different violation types have different risk weights
- **Threshold Management**: Configurable violation limits per event type
- **Real-time Risk Calculation**: Dynamic risk score updates

## 📋 Event Types and Risk Scores

| Event Type | Risk Score | Description | Max Allowed |
|------------|------------|-------------|-------------|
| MULTIPLE_PERSON_DETECTED | 0.9 | Multiple faces detected in camera | 0 |
| FACE_NOT_VISIBLE | 0.7 | Candidate's face not visible | 5 |
| PAGE_RELOAD | 0.8 | Page reload attempt | 1 |
| CAMERA_PERMISSION_DENIED | 0.8 | Camera access denied | 0 |
| VOICE_ACTIVITY_DETECTED | 0.6 | Speaking detected during test | 5 |
| HEAD_TURN_DETECTED | 0.4 | Excessive head turning | 10 |
| MOUTH_MOVEMENT_DETECTED | 0.5 | Suspicious mouth movement | 8 |
| FULLSCREEN_EXIT | 0.4 | Exited fullscreen mode | 3 |
| LOOKING_AWAY | 0.3 | Looking away from screen | 15 |
| TAB_SWITCH | 0.3 | Browser tab switch | 5 |
| IDLE_ACTIVITY | 0.2 | Inactivity for extended period | 10 |

## 🛠️ Installation Guide

### Prerequisites

#### Backend Dependencies
```bash
# Python packages (add to requirements.txt)
fastapi>=0.104.0
uvicorn>=0.24.0
sqlalchemy>=2.0.0
alembic>=1.12.0
psycopg2-binary>=2.9.0
pydantic>=2.4.0
python-jose>=3.3.0
passlib>=1.7.0
python-multipart>=0.0.6
```

#### Frontend Dependencies
```bash
# npm packages (add to package.json)
npm install @mediapipe/camera_utils
npm install @mediapipe/face_detection
npm install @mediapipe/face_mesh
npm install @mediapipe/drawing_utils
npm install lucide-react
```

### Database Setup

1. **Create the advanced proctoring table:**
```bash
psql -d ai_placement_platform -f database/advanced_proctoring_schema.sql
```

2. **Run Alembic migration:**
```bash
cd /path/to/project
alembic upgrade head
```

### Backend Setup

1. **Update models in `app/models/__init__.py`:**
```python
from app.models.advanced_proctoring import AdvancedProctoringEvent
```

2. **Add relationship to AssessmentSession:**
```python
# In app/models/assessment.py
advanced_proctoring_events = relationship(
    "AdvancedProctoringEvent",
    back_populates="session",
    cascade="all, delete-orphan",
    lazy="select",
)
```

3. **Restart backend server:**
```bash
uvicorn app.main:app --reload
```

### Frontend Setup

1. **Install MediaPipe dependencies:**
```bash
cd frontend
npm install @mediapipe/camera_utils @mediapipe/face_detection @mediapipe/face_mesh @mediapipe/drawing_utils
```

2. **Add proctoring components to your test page:**
```jsx
import { useAdvancedProctoring } from '../hooks/useAdvancedProctoring';
import AdvancedProctoringMonitor from '../components/AdvancedProctoringMonitor';
import ProctoringVideoDisplay from '../components/ProctoringVideoDisplay';
```

3. **Initialize advanced proctoring:**
```jsx
const advancedProctoring = useAdvancedProctoring(sessionId, handleViolation);
```

## 🔧 Configuration

### Backend Configuration

Add to your `.env` file:
```bash
# Advanced Proctoring Settings
ADVANCED_PROCTORING_ENABLED=true
PROCTORING_RISK_THRESHOLD=0.7
MAX_VIOLATION_SESSIONS=50
PROCTORING_DATA_RETENTION_DAYS=90
```

### Frontend Configuration

In your proctoring hook configuration:
```javascript
const PROCTORING_CONFIG = {
  CAMERA_FPS: 30,
  PROCESSING_FPS: 5,
  VIDEO_WIDTH: 640,
  VIDEO_HEIGHT: 480,
  FACE_DETECTION_CONFIDENCE: 0.5,
  MOUTH_MOVEMENT_THRESHOLD: 0.02,
  GAZE_DEVIATION_THRESHOLD: 0.3,
  HEAD_TURN_THRESHOLD: 35,
  VOICE_ACTIVITY_THRESHOLD: 0.5,
};
```

## 🎮 Usage Guide

### For Candidates

1. **Grant Permissions**: Allow camera and microphone access when prompted
2. **Position Camera**: Ensure your face is clearly visible in the camera frame
3. **Stay in Frame**: Maintain face visibility throughout the assessment
4. **No Speaking**: Avoid speaking during the test
5. **Focus**: Keep your eyes on the screen and avoid excessive head movement

### For Administrators

1. **Monitor Dashboard**: Access the admin dashboard to view real-time proctoring data
2. **Review Violations**: Check detailed violation logs and risk scores
3. **Set Thresholds**: Configure violation thresholds based on requirements
4. **Export Reports**: Generate compliance reports for audit purposes

## 📊 API Endpoints

### Advanced Proctoring Events

#### Log Event
```http
POST /api/v1/advanced-proctoring/log-event
Content-Type: application/json

{
  "session_id": 101,
  "event_type": "MULTIPLE_PERSON_DETECTED",
  "confidence": 0.92,
  "metadata": {
    "face_count": 2,
    "detection_boxes": [[100, 100, 200, 200], [300, 100, 400, 200]]
  }
}
```

#### Get Session Summary
```http
GET /api/v1/advanced-proctoring/session/{session_id}/summary
```

#### Get High-Risk Sessions
```http
GET /api/v1/advanced-proctoring/high-risk-sessions?risk_threshold=0.7&limit=50
```

#### Check Violation Thresholds
```http
GET /api/v1/advanced-proctoring/session/{session_id}/violations
```

## 🔍 Monitoring and Analytics

### Real-time Monitoring

The system provides real-time monitoring through:
- **Live Video Feed**: Privacy-focused video monitoring with face detection overlays
- **Violation Alerts**: Immediate notifications for critical violations
- **Risk Score Tracking**: Dynamic risk assessment based on all events
- **Session Timeline**: Complete event history with timestamps

### Admin Dashboard Features

- **High-Risk Session List**: Sessions exceeding risk thresholds
- **Violation Breakdown**: Detailed analysis of violation types and frequencies
- **Risk Assessment**: Overall risk scoring and trend analysis
- **Export Capabilities**: CSV export for compliance and audit purposes

## 🔒 Privacy and Security

### Data Protection
- **No Raw Video Storage**: Video and audio streams are processed in-browser only
- **Metadata Only**: Only violation metadata is stored in the database
- **Consent Required**: Explicit user consent for camera and microphone access
- **Data Retention**: Configurable data retention policies

### Security Measures
- **Encrypted Transmission**: All API communications use HTTPS
- **Session Isolation**: Users can only access their own session data
- **Access Control**: Role-based access for admin dashboard
- **Audit Trail**: Complete audit log of all proctoring events

## 🚨 Performance Optimization

### Frame Processing
- **Sampling Strategy**: Process every 6th frame (5 FPS from 30 FPS)
- **Memory Management**: Efficient garbage collection for MediaPipe objects
- **Async Processing**: Non-blocking API calls for event logging

### Browser Optimization
- **Web Workers**: Heavy processing moved to background threads
- **Lazy Loading**: Components loaded on-demand
- **Resource Caching**: Efficient caching of MediaPipe models

## 🐛 Troubleshooting

### Common Issues

#### Camera Permission Denied
```javascript
// Solution: Handle permission gracefully
if (error.name === 'NotAllowedError') {
  logProctoringEvent('CAMERA_PERMISSION_DENIED', {
    timestamp: Date.now(),
    error: error.name
  });
}
```

#### MediaPipe Loading Issues
```javascript
// Solution: Ensure CDN is accessible
const faceDetection = new FaceDetection({
  locateFile: (file) => {
    return `https://cdn.jsdelivr.net/npm/@mediapipe/face_detection/${file}`;
  },
});
```

#### High CPU Usage
```javascript
// Solution: Reduce processing frequency
const PROCESSING_FPS = 3; // Reduce from 5 to 3
```

### Debug Mode

Enable debug logging:
```javascript
const DEBUG_MODE = true;
if (DEBUG_MODE) {
  console.log('Proctoring Event:', eventType, metadata);
}
```

## 📈 Monitoring Metrics

### Key Performance Indicators
- **Detection Accuracy**: Face detection confidence scores
- **False Positive Rate**: Incorrect violation detection rate
- **System Latency**: Time from detection to logging
- **Resource Usage**: CPU and memory consumption

### Analytics Dashboard
- **Violation Trends**: Time-based analysis of violation patterns
- **Risk Distribution**: Histogram of risk scores across sessions
- **Geographic Analysis**: Location-based compliance monitoring
- **Device Compatibility**: Browser and device performance metrics

## 🔄 Future Enhancements

### Planned Features
- **Advanced Face Recognition**: Candidate identity verification
- **Object Detection**: Detect unauthorized materials (phones, notes)
- **Behavioral Analysis**: AI-powered cheating pattern recognition
- **Multi-Language Support**: Support for assessments in different languages

### Integration Opportunities
- **Learning Management Systems**: Seamless LMS integration
- **Video Conferencing**: Integration with Zoom, Teams, etc.
- **Identity Verification**: Integration with ID verification services
- **Analytics Platforms**: Integration with Tableau, Power BI

## 📞 Support

For technical support and questions:
- **Documentation**: Check inline code comments and API docs
- **Issues**: Report bugs and feature requests on GitHub
- **Community**: Join our developer community for best practices

---

**Built with ❤️ using MediaPipe, FastAPI, and Modern Web Technologies**
