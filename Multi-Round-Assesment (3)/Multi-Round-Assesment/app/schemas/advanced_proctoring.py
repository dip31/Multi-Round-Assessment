"""
Advanced Proctoring Schemas for Enhanced AI-Based Proctoring System.

Pydantic models for request/response validation with confidence scoring
and detailed metadata for computer vision and audio analysis.
"""

from datetime import datetime
from typing import Optional, Dict, Any

from pydantic import BaseModel, Field


class AdvancedProctorEventRequest(BaseModel):
    """Request schema for logging advanced proctoring events."""
    
    session_id: int = Field(..., description="Assessment session ID")
    event_type: str = Field(..., description="Type of proctoring event")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="AI model confidence score")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Detailed detection metadata")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "session_id": 101,
                "event_type": "MULTIPLE_PERSON_DETECTED",
                "confidence": 0.92,
                "metadata": {
                    "face_count": 2,
                    "detection_boxes": [[100, 100, 200, 200], [300, 100, 400, 200]],
                    "timestamp": 1640995200000
                }
            }
        }
    }


class AdvancedProctorEventResponse(BaseModel):
    """Response schema for successful event logging."""
    
    success: bool = Field(True, description="Event logged successfully")
    event_id: int = Field(..., description="Database ID of logged event")
    risk_score: float = Field(..., description="Calculated risk score for this event")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "success": True,
                "event_id": 12345,
                "risk_score": 0.9
            }
        }
    }


class ProctoringSessionSummary(BaseModel):
    """Summary of proctoring events for a session."""
    
    session_id: int
    total_events: int
    violation_counts: Dict[str, int]
    risk_score: float
    events: list[Dict[str, Any]]
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "session_id": 101,
                "total_events": 15,
                "violation_counts": {
                    "TAB_SWITCH": 3,
                    "MULTIPLE_PERSON_DETECTED": 1,
                    "VOICE_ACTIVITY_DETECTED": 2
                },
                "risk_score": 0.75,
                "events": [
                    {
                        "id": 1,
                        "event_type": "TAB_SWITCH",
                        "confidence": 1.0,
                        "created_at": "2024-01-01T10:00:00Z"
                    }
                ]
            }
        }
    }


class ProctoringViolationThreshold(BaseModel):
    """Configuration for violation detection thresholds."""
    
    event_type: str
    max_allowed: int
    risk_weight: float
    auto_fail_threshold: Optional[int] = None
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "event_type": "MULTIPLE_PERSON_DETECTED",
                "max_allowed": 0,
                "risk_weight": 0.9,
                "auto_fail_threshold": 1
            }
        }
    }
