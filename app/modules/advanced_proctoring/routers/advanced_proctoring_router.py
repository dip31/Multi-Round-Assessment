"""
Advanced Proctoring Router for AI-Based Online Proctoring System.

Handles computer vision events, audio analysis, and comprehensive violation detection
with confidence scoring and risk assessment.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database.db import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.services.session_service import get_active_session
from app.schemas.advanced_proctoring import (
    AdvancedProctorEventRequest,
    AdvancedProctorEventResponse,
    ProctoringSessionSummary
)
from app.services.advanced_proctoring_service import advanced_proctoring_service

router = APIRouter(
    prefix="/advanced-proctoring",
    tags=["Advanced Proctoring"],
)


def _require_active_session(db: Session, user_id: int):
    """Return the user's active assessment session or raise 404."""
    active_session = get_active_session(db, user_id)
    if active_session is None:
        raise HTTPException(
            status_code=404,
            detail="No active assessment session found",
        )
    return active_session


@router.post("/log-event", response_model=AdvancedProctorEventResponse)
def log_advanced_proctoring_event(
    event_data: AdvancedProctorEventRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Log an advanced proctoring event with AI-based detection.
    
    Supports computer vision events, audio analysis, and confidence scoring.
    """
    # Verify session ownership
    active_session = _require_active_session(db, current_user.id)
    if event_data.session_id != active_session.id:
        raise HTTPException(
            status_code=403,
            detail="Cannot log events for other users' sessions"
        )
    
    try:
        event, risk_score = advanced_proctoring_service.log_advanced_event(db, event_data)
        
        return AdvancedProctorEventResponse(
            success=True,
            event_id=event.id,
            risk_score=risk_score
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to log proctoring event: {str(e)}"
        )


@router.get("/session/{session_id}/summary", response_model=ProctoringSessionSummary)
def get_proctoring_session_summary(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get comprehensive proctoring summary for a session.
    
    Includes violation counts, risk scores, and detailed event timeline.
    """
    # Verify session ownership
    active_session = _require_active_session(db, current_user.id)
    if session_id != active_session.id:
        raise HTTPException(
            status_code=403,
            detail="Cannot access other users' session data"
        )
    
    try:
        summary = advanced_proctoring_service.get_session_proctoring_summary(db, session_id)
        return summary
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get session summary: {str(e)}"
        )


@router.get("/high-risk-sessions")
def get_high_risk_sessions(
    risk_threshold: float = Query(0.7, ge=0.0, le=1.0, description="Minimum risk score"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of sessions"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get sessions with high proctoring risk scores.
    
    Returns sessions exceeding the specified risk threshold, ordered by risk level.
    """
    # TODO: Add admin role check in production
    # if current_user.role != "admin":
    #     raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        high_risk_sessions = advanced_proctoring_service.get_high_risk_sessions(
            db, risk_threshold, limit
        )
        return {"sessions": high_risk_sessions, "threshold": risk_threshold}
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get high-risk sessions: {str(e)}"
        )


@router.get("/session/{session_id}/violations")
def check_violation_thresholds(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Check if session has exceeded violation thresholds.
    
    Returns threshold violations, critical violations, and recommendations.
    """
    # Verify session ownership
    active_session = _require_active_session(db, current_user.id)
    if session_id != active_session.id:
        raise HTTPException(
            status_code=403,
            detail="Cannot access other users' session data"
        )
    
    try:
        threshold_analysis = advanced_proctoring_service.check_violation_thresholds(db, session_id)
        return threshold_analysis
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check violation thresholds: {str(e)}"
        )


@router.get("/event-types")
def get_supported_event_types():
    """
    Get list of supported advanced proctoring event types.
    
    Returns event type definitions with risk scores and descriptions.
    """
    from app.models.advanced_proctoring import ADVANCED_PROCTORING_EVENTS, VIOLATION_RISK_SCORES
    
    event_types = []
    for event_key, event_value in ADVANCED_PROCTORING_EVENTS.items():
        event_types.append({
            "event_type": event_key,
            "internal_name": event_value,
            "risk_score": VIOLATION_RISK_SCORES.get(event_key, 0.1),
            "description": _get_event_description(event_key)
        })
    
    return {"event_types": event_types}


def _get_event_description(event_type: str) -> str:
    """Get human-readable description for event type."""
    descriptions = {
        "TAB_SWITCH": "Candidate switched browser tabs during assessment",
        "FULLSCREEN_EXIT": "Candidate exited fullscreen mode",
        "PAGE_RELOAD": "Candidate attempted to reload the page",
        "IDLE_ACTIVITY": "Candidate was inactive for extended period",
        "COPY_PASTE": "Candidate used copy/paste during assessment",
        "NETWORK_DISCONNECT": "Network connection was lost during assessment",
        "NETWORK_RECONNECT": "Network connection was restored during assessment",
        "MULTIPLE_PERSON_DETECTED": "Multiple faces detected in webcam feed",
        "FACE_NOT_VISIBLE": "Candidate's face not visible in webcam",
        "MOUTH_MOVEMENT_DETECTED": "Suspicious mouth movement detected",
        "LOOKING_AWAY": "Candidate looking away from screen",
        "HEAD_TURN_DETECTED": "Excessive head turning detected",
        "VOICE_ACTIVITY_DETECTED": "Voice activity detected during assessment",
        "CAMERA_PERMISSION_DENIED": "Camera access was denied",
        "MICROPHONE_PERMISSION_DENIED": "Microphone access was denied",
        "DEVICE_CHANGE": "Camera or microphone devices changed during assessment",
        "PROCTORING_INITIALIZED": "Advanced proctoring system initialized",
        "PROCTORING_ERROR": "Error in proctoring system",
    }
    return descriptions.get(event_type, "Unknown event type")
