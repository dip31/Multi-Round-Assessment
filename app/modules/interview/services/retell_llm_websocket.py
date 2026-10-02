"""
Custom LLM WebSocket Server for Retell Integration.

This runs inside EDI5 and communicates with Retell via the Custom LLM WebSocket protocol.
Retell connects to this WebSocket when a call starts.

Flow:
1. Retell initiates WebSocket to: wss://edi5.example.com/retell/llm/{call_id}
2. EDI5 sends config event
3. Retell sends call_details (if enabled)
4. Retell sends update_only events with live transcript
5. Retell sends response_required when it's agent's turn
6. EDI5 processes transcript through InterviewOrchestrator
7. EDI5 streams response back via response events
8. Repeat until interview complete

EDI5 remains the SOLE interview intelligence. Retell only handles:
- STT (speech-to-text)
- Turn detection (VAD)
- Audio streaming (WebRTC)
- TTS (text-to-speech)
- Interruption handling
"""

from __future__ import annotations

import json
import logging
import asyncio
from typing import Any, Dict, List, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
from contextlib import asynccontextmanager

from fastapi import WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.config.settings import settings
from app.models.interview import (
    ApprovedQuestionPool,
    InterviewSession,
    InterviewTurn,
    InterviewConversation,
    InterviewMessage,
    InterviewMessageSpeaker,
    InterviewMessageType,
)
from app.modules.interview.services.retell_adapter import (
    RetellAdapter, InterviewAction, InterviewActionType, get_retell_adapter
)
from app.modules.interview.services.interview_orchestrator import InterviewOrchestrator
from app.modules.interview.services.answer_understanding import AnswerUnderstanding
from app.modules.interview.services import question_planner
from app.modules.interview.services.interview_rl_engine import InterviewRLEngine
from app.services.groq_service import GroqService

logger = logging.getLogger(__name__)
groq_service = GroqService(settings.GROQ_API_KEY)


class RetellWSMessageType(str, Enum):
    """Retell → EDI5 message types."""
    CALL_DETAILS = "call_details"
    UPDATE_ONLY = "update_only"
    RESPONSE_REQUIRED = "response_required"
    REMINDER_REQUIRED = "reminder_required"
    PING_PONG = "ping_pong"


class EDI5WSMessageType(str, Enum):
    """EDI5 → Retell message types."""
    CONFIG = "config"
    RESPONSE = "response"
    AGENT_INTERRUPT = "agent_interrupt"
    UPDATE_AGENT = "update_agent"
    PING_PONG = "ping_pong"
    METADATA = "metadata"


@dataclass
class RetellLLMContext:
    """Per-call context for the Custom LLM WebSocket."""
    call_id: str
    edi5_interview_id: int
    interview_session: Optional[InterviewSession] = None
    db_session: Optional[Session] = None
    orchestrator: Optional[InterviewOrchestrator] = None
    
    # Conversation state
    current_transcript: List[Dict[str, Any]] = field(default_factory=list)
    last_user_transcript: str = ""
    last_agent_transcript: str = ""
    turn_count: int = 0
    response_id_counter: int = 0
    interrupt_id_counter: int = 0
    
    # Interview state
    is_first_turn: bool = True
    awaiting_user_response: bool = False
    interview_complete: bool = False
    
    # For streaming responses
    pending_response_id: Optional[int] = None
    streaming_content: str = ""


