"""
Frontend Transcript WebSocket for EDI5.

Provides real-time transcript streaming from backend to frontend during interview.
Works for both edi5_core (via Custom LLM WebSocket) and retell_hosted (via webhook) modes.
"""

from __future__ import annotations

import itertools
import json
import logging
from typing import Dict, Set, Optional
from dataclasses import dataclass, field
from collections import defaultdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.models.interview import InterviewSession

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/interview",
    tags=["Interview Transcript"],
)


@dataclass(eq=False)
class TranscriptConnection:
    """Represents a frontend WebSocket connection for transcript streaming."""
    websocket: WebSocket
    interview_id: int
    user_id: int
    conn_id: str = ""


class TranscriptConnectionManager:
    """Manages active transcript WebSocket connections."""

    # Monotonic counter so two connections for the same interview and user can
    # never share an id. Previously the id ended in ``id(self)``, which is the
    # manager singleton's address and therefore a constant — two sockets for
    # one interview collided, and the first one's cleanup silently evicted the
    # second, still-live socket from the broadcast set.
    _seq = itertools.count(1)

    def __init__(self):
        # interview_id -> set of connections
        self._connections: Dict[int, Set[TranscriptConnection]] = defaultdict(set)
        # connection_id -> connection (for cleanup)
        self._all_connections: Dict[str, TranscriptConnection] = {}

    def _generate_connection_id(self, interview_id: int, user_id: int) -> str:
        return f"{interview_id}:{user_id}:{next(self._seq)}"

    async def connect(self, websocket: WebSocket, interview_id: int, user_id: int) -> str:
        """Register an **already-accepted** transcript WebSocket connection.

        The caller owns ``websocket.accept()`` — see the ordering note in
        :func:`transcript_websocket_endpoint`. This method only registers.
        """
        conn_id = self._generate_connection_id(interview_id, user_id)

        connection = TranscriptConnection(
            websocket=websocket,
            interview_id=interview_id,
            user_id=user_id,
            conn_id=conn_id,
        )

        self._connections[interview_id].add(connection)
        self._all_connections[conn_id] = connection

        logger.info(
            f"[TranscriptWS] registered conn_id={conn_id} "
            f"active={len(self._connections[interview_id])}"
        )
        return conn_id

    def disconnect(self, conn_id: str) -> None:
        """Remove a transcript WebSocket connection."""
        connection = self._all_connections.pop(conn_id, None)
        if connection:
            self._connections[connection.interview_id].discard(connection)
            if not self._connections[connection.interview_id]:
                del self._connections[connection.interview_id]
            logger.info(
                f"[TranscriptWS] websocket disconnected: conn_id={conn_id}, "
                f"interview={connection.interview_id}, user={connection.user_id}"
            )

    async def broadcast_to_interview(self, interview_id: int, event: dict) -> None:
        """Send transcript event to all connections for an interview."""
        connections = self._connections.get(interview_id, set())
        logger.info(
            f"[TranscriptWS] broadcast event: {event.get('type')} "
            f"interview={interview_id}"
        )
        logger.info(f"[TranscriptWS] broadcast recipient count: {len(connections)}")
        if not connections:
            return

        message = json.dumps(event)
        disconnected = []

        # Iterate a snapshot: a send failure mutates the set via disconnect().
        for connection in list(connections):
            try:
                await connection.websocket.send_text(message)
            except Exception as e:
                logger.warning(f"Failed to send transcript event to interview {interview_id}: {e}")
                disconnected.append(connection)

        # Clean up disconnected connections
        for conn in disconnected:
            self.disconnect(conn.conn_id)

    def get_connection_count(self, interview_id: int) -> int:
        return len(self._connections.get(interview_id, set()))


# Global connection manager
transcript_manager = TranscriptConnectionManager()


async def _reject(websocket: WebSocket, code: int, reason: str) -> None:
    """Tell an accepted socket why it is being closed, then close it.

    The error frame is sent before the close so the frontend has a readable
    reason even where only the numeric close code is surfaced.
    """
    try:
        await websocket.send_text(json.dumps({
            "type": "error",
            "data": {"message": reason},
        }))
    except Exception:
        pass
    await websocket.close(code=code, reason=reason)


