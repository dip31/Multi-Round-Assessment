"""
Retell Transcript Finalization Service for EDI5.

Retrieves the authoritative final transcript from Retell after call completion,
reconciles it with live messages, and persists the finalized conversation.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.config.settings import settings
from app.models.interview import (
    InterviewSession,
    InterviewConversation,
    InterviewMessage,
    InterviewMessageSpeaker,
    InterviewMessageType,
    InterviewTurn,
)
from app.modules.interview.services.transcript_normalizer import (
    normalize_call_transcript_object,
    CanonicalTranscriptEvent,
)

logger = logging.getLogger(__name__)


@dataclass
class FinalizationResult:
    """Result of transcript finalization attempt."""
    success: bool
    status: str  # pending | processing | completed | failed | not_ready | no_call
    message: str
    transcript_finalized: bool = False
    messages_reconciled: int = 0
    error: Optional[str] = None


class RetellFinalizationService:
    """
    Service for retrieving and persisting authoritative final transcripts from Retell.
    
    Handles:
    - Calling Retell's call.retrieve() API
    - Validating call ownership
    - Normalizing final transcript_object
    - Reconciling with live messages
    - Idempotent finalization with retry support
    """

    def __init__(self, db: Session):
        self.db = db

    async def finalize_interview_transcript(
        self,
        interview_id: int,
        force: bool = False,
    ) -> FinalizationResult:
        """
        Finalize the transcript for an interview by retrieving the final call from Retell.

        Args:
            interview_id: The EDI5 interview session ID
            force: If True, re-finalize even if already completed

        Returns:
            FinalizationResult with status and details
        """
        interview = self.db.query(InterviewSession).filter(
            InterviewSession.id == interview_id
        ).first()

        if not interview:
            return FinalizationResult(
                success=False,
                status="failed",
                message=f"Interview {interview_id} not found",
                error="Interview not found",
            )

        # Skip if no Retell call ID
        if not interview.retell_call_id:
            interview.transcript_status = "completed"
            interview.transcript_source = "live"
            interview.transcript_finalized_at = datetime.now()
            self.db.commit()
            return FinalizationResult(
                success=True,
                status="no_call",
                message="No Retell call ID; transcript sourced from live events only",
            )

        # Idempotent: if already completed and not forced, return existing
        if interview.transcript_status == "completed" and not force:
            return FinalizationResult(
                success=True,
                status="completed",
                message="Transcript already finalized",
                transcript_finalized=True,
            )

        # Skip if already processing
        if interview.transcript_status == "processing":
            return FinalizationResult(
                success=False,
                status="processing",
                message="Finalization already in progress",
            )

        # Mark as processing
        interview.transcript_status = "processing"
        interview.transcript_finalization_error = None
        self.db.commit()

        try:
            # Retrieve call from Retell (sync SDK call in thread pool)
            call_response = await asyncio.to_thread(
                self._retrieve_call,
                interview.retell_call_id,
            )

            # Validate ownership
            if not self._validate_call_ownership(call_response, interview_id):
                error_msg = f"Call {interview.retell_call_id} does not belong to interview {interview_id}"
                logger.error(error_msg)
                interview.transcript_status = "failed"
                interview.transcript_finalization_error = error_msg
                self.db.commit()
                return FinalizationResult(
                    success=False,
                    status="failed",
                    message=error_msg,
                    error=error_msg,
                )

            # Check if call has ended
            call_status = getattr(call_response, "call_status", None)
            if call_status != "ended":
                # Call not yet ended; keep as pending, will retry on call_analyzed webhook
                interview.transcript_status = "pending"
                interview.transcript_finalization_error = f"Call status: {call_status}"
                self.db.commit()
                return FinalizationResult(
                    success=False,
                    status="not_ready",
                    message=f"Call not yet ended (status: {call_status})",
                )

            # Extract and normalize final transcript
            transcript_object = getattr(call_response, "transcript_object", None)
            if not transcript_object:
                # Fall back to flat transcript string if available
                flat_transcript = getattr(call_response, "transcript", None)
                if flat_transcript:
                    result = await self._persist_flat_transcript(
                        interview, flat_transcript, call_response
                    )
                    return result
                else:
                    error_msg = "No transcript_object or transcript in call response"
                    logger.warning(f"Interview {interview_id}: {error_msg}")
                    interview.transcript_status = "failed"
                    interview.transcript_finalization_error = error_msg
                    self.db.commit()
                    return FinalizationResult(
                        success=False,
                        status="failed",
                        message=error_msg,
                        error=error_msg,
                    )

            # Normalize final transcript
            canonical_events = normalize_call_transcript_object(
                transcript_object,
                base_sequence=0,
                interview_turn_id=None,
            )

            if not canonical_events:
                error_msg = "Retell call transcript_object contains no valid utterances"
                logger.warning(f"Interview {interview_id}: {error_msg}")
                interview.transcript_status = "failed"
                interview.transcript_finalization_error = error_msg
                self.db.commit()
                return FinalizationResult(
                    success=False,
                    status="failed",
                    message=error_msg,
                    error=error_msg,
                )

            # Reconcile with live messages
            messages_reconciled = await self._reconcile_final_transcript(
                interview, canonical_events
            )

            # Store final call metadata in personalization_metadata
            self._store_final_call_metadata(interview, call_response)

            # Mark as completed
            interview.transcript_status = "completed"
            interview.transcript_finalized_at = datetime.now()
            interview.transcript_source = "final"
            interview.transcript_finalization_error = None
            self.db.commit()

            # Trigger post-interview analysis after successful finalization
            # This runs in background to not block the webhook response
            try:
                from app.modules.interview.services.interview_analysis import get_interview_analysis_service
                analysis_service = get_interview_analysis_service()
                # Run analysis in background (fire and forget)
                asyncio.create_task(self._run_analysis(analysis_service, interview_id))
            except Exception as e:
                logger.warning(f"Failed to trigger analysis for interview {interview_id}: {e}")

            logger.info(
                f"Finalized transcript for interview {interview_id}: "
                f"{messages_reconciled} messages reconciled"
            )

            return FinalizationResult(
                success=True,
                status="completed",
                message="Transcript finalized successfully",
                transcript_finalized=True,
                messages_reconciled=messages_reconciled,
            )

        except Exception as e:
            self.db.rollback()
            error_msg = f"Finalization failed: {str(e)}"
            logger.error(f"Interview {interview_id}: {error_msg}", exc_info=True)
            try:
                failed_interview = self.db.query(InterviewSession).filter(
                    InterviewSession.id == interview_id
                ).first()
                if failed_interview:
                    failed_interview.transcript_status = "failed"
                    failed_interview.transcript_finalization_error = error_msg
                    self.db.commit()
            except Exception as rollback_err:
                self.db.rollback()
                logger.error(f"Failed to record finalization error state for interview {interview_id}: {rollback_err}")
            return FinalizationResult(
                success=False,
                status="failed",
                message=error_msg,
                error=error_msg,
            )

    def _retrieve_call(self, call_id: str) -> Any:
        """Retrieve call from Retell (synchronous SDK call)."""
        from retell import Retell
        client = Retell(api_key=settings.RETELL_API_KEY)
        return client.call.retrieve(call_id)

    def _validate_call_ownership(self, call_response: Any, interview_id: int) -> bool:
        """Validate that the Retell call belongs to this EDI5 interview."""
        metadata = getattr(call_response, "metadata", None)
        if not metadata:
            return False

        # We store edi5_interview_session_id in metadata at call creation
        stored_id = None
        if isinstance(metadata, dict):
            stored_id = metadata.get("edi5_interview_session_id")
        elif hasattr(metadata, "get"):
            stored_id = metadata.get("edi5_interview_session_id")

        if stored_id is None:
            logger.warning(f"Call {call_response.call_id} has no edi5_interview_session_id in metadata")
            return False

        try:
            return int(stored_id) == interview_id
        except (ValueError, TypeError):
            return False

    async def _reconcile_final_transcript(
        self,
        interview: InterviewSession,
        canonical_events: List[CanonicalTranscriptEvent],
    ) -> int:
        """
        Reconcile final transcript with live messages.

        Strategy:
        - Final transcript is authoritative for the ordered conversation.
        - For each position (sequence), update existing message or insert new.
        - Delete any surplus messages beyond final length.
        - Preserve turn_id from existing messages when updating.
        """
        conversation = self.db.query(InterviewConversation).filter(
            InterviewConversation.interview_id == interview.id
        ).first()

        if not conversation:
            # Create conversation if doesn't exist
            conversation = InterviewConversation(
                interview_id=interview.id,
                session_id=interview.session_id,
                total_messages=0,
                ai_message_count=0,
                candidate_message_count=0,
            )
            self.db.add(conversation)
            self.db.flush()

        # Load existing messages ordered by sequence
        existing_messages = self.db.query(InterviewMessage).filter(
            InterviewMessage.conversation_id == conversation.id
        ).order_by(InterviewMessage.sequence_number).all()

        existing_by_seq = {msg.sequence_number: msg for msg in existing_messages}
        final_length = len(canonical_events)
        reconciled = 0

        # Update or insert for each position in final transcript
        for idx, event in enumerate(canonical_events):
            seq_num = event.sequence  # 1-based from normalizer
            existing_msg = existing_by_seq.get(seq_num)

            # Map canonical speaker to InterviewMessageSpeaker
            if event.speaker == "ai":
                speaker = InterviewMessageSpeaker.AI
                message_type = InterviewMessageType.QUESTION
            elif event.speaker == "candidate":
                speaker = InterviewMessageSpeaker.CANDIDATE
                message_type = InterviewMessageType.ANSWER
            else:
                speaker = InterviewMessageSpeaker.SYSTEM
                message_type = InterviewMessageType.SYSTEM

            if existing_msg:
                # Update existing message
                existing_msg.speaker = speaker.value
                existing_msg.text = event.text
                existing_msg.message_type = message_type.value
                existing_msg.is_final = True
                existing_msg.confidence = event.confidence
                existing_msg.retell_utterance_id = event.retell_utterance_id
                # Verify existing turn_id against DB if set
                if existing_msg.turn_id is not None:
                    valid_turn = self.db.query(InterviewTurn).filter(InterviewTurn.id == existing_msg.turn_id).first()
                    if not valid_turn:
                        existing_msg.turn_id = None
                reconciled += 1
            else:
                # Insert new message with verified turn_id or None
                valid_turn_id = None
                if event.interview_turn_id is not None:
                    valid_turn = self.db.query(InterviewTurn).filter(InterviewTurn.id == event.interview_turn_id).first()
                    if valid_turn:
                        valid_turn_id = valid_turn.id

                new_msg = InterviewMessage(
                    conversation_id=conversation.id,
                    sequence_number=seq_num,
                    speaker=speaker.value,
                    text=event.text,
                    message_type=message_type.value,
                    is_final=True,
                    confidence=event.confidence,
                    retell_utterance_id=event.retell_utterance_id,
                    turn_id=valid_turn_id,
                )
                self.db.add(new_msg)
                reconciled += 1

        # Delete surplus messages beyond final length
        surplus_messages = self.db.query(InterviewMessage).filter(
            InterviewMessage.conversation_id == conversation.id,
            InterviewMessage.sequence_number > final_length,
        ).all()
        for msg in surplus_messages:
            self.db.delete(msg)

        # Recompute conversation counts from DB
        total_messages = self.db.query(InterviewMessage).filter(
            InterviewMessage.conversation_id == conversation.id
        ).count()
        ai_count = self.db.query(InterviewMessage).filter(
            InterviewMessage.conversation_id == conversation.id,
            InterviewMessage.speaker == InterviewMessageSpeaker.AI.value,
        ).count()
        candidate_count = self.db.query(InterviewMessage).filter(
            InterviewMessage.conversation_id == conversation.id,
            InterviewMessage.speaker == InterviewMessageSpeaker.CANDIDATE.value,
        ).count()

        conversation.total_messages = total_messages
        conversation.ai_message_count = ai_count
        conversation.candidate_message_count = candidate_count

        self.db.commit()
        return reconciled

    async def _persist_flat_transcript(
        self,
        interview: InterviewSession,
        flat_transcript: str,
        call_response: Any,
    ) -> FinalizationResult:
        """Fallback: persist flat transcript string when transcript_object unavailable."""
        try:
            conversation = self.db.query(InterviewConversation).filter(
                InterviewConversation.interview_id == interview.id
            ).first()

            if not conversation:
                conversation = InterviewConversation(
                    interview_id=interview.id,
                    session_id=interview.session_id,
                    total_messages=0,
                    ai_message_count=0,
                    candidate_message_count=0,
                )
                self.db.add(conversation)
                self.db.flush()

            # Clear existing messages
            self.db.query(InterviewMessage).filter(
                InterviewMessage.conversation_id == conversation.id
            ).delete()

            # Parse "Speaker: content" lines
            lines = [line.strip() for line in flat_transcript.split("\n") if line.strip()]
            ai_count = 0
            candidate_count = 0

            for idx, line in enumerate(lines):
                if ":" not in line:
                    continue
                speaker_part, content = line.split(":", 1)
                speaker_part = speaker_part.strip().lower()
                content = content.strip()
                if not content:
                    continue

                if speaker_part in ("interviewer", "agent", "ai"):
                    speaker = InterviewMessageSpeaker.AI
                    message_type = InterviewMessageType.QUESTION
                    ai_count += 1
                elif speaker_part in ("candidate", "user", "you"):
                    speaker = InterviewMessageSpeaker.CANDIDATE
                    message_type = InterviewMessageType.ANSWER
                    candidate_count += 1
                else:
                    speaker = InterviewMessageSpeaker.SYSTEM
                    message_type = InterviewMessageType.SYSTEM

                msg = InterviewMessage(
                    conversation_id=conversation.id,
                    sequence_number=idx + 1,
                    speaker=speaker.value,
                    text=content,
                    message_type=message_type.value,
                    is_final=True,
                    turn_id=None,
                )
                self.db.add(msg)

            conversation.total_messages = len(lines)
            conversation.ai_message_count = ai_count
            conversation.candidate_message_count = candidate_count

            self._store_final_call_metadata(interview, call_response)
            interview.transcript_status = "completed"
            interview.transcript_finalized_at = datetime.now()
            interview.transcript_source = "final"
            self.db.commit()

            return FinalizationResult(
                success=True,
                status="completed",
                message="Flat transcript persisted as fallback",
                transcript_finalized=True,
                messages_reconciled=len(lines),
            )

        except Exception as e:
            self.db.rollback()
            error_msg = f"Flat transcript persistence failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            try:
                failed_interview = self.db.query(InterviewSession).filter(
                    InterviewSession.id == interview.id
                ).first()
                if failed_interview:
                    failed_interview.transcript_status = "failed"
                    failed_interview.transcript_finalization_error = error_msg
                    self.db.commit()
            except Exception as rb_err:
                self.db.rollback()
                logger.error(f"Failed to record flat transcript error: {rb_err}")
            return FinalizationResult(
                success=False,
                status="failed",
                message=error_msg,
                error=error_msg,
            )

    def _store_final_call_metadata(self, interview: InterviewSession, call_response: Any) -> None:
        """Store relevant final call metadata in personalization_metadata JSONB."""
        metadata = dict(interview.personalization_metadata or {})

        # Store key fields from final call response
        metadata["retell_final_call"] = {
            "call_id": getattr(call_response, "call_id", None),
            "call_status": getattr(call_response, "call_status", None),
            "disconnection_reason": getattr(call_response, "disconnection_reason", None),
            "duration_ms": getattr(call_response, "duration_ms", None),
            "start_timestamp": getattr(call_response, "start_timestamp", None),
            "end_timestamp": getattr(call_response, "end_timestamp", None),
            "recording_url": getattr(call_response, "recording_url", None),
            "call_analysis": getattr(call_response, "call_analysis", None),
            "finalized_at": datetime.now().isoformat(),
        }

        # Also store flat transcript if present
        flat_transcript = getattr(call_response, "transcript", None)
        if flat_transcript:
            metadata["retell_final_call"]["transcript"] = flat_transcript

        interview.personalization_metadata = metadata


    async def _run_analysis(
        self,
        analysis_service: Any,
        interview_id: int,
    ) -> None:
        """Run post-interview analysis in background."""
        try:
            # Create a new DB session for the background task
            from app.database.db import SessionLocal
            db = SessionLocal()
            try:
                analysis = analysis_service.analyze_interview(
                    db=db,
                    interview_id=interview_id,
                    persist=True,
                    update_competency=True,
                )
                logger.info(f"Background analysis completed for interview {interview_id}")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Background analysis failed for interview {interview_id}: {e}")


def get_retell_finalization_service(db: Session) -> RetellFinalizationService:
    """Factory function for dependency injection."""
    return RetellFinalizationService(db)