class RetellLLMWebSocketHandler:
    """
    Handles the Custom LLM WebSocket connection from Retell.
    
    This is the bridge between Retell's voice layer and EDI5's interview intelligence.
    """
    
    def __init__(
        self,
        websocket: WebSocket,
        call_id: str,
        adapter: RetellAdapter,
        get_db_session: Callable[[], Session],
    ):
        self.websocket = websocket
        self.call_id = call_id
        self.adapter = adapter
        self.get_db_session = get_db_session
        self.context = RetellLLMContext(call_id=call_id, edi5_interview_id=0)
        self._running = True
        self._send_lock = asyncio.Lock()
    
    async def handle_connection(self):
        """Main WebSocket connection handler."""
        logger.info(f"Retell LLM WebSocket connected for call {self.call_id}")
        
        try:
            # Send initial config
            await self._send_config()
            
            # Main message loop
            while self._running:
                try:
                    message = await self.websocket.receive_text()
                    await self._handle_message(message)
                except WebSocketDisconnect:
                    logger.info(f"Retell WebSocket disconnected for call {self.call_id}")
                    break
                except Exception as e:
                    logger.error(f"Error in WebSocket message loop: {e}")
                    await self._send_error_response(str(e))
                    
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
        finally:
            await self._cleanup()
    
    async def _send_config(self):
        """Send initial config event to Retell."""
        config_event = self.adapter.build_config_event(
            auto_reconnect=True,
            call_details=True,
            transcript_with_tool_calls=True,
        )
        await self._send_message(config_event)
    
    async def _handle_message(self, message: str):
        """Handle incoming message from Retell."""
        try:
            data = json.loads(message)
            interaction_type = data.get("interaction_type")
            
            if interaction_type == RetellWSMessageType.CALL_DETAILS:
                await self._handle_call_details(data)
            elif interaction_type == RetellWSMessageType.UPDATE_ONLY:
                await self._handle_update_only(data)
            elif interaction_type == RetellWSMessageType.RESPONSE_REQUIRED:
                await self._handle_response_required(data)
            elif interaction_type == RetellWSMessageType.REMINDER_REQUIRED:
                await self._handle_reminder_required(data)
            elif interaction_type == RetellWSMessageType.PING_PONG:
                await self._handle_ping_pong(data)
            else:
                logger.warning(f"Unknown interaction_type: {interaction_type}")
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Retell message: {e}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            await self._send_error_response(str(e))
    
    async def _handle_call_details(self, data: Dict[str, Any]):
        """Handle initial call details from Retell."""
        call_data = data.get("call", {})
        metadata = call_data.get("metadata", {})
        
        # Extract EDI5 interview session ID from metadata
        edi5_session_id = metadata.get("edi5_interview_session_id")
        if not edi5_session_id:
            logger.error(f"No edi5_interview_session_id in call metadata for call {self.call_id}")
            await self._close_with_error("Missing EDI5 session ID")
            return
        
        self.context.edi5_interview_id = int(edi5_session_id)
        
        # Load interview session and create orchestrator
        db = self.get_db_session()
        self.context.db_session = db
        
        interview = db.query(InterviewSession).filter(
            InterviewSession.id == self.context.edi5_interview_id
        ).first()
        
        if not interview:
            logger.error(f"EDI5 interview {self.context.edi5_interview_id} not found")
            await self._close_with_error("Interview not found")
            return
        
        self.context.interview_session = interview
        self.context.orchestrator = InterviewOrchestrator(db, groq_service)
        
        # Restore RL state
        rl_engine = InterviewRLEngine()
        rl_engine.from_dict(interview.rl_state or {})
        self.context.orchestrator._rl_engine = rl_engine
        self.context.orchestrator._state = dict(interview.rl_state or {})
        
        # Load interviewer profile
        from app.modules.interview.config import interviewer_profiles
        self.context.orchestrator._profile = interviewer_profiles.get_interviewer(
            interview.interviewer_id
        )
        
        logger.info(f"Retell call {self.call_id} linked to EDI5 interview {interview.id}")
    
    async def _handle_update_only(self, data: Dict[str, Any]):
        """Handle live transcript update."""
        transcript = data.get("transcript", [])
        turntaking = data.get("turntaking")
        
        self.context.current_transcript = transcript
        
        # Extract latest user utterance
        for utterance in reversed(transcript):
            if utterance.get("role") == "user":
                self.context.last_user_transcript = utterance.get("content", "")
                break
        
        # Extract latest agent utterance
        for utterance in reversed(transcript):
            if utterance.get("role") == "agent":
                self.context.last_agent_transcript = utterance.get("content", "")
                break
        
        logger.debug(f"Transcript updated: {len(transcript)} utterances, turntaking={turntaking}")
        
        # Persist structured transcript for analysis
        if self.context.interview_session and self.context.db_session:
            await self._persist_structured_transcript(transcript)
    
    async def _persist_structured_transcript(self, transcript: List[Dict[str, Any]]) -> None:
        """Persist structured transcript messages from custom LLM WebSocket.
        
        The transcript from Retell in edi5_core mode contains utterances with:
        - role: "agent" or "user"
        - content: text
        - utterance_id: unique ID
        - is_final: boolean
        - confidence: float
        """
        try:
            interview = self.context.interview_session
            db = self.context.db_session
            
            if not interview or not db:
                return
            
            # Get or create conversation record
            conversation = db.query(InterviewConversation).filter(
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
                db.add(conversation)
                db.flush()
            
            # Track existing utterance IDs
            existing_utterance_ids = set()
            existing_messages = db.query(InterviewMessage.retell_utterance_id).filter(
                InterviewMessage.conversation_id == conversation.id,
                InterviewMessage.retell_utterance_id.isnot(None)
            ).all()
            for (uid,) in existing_messages:
                if uid:
                    existing_utterance_ids.add(uid)
            
            new_messages = []
            ai_count = 0
            candidate_count = 0
            
            for idx, utterance in enumerate(transcript):
                utterance_id = utterance.get("utterance_id")
                role = utterance.get("role", "").lower()
                content = utterance.get("content", "").strip()
                is_final = utterance.get("is_final", True)
                confidence = utterance.get("confidence")
                
                if not content:
                    continue
                
                if utterance_id and utterance_id in existing_utterance_ids:
                    continue
                
                if role == "agent":
                    speaker = InterviewMessageSpeaker.AI
                    ai_count += 1
                elif role == "user":
                    speaker = InterviewMessageSpeaker.CANDIDATE
                    candidate_count += 1
                else:
                    speaker = InterviewMessageSpeaker.SYSTEM
                
                if speaker == InterviewMessageSpeaker.AI:
                    message_type = InterviewMessageType.QUESTION
                else:
                    message_type = InterviewMessageType.ANSWER
                
                message = InterviewMessage(
                    conversation_id=conversation.id,
                    sequence_number=idx + 1,
                    speaker=speaker.value,
                    text=content,
                    message_type=message_type.value,
                    retell_utterance_id=utterance_id,
                    is_final=is_final,
                    confidence=confidence,
                )
                new_messages.append(message)
                if utterance_id:
                    existing_utterance_ids.add(utterance_id)
            
            if new_messages:
                for msg in new_messages:
                    db.add(msg)
                
                conversation.total_messages = len(existing_utterance_ids)
                conversation.ai_message_count = ai_count
                conversation.candidate_message_count = candidate_count
                
                db.commit()
                logger.debug(f"Persisted {len(new_messages)} structured messages for interview {interview.id}")
                
        except Exception as e:
            logger.error(f"Failed to persist structured transcript for interview {self.context.edi5_interview_id}: {e}")
            db.rollback()
    
    async def _handle_response_required(self, data: Dict[str, Any]):
        """Handle response_required - Retell wants EDI5 to generate a response."""
        response_id = data.get("response_id", 0)
        transcript = data.get("transcript", [])
        
        logger.info(f"Response required (id={response_id}) for call {self.call_id}")
        
        self.context.pending_response_id = response_id
        self.context.response_id_counter = max(self.context.response_id_counter, response_id)
        
        # The interviewer greeting was spoken by Retell; start the core interview
        # by asking EDI5's first approved question.
        if self.context.is_first_turn:
            self.context.is_first_turn = False
            await self._ask_initial_question(response_id)
            return
        
        # Process the user's answer through EDI5 InterviewOrchestrator
        await self._process_user_answer(response_id, transcript)
    
    async def _handle_reminder_required(self, data: Dict[str, Any]):
        """Handle reminder_required - user has been silent."""
        response_id = data.get("response_id", 0)
        transcript = data.get("transcript", [])
        
        logger.info(f"Reminder required (id={response_id}) for call {self.call_id}")
        
        # This is like a retry for silence
        # EDI5's InterviewOrchestrator handles silence in _reprompt_for_silence
        # We can send a brief reminder
        reminder_text = "Are you still there? Take your time."
        
        await self._send_message(self.adapter.build_response_event(
            response_id=response_id,
            content=reminder_text,
            content_complete=True,
            no_interruption_allowed=False,
        ))
    
    async def _handle_ping_pong(self, data: Dict[str, Any]):
        """Handle ping-pong keepalive."""
        await self._send_message(self.adapter.build_ping_pong_event())

    async def _ask_initial_question(self, response_id: int):
        """Select and speak the first EDI5-owned question for a core-mode call."""
        interview = self.context.interview_session
        db = self.context.db_session
        orchestrator = self.context.orchestrator
        if not interview or not db or not orchestrator:
            await self._send_error_response("Interview session was not initialized.", response_id)
            return

        state = dict(interview.rl_state or {})
        if state.get("current_question_text"):
            question_text = state["current_question_text"]
            difficulty = state.get("current_question_difficulty", "MEDIUM")
        else:
            pool_record = db.query(ApprovedQuestionPool).filter(
                ApprovedQuestionPool.session_id == interview.session_id,
                ApprovedQuestionPool.admin_approved == True,
            ).first()
            if not pool_record:
                await self._send_error_response("No approved interview question pool was found.", response_id)
                return

            rl_engine = InterviewRLEngine()
            rl_engine.from_dict(state)
            state_for_selection = {"last_score": 0.5, "turn": interview.current_turn}
            last_turn = db.query(InterviewTurn).filter(
                InterviewTurn.interview_id == interview.id
            ).order_by(InterviewTurn.turn_number.desc()).first()
            if last_turn and last_turn.final_score is not None:
                state_for_selection["last_score"] = last_turn.final_score
            difficulty = rl_engine.select_difficulty(state_for_selection)
            selected = question_planner.select_question(
                pool_record.question_pool,
                asked_question_ids=set(rl_engine.asked_question_ids),
                phase=interview.phase,
                difficulty=difficulty,
                reuse_exhausted_pool=False,
            )
            if not selected:
                await self._send_error_response("No interview questions are available.", response_id)
                return

            question_text = selected["question"]
            question_id = question_planner.resolve_question_id(selected)
            rl_engine.current_question_text = question_text
            rl_engine.current_question_difficulty = selected.get("difficulty", difficulty)
            rl_engine.current_question_id = question_id
            rl_engine.asked_question_ids.append(question_id)
            interview.rl_state = rl_engine.to_dict()
            db.commit()

        orchestrator._state = dict(interview.rl_state or {})
        spoken_question = groq_service.rephrase_question(question_text, difficulty)
        await self._send_message(self.adapter.build_response_event(
            response_id=response_id,
            content=spoken_question,
            content_complete=True,
            no_interruption_allowed=False,
        ))
    
    async def _process_user_answer(self, response_id: int, transcript: List[Dict[str, Any]]):
        """Process user's answer through EDI5 InterviewOrchestrator."""
        if not self.context.orchestrator or not self.context.interview_session:
            logger.error("Orchestrator or interview session not initialized")
            return
        
        # Get the latest user answer
        user_answer = self.context.last_user_transcript
        if not user_answer:
            logger.warning("No user answer found in transcript")
            await self._send_acknowledgment(response_id)
            return
        
        # Get current question from orchestrator state
        question = self.context.orchestrator._state.get("current_question_text", "")
        if not question:
            logger.warning("No current question in state")
            await self._send_acknowledgment(response_id)
            return
        
        try:
            # Create a mock request for the orchestrator
            from app.modules.interview.schemas.interview_schema import (
                SubmitResponseRequest, BehavioralSnapshot
            )
            
            request = SubmitResponseRequest(
                transcript=user_answer,
                response_time_sec=5.0,  # Approximate - Retell doesn't give exact timing
                behavioral_snapshot=BehavioralSnapshot(
                    eye_contact_pct=0.5,
                    head_stability=0.5,
                    face_detected=True,
                    looking_away_count=0,
                    response_time_sec=5.0,
                    dominant_emotion="neutral",
                ),
            )
            
            # Process through InterviewOrchestrator
            # This runs the full EDI5 pipeline:
            # 1. AnswerUnderstanding (classification)
            # 2. FollowupPolicy (decide follow-up vs next)
            # 3. QuestionPlanner (select next question)
            # 4. RL update
            # 5. Generate interviewer response
            response = self.context.orchestrator.handle_response(
                self.context.interview_session,
                request,
            )
            
            # Convert EDI5 response to InterviewAction
            action = self._edi5_response_to_action(response)
            
            # Send response to Retell
            await self._send_edi5_action(response_id, action)
            
            # Update context
            self.context.turn_count += 1
            self.context.awaiting_user_response = (action.action_type in [
                InterviewActionType.ASK_QUESTION,
                InterviewActionType.FOLLOW_UP,
                InterviewActionType.CLARIFY,
            ])
            self.context.interview_complete = (action.action_type == InterviewActionType.END_INTERVIEW)
            
        except Exception as e:
            logger.error(f"Error processing user answer: {e}")
            await self._send_error_response(str(e), response_id)
    
    def _edi5_response_to_action(self, response) -> InterviewAction:
        """Convert EDI5 SubmitResponseResponse to InterviewAction."""
        if response.is_complete:
            return InterviewAction(
                action_type=InterviewActionType.END_INTERVIEW,
                question_text=response.message,
            )
        
        if response.action == "RETRY":
            return InterviewAction(
                action_type=InterviewActionType.RETRY,
                question_text=response.message,
            )
        
        if response.action == "FOLLOWUP":
            return InterviewAction(
                action_type=InterviewActionType.FOLLOW_UP,
                question_text=response.message,
                followup_type=response.followup_type,
            )
        
        if response.action == "NEXT":
            next_q = response.next_question
            return InterviewAction(
                action_type=InterviewActionType.ASK_QUESTION,
                question_text=next_q.text if next_q else response.message,
                question_id=next_q.text[:50] if next_q else None,
                difficulty=next_q.difficulty if next_q else None,
                topic=next_q.phase if next_q else None,
            )
        
        # Default
        return InterviewAction(
            action_type=InterviewActionType.WAIT,
            question_text=response.message,
        )
    
    async def _send_edi5_action(self, response_id: int, action: InterviewAction):
        """Send EDI5's decided action to Retell as streaming response."""
        events = self.adapter.format_action_for_retell(action, response_id)
        
        for event in events:
            await self._send_message(event)
    
    async def _send_acknowledgment(self, response_id: int):
        """Send empty acknowledgment when no response needed yet."""
        await self._send_message(self.adapter.build_response_event(
            response_id=response_id,
            content="",
            content_complete=True,
        ))
    
    async def _send_message(self, message: Dict[str, Any]):
        """Send message to Retell WebSocket with locking."""
        async with self._send_lock:
            if self._running:
                try:
                    await self.websocket.send_text(json.dumps(message))
                except Exception as e:
                    logger.error(f"Failed to send WebSocket message: {e}")
    
    async def _send_error_response(self, error: str, response_id: Optional[int] = None):
        """Send error response to Retell."""
        if response_id:
            await self._send_message(self.adapter.build_response_event(
                response_id=response_id,
                content="I apologize, there was a technical issue. Let's continue.",
                content_complete=True,
            ))
    
    async def _close_with_error(self, error: str):
        """Close connection with error."""
        logger.error(f"Closing WebSocket for call {self.call_id}: {error}")
        self._running = False
        try:
            await self.websocket.close(code=1011, reason=error)
        except Exception:
            pass
    
    async def _cleanup(self):
        """Cleanup on disconnect."""
        self._running = False
        if self.context.db_session:
            try:
                self.context.db_session.close()
            except Exception:
                pass
        logger.info(f"Retell LLM WebSocket cleaned up for call {self.call_id}")


# ── FastAPI WebSocket Endpoint ────────────────────────────────────────────

async def retell_llm_websocket_endpoint(
    websocket: WebSocket,
    call_id: str,
    adapter: RetellAdapter = Depends(get_retell_adapter),
):
    """
    Custom LLM WebSocket endpoint for Retell.
    
    Retell connects here when a web call starts.
    Path: /retell/llm/{call_id}
    """
    await websocket.accept()
    
    # Get DB session factory
    def get_db_session():
        from app.database.db import SessionLocal
        return SessionLocal()
    
    handler = RetellLLMWebSocketHandler(
        websocket=websocket,
        call_id=call_id,
        adapter=adapter,
        get_db_session=get_db_session,
    )
    
    await handler.handle_connection()