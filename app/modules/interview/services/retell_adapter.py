"""
Retell AI Adapter for EDI5 Interview Platform.

Isolates all Retell-specific implementation from EDI5 core interview logic.
EDI5 remains the authoritative interview intelligence; Retell provides
real-time voice transport (STT, TTS, turn detection, interruption, audio streaming).

This module follows the architecture:
    Candidate ↔ Retell ↔ EDI5 InterviewOrchestrator ↔ EDI5 Interview Intelligence

Retell must NOT independently decide:
- what competency to test
- whether an answer is correct
- whether to follow up
- which question to ask
- interview completion
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, Awaitable
from enum import Enum

import httpx
from fastapi import Request, HTTPException

from app.config.settings import settings
from app.modules.interview.config import interviewer_profiles
from app.modules.interview.config.interviewer_profiles import DEFAULT_INTERVIEWER_ID

logger = logging.getLogger(__name__)


# ── Retell API Configuration ────────────────────────────────────────────────

RETELL_API_BASE = "https://api.retellai.com"
RETELL_API_VERSION = "v3"  # For web calls

# Mapping from static interviewer IDs to Retell-compatible voice configs
# Static profiles use Sarvam voices; Retell needs its own voice models.
# Allowed Retell voice_model values: eleven_turbo_v2, eleven_flash_v2, eleven_turbo_v2_5,
# eleven_flash_v2_5, eleven_multilingual_v2, eleven_v3, sonic-3, sonic-3-latest,
# sonic-3.5, sonic-3.6, tts-1, gpt-4o-mini-tts, speech-02-turbo, speech-2.8-turbo,
# s1, s2-pro, s2.1-pro, inworld-tts-2, inworld-tts-2-flash

RETELL_VOICE_MAP: Dict[str, Dict[str, str]] = {
    "arjun": {"voice_id": "eleven_turbo_v2_5", "voice_model": "eleven_turbo_v2_5"},
    "kavya": {"voice_id": "eleven_multilingual_v2", "voice_model": "eleven_multilingual_v2"},
    "ishita": {"voice_id": "eleven_v3", "voice_model": "eleven_v3"},
    "priya": {"voice_id": "sonic-3.5", "voice_model": "sonic-3.5"},
}

DEFAULT_RETELL_VOICE = {"voice_id": "eleven_turbo_v2_5", "voice_model": "eleven_turbo_v2_5"}

# Interview action types - platform neutral, not Retell-specific
class InterviewActionType(str, Enum):
    ASK_QUESTION = "ASK_QUESTION"
    FOLLOW_UP = "FOLLOW_UP"
    CLARIFY = "CLARIFY"
    RETRY = "RETRY"
    END_INTERVIEW = "END_INTERVIEW"
    WAIT = "WAIT"


@dataclass(frozen=True)
class InterviewAction:
    """Platform-neutral interview action from EDI5 intelligence layer.
    
    This is what EDI5 decides. Retell only delivers it via voice.
    """
    action_type: InterviewActionType
    question_id: Optional[str] = None
    question_text: Optional[str] = None
    topic: Optional[str] = None
    difficulty: Optional[str] = None
    reason: Optional[str] = None
    followup_type: Optional[str] = None  # SHORT, PARTIAL, IRRELEVANT, NEGATIVE
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RetellCallConfig:
    """Configuration for creating a Retell web call."""
    agent_id: str
    agent_override: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    dynamic_variables: Optional[Dict[str, str]] = None
    # For custom LLM integration
    llm_websocket_url: Optional[str] = None


@dataclass(frozen=True)
class RetellWebCallResponse:
    """Response from creating a web call."""
    call_id: str
    access_token: str
    transport: str
    ice_servers: List[Dict[str, Any]]
    expires_at: int


@dataclass(frozen=True)
class RetellTranscriptEvent:
    """Incoming transcript event from Retell WebSocket."""
    call_id: str
    interaction_type: str  # update_only, response_required, reminder_required
    transcript: List[Dict[str, Any]]
    transcript_with_tool_calls: Optional[List[Dict[str, Any]]] = None
    turntaking: Optional[str] = None  # agent_turn, user_turn
    response_id: Optional[int] = None
    timestamp: Optional[int] = None


class RetellAPIError(Exception):
    """Retell API error with status code."""
    def __init__(self, message: str, status_code: int = 500, response_body: Any = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_body = response_body


class RetellAdapter:
    """
    Retell integration adapter.
    
    Handles:
    - Web call creation
    - Agent override for interviewer profiles
    - Webhook verification and handling
    - Custom LLM WebSocket message formatting
    
    Does NOT handle:
    - Interview decision logic (that's InterviewOrchestrator)
    - Answer classification (that's AnswerUnderstanding)
    - Question selection (that's QuestionPlanner)
    - RL state (that's InterviewRLEngine)
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.RETELL_API_KEY
        if not self.api_key:
            raise ValueError("RETELL_API_KEY not configured")
        
        self._client = httpx.AsyncClient(
            base_url=RETELL_API_BASE,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()

    # ── Web Call Creation ────────────────────────────────────────────────

    async def create_web_call(self, config: RetellCallConfig) -> RetellWebCallResponse:
        """
        Create a new Retell web call for real-time voice interview.
        
        Maps EDI5 interviewer profile to Retell voice configuration.
        """
        payload: Dict[str, Any] = {
            "agent_id": config.agent_id,
        }
        
        if config.agent_override:
            payload["agent_override"] = config.agent_override
        
        if config.metadata:
            payload["metadata"] = config.metadata
        
        if config.dynamic_variables:
            payload["retell_llm_dynamic_variables"] = config.dynamic_variables
        
        # If using custom LLM, override response engine
        if config.llm_websocket_url:
            if "agent_override" not in payload:
                payload["agent_override"] = {}
            payload["agent_override"]["response_engine"] = {
                "type": "custom-llm",
                "llm_websocket_url": config.llm_websocket_url,
            }
        
        logger.info(f"Creating Retell web call for agent {config.agent_id}")
        
        try:
            response = await self._client.post(f"/{RETELL_API_VERSION}/create-web-call", json=payload)
            response.raise_for_status()
            data = response.json()
            
            return RetellWebCallResponse(
                call_id=data["call_id"],
                access_token=data["access_token"],
                transport=data["transport"],
                ice_servers=data["ice_servers"],
                expires_at=data["expires_at"],
            )
        except httpx.HTTPStatusError as e:
            raise RetellAPIError(
                f"Retell web call creation failed: {e.response.text}",
                status_code=e.response.status_code,
                response_body=e.response.json() if e.response.content else None,
            )
        except Exception as e:
            raise RetellAPIError(f"Retell web call creation failed: {str(e)}")

    # ── Interviewer Profile → Retell Voice Mapping ────────────────────────

    def build_agent_override_for_interviewer(
        self,
        interviewer_id: Optional[str],
        interview_type: str = "technical",
        custom_begin_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Build Retell agent_override from EDI5 InterviewerProfile.
        
        NOTE: For web calls, only `retell_llm` can be overridden.
        Voice settings (`agent`) are fixed on the Agent in the Retell dashboard.
        """
        profile = interviewer_profiles.get_interviewer(interviewer_id)
        
        # Begin message from interviewer greeting
        begin_message = custom_begin_message or profile.render_greeting()
        
        # Only include begin_message; model is defined on the Agent's LLM, not here.
        # For edi5_core (custom-llm): response_engine=custom-llm ignores retell_llm entirely.
        # For retell_hosted: Agent already has a Retell LLM attached.
        return {
            "retell_llm": {
                "model_temperature": 0.3,
                "start_speaker": "agent",
                "begin_message": begin_message,
            }
        }

    def build_dynamic_variables(
        self,
        candidate_name: str,
        interview_type: str,
        interviewer_id: Optional[str],
        edi5_session_id: int,
        questions: Optional[List[str]] = None,
        detected_role: Optional[str] = None,
        total_turns: int = 10,
    ) -> Dict[str, str]:
        """Build dynamic variables injected into Retell agent prompt.
        
        Variable names MUST match the {{variable}} placeholders configured
        in the Retell agent's LLM prompt on the dashboard.
        """
        profile = interviewer_profiles.get_interviewer(interviewer_id)
        
        # Estimate interview duration: ~2 mins per question
        estimated_mins = max(5, total_turns * 2)
        
        # Build numbered question list for the {{questions}} variable
        question_list = ""
        if questions:
            question_list = "\n".join(
                f"{i}. {q}" for i, q in enumerate(questions, start=1)
            )
        
        # Build interview objective from type and detected role
        objective = f"{interview_type.replace('_', ' ').title()} interview"
        if detected_role:
            objective += f" for {detected_role}"
        
        return {
            # Variables expected by the Retell agent prompt template
            "name": candidate_name,
            "mins": str(estimated_mins),
            "objective": objective,
            "questions": question_list,
            # Additional context variables (available if agent prompt uses them)
            "candidate_name": candidate_name,
            "interview_type": interview_type,
            "interviewer_name": profile.name,
            "interviewer_title": profile.title,
            "edi5_session_id": str(edi5_session_id),
        }

    # ── Custom LLM WebSocket Message Builders ─────────────────────────────
    # These format EDI5 decisions into Retell WebSocket protocol

    def build_config_event(
        self,
        auto_reconnect: bool = True,
        call_details: bool = True,
        transcript_with_tool_calls: bool = False,
    ) -> Dict[str, Any]:
        """Build initial config event for Custom LLM WebSocket."""
        return {
            "response_type": "config",
            "config": {
                "auto_reconnect": auto_reconnect,
                "call_details": call_details,
                "transcript_with_tool_calls": transcript_with_tool_calls,
            },
        }

    def build_response_event(
        self,
        response_id: int,
        content: str,
        content_complete: bool,
        end_call: bool = False,
        no_interruption_allowed: bool = False,
    ) -> Dict[str, Any]:
        """Build response event for Custom LLM WebSocket.
        
        Used to stream EDI5's decided response back to Retell for TTS.
        """
        return {
            "response_type": "response",
            "response_id": response_id,
            "content": content,
            "content_complete": content_complete,
            "end_call": end_call,
            "no_interruption_allowed": no_interruption_allowed,
        }

    def build_agent_interrupt_event(
        self,
        interrupt_id: int,
        content: str,
        content_complete: bool,
        end_call: bool = False,
        no_interruption_allowed: bool = True,
    ) -> Dict[str, Any]:
        """Build agent interrupt event for immediate interruption."""
        return {
            "response_type": "agent_interrupt",
            "interrupt_id": interrupt_id,
            "content": content,
            "content_complete": content_complete,
            "end_call": end_call,
            "no_interruption_allowed": no_interruption_allowed,
        }

    def build_update_agent_event(
        self,
        responsiveness: Optional[float] = None,
        interruption_sensitivity: Optional[float] = None,
        reminder_trigger_ms: Optional[int] = None,
        reminder_max_count: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Build agent update event to modify behavior mid-call."""
        agent_config = {}
        if responsiveness is not None:
            agent_config["responsiveness"] = responsiveness
        if interruption_sensitivity is not None:
            agent_config["interruption_sensitivity"] = interruption_sensitivity
        if reminder_trigger_ms is not None:
            agent_config["reminder_trigger_ms"] = reminder_trigger_ms
        if reminder_max_count is not None:
            agent_config["reminder_max_count"] = reminder_max_count
        
        return {
            "response_type": "update_agent",
            "agent_config": agent_config,
        }

    def build_metadata_event(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Build metadata event to forward to frontend."""
        return {
            "response_type": "metadata",
            "metadata": metadata,
        }

    def build_ping_pong_event(self) -> Dict[str, Any]:
        """Build ping-pong event for keepalive."""
        return {
            "response_type": "ping_pong",
            "timestamp": int(time.time() * 1000),
        }

    # ── Webhook Verification ──────────────────────────────────────────────

    @staticmethod
    def verify_webhook_signature(raw_body: str, signature: str) -> bool:
        """Verify Retell webhook signature using Retell SDK logic.
        
        Note: In production, use `retell.verify()` from retell-sdk.
        This is a placeholder - install retell-sdk for proper verification.
        """
        try:
            from retell import Retell
            retell_client = Retell(api_key=settings.RETELL_API_KEY)
            return retell_client.verify(raw_body, api_key=settings.RETELL_API_KEY, signature=signature)
        except ImportError:
            logger.warning("retell-sdk not installed, skipping webhook signature verification")
            return True  # Allow in dev, but require in prod
        except Exception as e:
            logger.error(f"Webhook signature verification failed: {e}")
            return False

    # ── Webhook Event Parsing ─────────────────────────────────────────────

    @staticmethod
    def parse_webhook_event(raw_body: str) -> Dict[str, Any]:
        """Parse and validate webhook event payload."""
        try:
            data = json.loads(raw_body)
            event_type = data.get("event")
            call_data = data.get("call", {})
            
            if not event_type or not call_data:
                raise ValueError("Invalid webhook payload: missing event or call")
            
            return {
                "event_type": event_type,
                "call_id": call_data.get("call_id"),
                "call_data": call_data,
                "raw": data,
            }
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in webhook: {e}")
        except Exception as e:
            raise ValueError(f"Failed to parse webhook: {e}")

    # ── Interview Action → Retell Response Mapping ────────────────────────

    def format_action_for_retell(
        self,
        action: InterviewAction,
        response_id: int,
    ) -> List[Dict[str, Any]]:
        """
        Convert EDI5 InterviewAction to Retell response events.
        
        This is where EDI5's platform-neutral action becomes Retell-specific
        streaming response. EDI5 decides WHAT; this formats HOW for Retell.
        """
        events = []
        
        if action.action_type == InterviewActionType.ASK_QUESTION:
            # New question from QuestionPlanner
            question_text = action.question_text or ""
            events.append(self.build_response_event(
                response_id=response_id,
                content=question_text,
                content_complete=True,
                no_interruption_allowed=False,
            ))
        
        elif action.action_type == InterviewActionType.FOLLOW_UP:
            # Follow-up question
            followup_text = action.question_text or "Could you elaborate on that?"
            events.append(self.build_response_event(
                response_id=response_id,
                content=followup_text,
                content_complete=True,
                no_interruption_allowed=False,
            ))
        
        elif action.action_type == InterviewActionType.CLARIFY:
            # Clarification request
            clarify_text = action.question_text or "I want to make sure I understand. Could you clarify?"
            events.append(self.build_response_event(
                response_id=response_id,
                content=clarify_text,
                content_complete=True,
                no_interruption_allowed=False,
            ))
        
        elif action.action_type == InterviewActionType.RETRY:
            # Silence retry
            retry_text = "I didn't catch that. Could you please repeat your answer?"
            events.append(self.build_response_event(
                response_id=response_id,
                content=retry_text,
                content_complete=True,
                no_interruption_allowed=False,
            ))
        
        elif action.action_type == InterviewActionType.END_INTERVIEW:
            # Interview complete
            end_text = action.question_text or "Thank you for your time today. Best of luck!"
            events.append(self.build_response_event(
                response_id=response_id,
                content=end_text,
                content_complete=True,
                end_call=True,
                no_interruption_allowed=True,
            ))
        
        elif action.action_type == InterviewActionType.WAIT:
            # No immediate response needed
            pass
        
        return events


# ── Singleton Instance (initialized by app lifespan) ───────────────────────

_retell_adapter: Optional[RetellAdapter] = None


def get_retell_adapter() -> RetellAdapter:
    """Get or create the global RetellAdapter instance."""
    global _retell_adapter
    if _retell_adapter is None:
        _retell_adapter = RetellAdapter()
    return _retell_adapter


async def init_retell_adapter():
    """Initialize Retell adapter on app startup."""
    global _retell_adapter
    _retell_adapter = RetellAdapter()
    logger.info("Retell adapter initialized")


async def close_retell_adapter():
    """Close Retell adapter on app shutdown."""
    global _retell_adapter
    if _retell_adapter:
        await _retell_adapter.close()
        _retell_adapter = None
        logger.info("Retell adapter closed")