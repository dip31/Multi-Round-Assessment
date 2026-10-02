"""
Retell Webhook Handler for EDI5.

Receives real-time call events from Retell and updates EDI5 interview state.
This is separate from the normal interview /respond route - webhooks are
async notifications for audit, analytics, and session lifecycle tracking.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.core.auth import get_current_user
from app.database.db import get_db
from app.models.interview import InterviewSession
from app.modules.interview.services.retell_adapter import RetellAdapter, get_retell_adapter
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/integrations/retell",
    tags=["Retell Integration"],
)

# In-memory idempotency store (use Redis in production)
_processed_webhook_keys: set = set()


def _generate_idempotency_key(event_type: str, call_id: str, start_timestamp: Optional[int] = None) -> str:
    """Generate unique key for webhook deduplication."""
    if event_type == "transcript_updated":
        # transcript_updated fires many times - don't deduplicate by call_id alone
        # Use the latest payload as canonical, but track final one
        return f"{event_type}:{call_id}:latest"
    elif event_type in ("transfer_started", "transfer_bridged", "transfer_cancelled", "transfer_ended"):
        return f"{event_type}:{call_id}:{start_timestamp or 0}"
    else:
        return f"{event_type}:{call_id}"


async def _is_duplicate_webhook(key: str) -> bool:
    """Check if webhook was already processed."""
    if key in _processed_webhook_keys:
        return True
    _processed_webhook_keys.add(key)
    # Keep set bounded (in production use Redis with TTL)
    if len(_processed_webhook_keys) > 10000:
        # Remove oldest entries (simple approximation)
        _processed_webhook_keys.clear()
    return False


@router.post("/webhook")
async def handle_retell_webhook(
    request: Request,
    x_retell_signature: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    adapter: RetellAdapter = Depends(get_retell_adapter),
) -> Response:
    """
    Handle Retell webhook events.
    
    Events: call_started, call_ended, call_analyzed, transcript_updated, transfer_*
    
    Idempotent: Safe to process duplicate deliveries.
    """
    # Get raw body for signature verification
    raw_body = await request.body()
    raw_body_str = raw_body.decode("utf-8")
    
    # Verify webhook signature
    if not adapter.verify_webhook_signature(raw_body_str, x_retell_signature or ""):
        logger.warning("Invalid Retell webhook signature")
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Parse event
    try:
        event = adapter.parse_webhook_event(raw_body_str)
    except ValueError as e:
        logger.error(f"Failed to parse webhook: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    
    event_type = event["event_type"]
    call_id = event["call_id"]
    call_data = event["call_data"]
    
    logger.info(f"Retell webhook: {event_type} for call {call_id}")
    
    # Idempotency check
    start_ts = call_data.get("start_timestamp")
    idempotency_key = _generate_idempotency_key(event_type, call_id, start_ts)
    
    if event_type != "transcript_updated" and await _is_duplicate_webhook(idempotency_key):
        logger.debug(f"Duplicate webhook ignored: {idempotency_key}")
        return Response(status_code=204)
    
    # Find EDI5 interview session by Retell call_id
    interview = db.query(InterviewSession).filter(
        InterviewSession.retell_call_id == call_id
    ).first()
    
    if not interview:
        logger.warning(f"No EDI5 session found for Retell call {call_id}")
        # Don't fail - webhook may be for a call not linked to EDI5
        return Response(status_code=204)
    
    # Process based on event type
    try:
        if event_type == "call_started":
            await _handle_call_started(interview, call_data, db)
        elif event_type == "call_ended":
            await _handle_call_ended(interview, call_data, db)
        elif event_type == "call_analyzed":
            await _handle_call_analyzed(interview, call_data, db)
        elif event_type == "transcript_updated":
            await _handle_transcript_updated(interview, call_data, db)
        elif event_type in ("transfer_started", "transfer_bridged", "transfer_cancelled", "transfer_ended"):
            await _handle_transfer_event(interview, event_type, call_data, db)
        else:
            logger.info(f"Unhandled webhook event type: {event_type}")
    except Exception as e:
        logger.error(f"Error processing webhook {event_type} for call {call_id}: {e}")
        # Don't raise - we acknowledged the webhook
        # In production, send to dead letter queue
    
    return Response(status_code=204)


async def _handle_call_started(
    interview: InterviewSession,
    call_data: Dict[str, Any],
    db: Session,
) -> None:
    """Handle call_started webhook."""
    interview.status = "ACTIVE"
    if not interview.started_at:
        from datetime import datetime
        interview.started_at = datetime.fromtimestamp(call_data.get("start_timestamp", 0) / 1000)
    db.commit()
    logger.info(f"Interview {interview.id} marked ACTIVE via call_started")


async def _handle_call_ended(
    interview: InterviewSession,
    call_data: Dict[str, Any],
    db: Session,
) -> None:
    """Handle call_ended webhook."""
    from datetime import datetime
    
    # Only complete if not already completed by EDI5 logic
    if interview.phase != "COMPLETE":
        interview.phase = "COMPLETE"
        interview.status = "COMPLETED"
        interview.completion_reason = "CALL_ENDED"
        interview.completed_at = datetime.fromtimestamp(call_data.get("end_timestamp", 0) / 1000)
        db.commit()
        logger.info(f"Interview {interview.id} completed via call_ended webhook")


async def _handle_call_analyzed(
    interview: InterviewSession,
    call_data: Dict[str, Any],
    db: Session,
) -> None:
    """Handle call_analyzed webhook - post-call analysis complete."""
    # Store analysis results if needed
    analysis = call_data.get("call_analysis", {})
    if analysis:
        interview.personalization_metadata = {
            **(interview.personalization_metadata or {}),
            "retell_analysis": analysis,
        }
        db.commit()
    logger.info(f"Interview {interview.id} analysis stored via call_analyzed")


async def _handle_transcript_updated(
    interview: InterviewSession,
    call_data: Dict[str, Any],
    db: Session,
) -> None:
    """Handle transcript_updated webhook - live transcript updates.
    
    Note: This fires frequently. We store the latest transcript for
    real-time monitoring but don't create InterviewTurn records here -
    those are created by the InterviewOrchestrator via the custom LLM WebSocket.
    """
    transcript = call_data.get("transcript", "")
    interview.personalization_metadata = {
        **(interview.personalization_metadata or {}),
        "retell_live_transcript": transcript,
        "retell_transcript_object": call_data.get("transcript_object"),
        "retell_transcript_updated_at": call_data.get("start_timestamp"),
    }
    db.commit()


async def _handle_transfer_event(
    interview: InterviewSession,
    event_type: str,
    call_data: Dict[str, Any],
    db: Session,
) -> None:
    """Handle transfer-related webhooks."""
    transfer_info = {
        "event": event_type,
        "timestamp": call_data.get("start_timestamp"),
        "destination": call_data.get("transfer_destination"),
        "option": call_data.get("transfer_option"),
    }
    
    interview.personalization_metadata = {
        **(interview.personalization_metadata or {}),
        "retell_transfers": [
            *(interview.personalization_metadata or {}).get("retell_transfers", []),
            transfer_info,
        ],
    }
    db.commit()
    logger.info(f"Interview {interview.id} transfer event: {event_type}")


# ── Health Check ───────────────────────────────────────────────────────────

@router.get("/health")
async def retell_integration_health() -> Dict[str, Any]:
    """Health check for Retell integration."""
    return {
        "status": "healthy",
        "retell_api_configured": bool(settings.RETELL_API_KEY),
        "webhook_endpoint": "/integrations/retell/webhook",
    }