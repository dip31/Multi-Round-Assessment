"""
Enhanced Proctoring Event Model for Advanced AI-Based Proctoring System.

Supports computer vision, audio analysis, and advanced violation detection.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, JSON
from sqlalchemy.orm import relationship

from app.database.base import Base


class AdvancedProctoringEvent(Base):
    """Advanced proctoring events with AI-based detection capabilities.
    
    Extends basic proctoring with computer vision, audio analysis,
    and confidence scoring for violation detection.
    """

    __tablename__ = "advanced_proctoring_events"

    id: int = Column(Integer, primary_key=True, index=True)
    session_id: int = Column(
        Integer,
        ForeignKey("assessment_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: str = Column(String(50), nullable=False, index=True)
    confidence: Optional[float] = Column(Float, nullable=True)  # AI model confidence (0.0-1.0)
    event_metadata: Optional[dict] = Column(JSON, nullable=True)  # Detailed detection data
    created_at: datetime = Column(DateTime, default=datetime.utcnow, index=True)

    # ── Relationships ─────────────────────────────────────────────────
    session = relationship("AssessmentSession", back_populates="advanced_proctoring_events")

    def __repr__(self) -> str:
        return (
            f"<AdvancedProctoringEvent id={self.id} session_id={self.session_id} "
            f"type={self.event_type} confidence={self.confidence}>"
        )


# Event types for advanced proctoring system
ADVANCED_PROCTORING_EVENTS = {
    # Browser-based events (from basic system)
    "TAB_SWITCH": "tab_switch",
    "FULLSCREEN_EXIT": "fullscreen_exit", 
    "PAGE_RELOAD": "page_reload",
    "IDLE_ACTIVITY": "idle_activity",
    "COPY_PASTE": "copy_paste",
    "NETWORK_DISCONNECT": "network_disconnect",
    "NETWORK_RECONNECT": "network_reconnect",
    
    # Computer vision events
    "MULTIPLE_PERSON_DETECTED": "multiple_person_detected",
    "FACE_NOT_VISIBLE": "face_not_visible",
    "MOUTH_MOVEMENT_DETECTED": "mouth_movement_detected",
    "LOOKING_AWAY": "looking_away",
    "HEAD_TURN_DETECTED": "head_turn_detected",
    
    # Audio events
    "VOICE_ACTIVITY_DETECTED": "voice_activity_detected",
    
    # System events
    "CAMERA_PERMISSION_DENIED": "camera_permission_denied",
    "MICROPHONE_PERMISSION_DENIED": "microphone_permission_denied",
    "DEVICE_CHANGE": "device_change",
    "PROCTORING_INITIALIZED": "proctoring_initialized",
    "PROCTORING_ERROR": "proctoring_error",
}

# Risk scoring for different violation types
VIOLATION_RISK_SCORES = {
    "TAB_SWITCH": 0.3,
    "FULLSCREEN_EXIT": 0.4,
    "PAGE_RELOAD": 0.8,
    "IDLE_ACTIVITY": 0.2,
    "COPY_PASTE": 0.6,
    "NETWORK_DISCONNECT": 0.7,
    "NETWORK_RECONNECT": 0.2,
    "MULTIPLE_PERSON_DETECTED": 0.9,
    "FACE_NOT_VISIBLE": 0.7,
    "MOUTH_MOVEMENT_DETECTED": 0.5,
    "LOOKING_AWAY": 0.3,
    "HEAD_TURN_DETECTED": 0.4,
    "VOICE_ACTIVITY_DETECTED": 0.6,
    "CAMERA_PERMISSION_DENIED": 0.8,
    "MICROPHONE_PERMISSION_DENIED": 0.6,
    "DEVICE_CHANGE": 0.7,
}
