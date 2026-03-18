"""
Advanced Proctoring Service for AI-Based Online Proctoring System.

Handles computer vision events, audio analysis, and comprehensive violation detection
with confidence scoring and risk assessment.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, Float

from app.models.advanced_proctoring import AdvancedProctoringEvent, VIOLATION_RISK_SCORES
from app.schemas.advanced_proctoring import AdvancedProctorEventRequest, ProctoringSessionSummary


class AdvancedProctoringService:
    """Service for managing advanced proctoring events and analysis."""
    
    def __init__(self):
        self.violation_thresholds = {
            "TAB_SWITCH": {"max_allowed": 5, "risk_weight": 0.3},
            "FULLSCREEN_EXIT": {"max_allowed": 3, "risk_weight": 0.4},
            "PAGE_RELOAD": {"max_allowed": 1, "risk_weight": 0.8},
            "IDLE_ACTIVITY": {"max_allowed": 10, "risk_weight": 0.2},
            "COPY_PASTE": {"max_allowed": 0, "risk_weight": 0.6},
            "NETWORK_DISCONNECT": {"max_allowed": 0, "risk_weight": 0.7},
            "DEVICE_CHANGE": {"max_allowed": 0, "risk_weight": 0.7},
            "MULTIPLE_PERSON_DETECTED": {"max_allowed": 0, "risk_weight": 0.9},
            "FACE_NOT_VISIBLE": {"max_allowed": 5, "risk_weight": 0.7},
            "MOUTH_MOVEMENT_DETECTED": {"max_allowed": 8, "risk_weight": 0.5},
            "LOOKING_AWAY": {"max_allowed": 15, "risk_weight": 0.3},
            "HEAD_TURN_DETECTED": {"max_allowed": 10, "risk_weight": 0.4},
            "VOICE_ACTIVITY_DETECTED": {"max_allowed": 5, "risk_weight": 0.6},
        }

    def log_advanced_event(
        self,
        db: Session,
        event_data: AdvancedProctorEventRequest
    ) -> tuple[AdvancedProctoringEvent, float]:
        """Log an advanced proctoring event with risk assessment.
        
        Args:
            db: Database session
            event_data: Event data with confidence and metadata
            
        Returns:
            Tuple of (created event, calculated risk score)
        """
        # Create the event
        event = AdvancedProctoringEvent(
            session_id=event_data.session_id,
            event_type=event_data.event_type,
            confidence=event_data.confidence,
            event_metadata=event_data.metadata or {}
        )
        
        db.add(event)
        db.flush()
        
        # Calculate risk score
        risk_score = self._calculate_event_risk(event)
        
        # Update event metadata with risk score
        event.event_metadata["risk_score"] = risk_score
        event.event_metadata["processed_at"] = datetime.utcnow().isoformat()
        
        db.commit()
        
        return event, risk_score

    def get_session_proctoring_summary(
        self,
        db: Session,
        session_id: int
    ) -> ProctoringSessionSummary:
        """Get comprehensive proctoring summary for a session.
        
        Args:
            db: Database session
            session_id: Assessment session ID
            
        Returns:
            Proctoring session summary with violation counts and risk score
        """
        # Get all events for the session
        events = db.query(AdvancedProctoringEvent)\
            .filter(AdvancedProctoringEvent.session_id == session_id)\
            .order_by(desc(AdvancedProctoringEvent.created_at))\
            .all()
        
        # Count violations by type
        violation_counts = {}
        total_risk_score = 0.0
        
        for event in events:
            violation_counts[event.event_type] = violation_counts.get(event.event_type, 0) + 1
            total_risk_score += event.event_metadata.get("risk_score", 0.0)
        
        # Calculate overall risk score (normalized)
        overall_risk = min(total_risk_score / max(len(events), 1), 1.0)
        
        # Format events for response
        event_list = []
        for event in events:
            event_list.append({
                "id": event.id,
                "event_type": event.event_type,
                "confidence": event.confidence,
                "risk_score": event.event_metadata.get("risk_score", 0.0),
                "created_at": event.created_at.isoformat(),
                "metadata": event.event_metadata
            })
        
        return ProctoringSessionSummary(
            session_id=session_id,
            total_events=len(events),
            violation_counts=violation_counts,
            risk_score=overall_risk,
            events=event_list
        )

    def get_high_risk_sessions(
        self,
        db: Session,
        risk_threshold: float = 0.7,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get sessions with high proctoring risk scores.
        
        Args:
            db: Database session
            risk_threshold: Minimum risk score to include
            limit: Maximum number of sessions to return
            
        Returns:
            List of high-risk session summaries
        """
        # Get session IDs with risk scores above threshold
        high_risk_sessions = db.query(
            AdvancedProctoringEvent.session_id,
            func.count(AdvancedProctoringEvent.id).label('event_count'),
            func.avg(
                func.cast(AdvancedProctoringEvent.event_metadata['risk_score'], Float)
            ).label('avg_risk_score')
        )\
        .group_by(AdvancedProctoringEvent.session_id)\
        .having(
            func.avg(
                func.cast(AdvancedProctoringEvent.event_metadata['risk_score'], Float)
            ) >= risk_threshold
        )\
        .order_by(desc('avg_risk_score'))\
        .limit(limit)\
        .all()
        
        results = []
        for session_data in high_risk_sessions:
            session_id = session_data.session_id
            summary = self.get_session_proctoring_summary(db, session_id)
            results.append({
                "session_id": session_id,
                "event_count": session_data.event_count,
                "avg_risk_score": session_data.avg_risk_score,
                "total_violations": len(summary.events),
                "violation_counts": summary.violation_counts
            })
        
        return results

    def _calculate_event_risk(self, event: AdvancedProctoringEvent) -> float:
        """Calculate risk score for a specific event.
        
        Args:
            event: Advanced proctoring event
            
        Returns:
            Risk score between 0.0 and 1.0
        """
        # Base risk score from event type
        base_risk = VIOLATION_RISK_SCORES.get(event.event_type, 0.1)
        
        # Adjust by confidence if available
        if event.confidence is not None:
            base_risk *= event.confidence
        
        # Additional risk factors based on event type and metadata
        metadata = event.event_metadata or {}
        
        if event.event_type == "MULTIPLE_PERSON_DETECTED":
            face_count = metadata.get("face_count", 1)
            if face_count > 2:
                base_risk = min(base_risk * 1.5, 1.0)
        
        elif event.event_type == "FACE_NOT_VISIBLE":
            duration = metadata.get("duration_seconds", 0)
            if duration > 30:  # Long duration without face
                base_risk = min(base_risk * 1.3, 1.0)
        
        elif event.event_type == "VOICE_ACTIVITY_DETECTED":
            duration = metadata.get("duration_seconds", 0)
            if duration > 10:  # Long speaking duration
                base_risk = min(base_risk * 1.2, 1.0)
        
        return min(base_risk, 1.0)

    def check_violation_thresholds(
        self,
        db: Session,
        session_id: int
    ) -> Dict[str, Any]:
        """Check if session has exceeded violation thresholds.
        
        Args:
            db: Database session
            session_id: Assessment session ID
            
        Returns:
            Dictionary with threshold violations and recommendations
        """
        summary = self.get_session_proctoring_summary(db, session_id)
        
        threshold_violations = []
        critical_violations = []
        
        for event_type, count in summary.violation_counts.items():
            threshold = self.violation_thresholds.get(event_type)
            if threshold:
                if count > threshold["max_allowed"]:
                    violation = {
                        "event_type": event_type,
                        "count": count,
                        "max_allowed": threshold["max_allowed"],
                        "severity": "critical" if count > threshold["max_allowed"] * 2 else "warning"
                    }
                    threshold_violations.append(violation)
                    
                    if violation["severity"] == "critical":
                        critical_violations.append(event_type)
        
        return {
            "session_id": session_id,
            "overall_risk_score": summary.risk_score,
            "threshold_violations": threshold_violations,
            "critical_violations": critical_violations,
            "recommendation": self._generate_recommendation(summary.risk_score, critical_violations),
            "should_flag_for_review": len(critical_violations) > 0 or summary.risk_score > 0.8
        }

    def _generate_recommendation(self, risk_score: float, critical_violations: List[str]) -> str:
        """Generate recommendation based on risk assessment.
        
        Args:
            risk_score: Overall risk score (0.0-1.0)
            critical_violations: List of critical violation types
            
        Returns:
            Recommendation string
        """
        if risk_score < 0.3:
            return "Low risk - No action needed"
        elif risk_score < 0.6:
            return "Medium risk - Monitor session closely"
        elif risk_score < 0.8:
            return "High risk - Consider manual review"
        else:
            if critical_violations:
                return f"Critical risk - Immediate review required. Critical violations: {', '.join(critical_violations)}"
            else:
                return "Critical risk - Immediate review required"


# Global service instance
advanced_proctoring_service = AdvancedProctoringService()