@router.websocket("/session/{interview_id}/transcript")
async def transcript_websocket_endpoint(
    websocket: WebSocket,
    interview_id: int,
    token: str = Query(..., description="JWT access token"),
):
    """
    WebSocket endpoint for real-time transcript streaming.

    Frontend connects here to receive live transcript updates during interview.

    Query params:
    - token: JWT access token for authentication

    Messages sent to frontend:
    - {"type": "transcript", "data": {...}}
    - {"type": "transcript_final", "data": {...}}
    - {"type": "transcript_clear", "data": {}}
    - {"type": "error", "data": {"message": "..."}}

    Handshake ordering
    ------------------
    ``accept()`` runs **before** authentication, deliberately. Under the ASGI
    contract, sending ``websocket.close`` before ``websocket.accept`` makes the
    server answer the HTTP upgrade with a 403; the browser then reports an
    opaque close code 1006 with an empty reason and the application's own
    4001/4004 codes never arrive. Accepting first is the only way for a client
    to learn *why* it was refused. No payload is sent before authentication
    succeeds, and a failed check closes the socket immediately.
    """
    # Authenticate user via token
    from app.config.settings import settings
    from jose import jwt, JWTError

    logger.info("[TranscriptWS] connection requested")
    logger.info(f"[TranscriptWS] interview_id: {interview_id}")
    logger.info(f"[TranscriptWS] token received: {'yes' if token else 'no'}")

    await websocket.accept()
    logger.info("[TranscriptWS] websocket accepted")

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = int(payload.get("sub", 0))
        if not user_id:
            raise ValueError("token carries no subject claim")
    except (JWTError, ValueError) as e:
        # Log why the token was rejected, never the token itself.
        logger.warning(f"[TranscriptWS] authentication failed: {e}")
        await _reject(websocket, 4001, "Authentication failed")
        return

    logger.info(f"[TranscriptWS] authentication successful user_id={user_id}")

    # Verify interview exists and belongs to user — use a short-lived manual
    # DB session so the generator-based get_db dependency doesn't interfere
    # with the long-lived WebSocket connection.
    from app.database.db import SessionLocal
    from app.models.assessment import AssessmentSession
    db = SessionLocal()
    try:
        interview = db.query(InterviewSession).join(
            AssessmentSession, InterviewSession.session_id == AssessmentSession.id
        ).filter(
            InterviewSession.id == interview_id,
            AssessmentSession.user_id == user_id,
        ).first()
    finally:
        db.close()

    if not interview:
        logger.warning(
            f"[TranscriptWS] interview {interview_id} not found for user {user_id}"
        )
        await _reject(websocket, 4004, "Interview not found")
        return

    logger.info(
        f"[TranscriptWS] interview verified: interview_id={interview_id}, "
        f"user_id={user_id}"
    )

    # Register the accepted connection
    conn_id = await transcript_manager.connect(websocket, interview_id, user_id)

    try:
        # Send initial connection confirmation
        await websocket.send_text(json.dumps({
            "type": "connected",
            "data": {"interview_id": interview_id}
        }))

        # Keep connection alive - wait for disconnect
        while True:
            try:
                # We don't expect messages from frontend, but read to detect disconnect
                await websocket.receive_text()
            except WebSocketDisconnect:
                break
            except Exception:
                break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"[TranscriptWS] error for interview {interview_id}: {e}")
    finally:
        transcript_manager.disconnect(conn_id)


# Helper functions for other modules to broadcast transcript events
async def broadcast_transcript_update(interview_id: int, transcript_event: dict) -> None:
    """Broadcast a transcript update to all frontend connections for an interview."""
    event = {
        "type": "transcript",
        "data": transcript_event,
    }
    await transcript_manager.broadcast_to_interview(interview_id, event)


async def broadcast_transcript_final(interview_id: int, transcript_event: dict) -> None:
    """Broadcast a final transcript event to all frontend connections for an interview."""
    event = {
        "type": "transcript_final",
        "data": transcript_event,
    }
    await transcript_manager.broadcast_to_interview(interview_id, event)


async def broadcast_transcript_clear(interview_id: int) -> None:
    """Signal frontend to clear transcript (e.g., on interview reset)."""
    event = {
        "type": "transcript_clear",
        "data": {},
    }
    await transcript_manager.broadcast_to_interview(interview_id, event)