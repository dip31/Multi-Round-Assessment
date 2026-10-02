"""
Interviewer Management Service for EDI5.

Handles creation and management of dynamic interviewers with Retell integration.
Creates Retell LLM and Agent resources, manages their lifecycle.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.config.settings import settings
from app.models.interview import DynamicInterviewer
from app.models.user import User

logger = logging.getLogger(__name__)

RETELL_VOICE_IDS = frozenset({"retell-Cimo", "retell-Jessica"})


def build_retell_agent_create_args(
    *,
    llm_id: str,
    name: str,
    voice_id: str,
    voice_model: Optional[str],
) -> Dict[str, Any]:
    """Build valid Retell agent arguments, omitting unset optional values."""
    args: Dict[str, Any] = {
        "response_engine": {
            "type": "retell-llm",
            "llm_id": llm_id,
            "version": 0,
        },
        "voice_id": voice_id,
        "agent_name": name,
    }
    if voice_model and voice_model.strip():
        args["voice_model"] = voice_model.strip()
    return args


# Try to import Retell SDK
try:
    from retell import Retell
    RETELL_SDK_AVAILABLE = True
except ImportError:
    Retell = None
    RETELL_SDK_AVAILABLE = False
    logger.warning("retell-sdk not installed. Interviewer creation will not work.")


@dataclass
class InterviewerCreateRequest:
    """Request to create a new dynamic interviewer."""
    name: str
    title: str
    tagline: str
    description: Optional[str] = None
    personality: str = ""
    speaking_style: str = ""
    greeting: str = ""
    avatar_initials: str = ""
    accent: str = "indigo"
    avatar_url: Optional[str] = None
    voice_id: str = "retell-Cimo"
    voice_model: Optional[str] = None
    language_code: str = "en-US"
    pace: float = 0.95


@dataclass
class InterviewerUpdateRequest:
    """Request to update an existing dynamic interviewer."""
    name: Optional[str] = None
    title: Optional[str] = None
    tagline: Optional[str] = None
    description: Optional[str] = None
    personality: Optional[str] = None
    speaking_style: Optional[str] = None
    greeting: Optional[str] = None
    avatar_initials: Optional[str] = None
    accent: Optional[str] = None
    avatar_url: Optional[str] = None
    voice_id: Optional[str] = None
    voice_model: Optional[str] = None
    language_code: Optional[str] = None
    pace: Optional[float] = None
    is_active: Optional[bool] = None


@dataclass
class InterviewerCreationResult:
    """Result of interviewer creation."""
    interviewer: DynamicInterviewer
    retell_llm_id: str
    retell_agent_id: str


class InterviewerServiceError(Exception):
    """Custom exception for interviewer service errors."""
    def __init__(self, message: str, retell_error: bool = False):
        super().__init__(message)
        self.message = message
        self.retell_error = retell_error


class InterviewerService:
    """
    Service for managing dynamic interviewers with Retell integration.
    
    Handles:
    - Creating Retell LLM and Agent
    - Storing interviewer in database
    - Updating interviewer (with Retell resource updates)
    - Deactivating interviewers
    - Listing interviewers
    """
    
    def __init__(self, db: Session):
        self.db = db
        self._retell_client: Optional[Any] = None
        
    def _get_retell_client(self):
        """Get or create Retell client."""
        if not RETELL_SDK_AVAILABLE:
            raise InterviewerServiceError(
                "retell-sdk not installed. Cannot create interviewer.",
                retell_error=True
            )
        
        if not settings.RETELL_API_KEY:
            raise InterviewerServiceError(
                "RETELL_API_KEY not configured in settings.",
                retell_error=True
            )
            
        if self._retell_client is None:
            self._retell_client = Retell(api_key=settings.RETELL_API_KEY)
            
        return self._retell_client
    
    def _generate_slug(self, name: str) -> str:
        """Generate a unique slug from name."""
        base_slug = name.lower().replace(" ", "-").replace(".", "").replace("'", "")
        # Remove non-alphanumeric except hyphens
        import re
        base_slug = re.sub(r'[^a-z0-9-]', '', base_slug)
        
        # Check if slug exists and append number if needed
        slug = base_slug
        counter = 1
        while self.db.execute(
            select(DynamicInterviewer).where(DynamicInterviewer.slug == slug)
        ).scalar_one_or_none():
            counter += 1
            slug = f"{base_slug}-{counter}"
            
        return slug
    
    def _build_llm_prompt(self, interviewer: DynamicInterviewer) -> str:
        """Build the Retell LLM general prompt from interviewer configuration."""
        
        # Build personality traits from personality field
        traits = [t.strip() for t in interviewer.personality.split(",") if t.strip()]
        trait_lines = "\n".join(f"- {t}" for t in traits)
        
        speaking_style = interviewer.speaking_style or "Natural and conversational"
        
        prompt = f"""You are {interviewer.name}, {interviewer.title}.

{interviewer.tagline}

Your personality:
{trait_lines}

Your speaking style:
{speaking_style}

You are a professional interviewer conducting a campus placement interview for an engineering student.

CRITICAL RULES - These are inviolable:
- You NEVER lecture or explain the answer
- You NEVER repeat what the candidate just said back to them
- You NEVER ask two questions in one response
- Maximum 2 sentences in your response
- Sound human, not like a bot reading a script

You receive interview actions from the EDI5 interview engine. The engine decides:
- What question to ask
- Whether to follow up
- When the interview ends
- Candidate scoring

Your job is ONLY to deliver the interviewer's response naturally with your personality.
The EDI5 engine will provide you with:
- The current question or follow-up
- The candidate's answer
- The action to take (ASK_QUESTION, FOLLOW_UP, CLARIFY, END_INTERVIEW, etc.)
- The next question (if applicable)

Deliver the response in your voice and style. Do not add assessment logic or change the question intent.
"""
        return prompt.strip()
    
    def _build_agent_override(self, interviewer: DynamicInterviewer, interview_type: str = "technical") -> Dict[str, Any]:
        """Build Retell agent_override from dynamic interviewer."""
        
        agent_config = {
            "voice_id": interviewer.voice_id,
            "voice_model": interviewer.voice_model,
            "voice_speed": interviewer.pace,
            "language": interviewer.language_code,
            "enable_expressive_mode": True,
            "expressive_emotion_tags": ["empathetic", "curious", "pause", "emphasis"],
            "interruption_sensitivity": 0.7,
            "enable_backchannel": True,
            "backchannel_frequency": 0.6,
            "backchannel_words": ["yeah", "uh-huh", "right", "I see"],
            "responsiveness": 0.8,
            "reminder_trigger_ms": 8000,
            "reminder_max_count": 2,
        }
        
        # Interviewer-specific expressive tags based on personality
        personality_lower = interviewer.personality.lower()
        if "professional" in personality_lower:
            agent_config["expressive_emotion_tags"] = ["clear throat", "emphasis", "pause"]
        elif "friendly" in personality_lower or "approachable" in personality_lower:
            agent_config["expressive_emotion_tags"] = ["happy", "excited", "empathetic", "pause"]
        elif "calm" in personality_lower or "measured" in personality_lower:
            agent_config["expressive_emotion_tags"] = ["pause", "long pause", "emphasis"]
        
        # Interview type adjustments
        if interview_type == "hr":
            agent_config["responsiveness"] = 0.7
            agent_config["backchannel_frequency"] = 0.7
        elif interview_type == "communication":
            agent_config["enable_expressive_mode"] = True
            agent_config["expressive_emotion_tags"] = ["excited", "curious", "emphasis", "happy"]
        
        return {
            "agent": agent_config,
        }
    
    async def create_interviewer(
        self,
        request: InterviewerCreateRequest,
        created_by: Optional[User] = None,
    ) -> InterviewerCreationResult:
        """
        Create a new dynamic interviewer with Retell LLM and Agent.
        
        Steps:
        1. Validate request
        2. Generate unique slug
        3. Create Retell LLM with interviewer prompt
        4. Create Retell Agent using the LLM
        5. Save interviewer to database with Retell IDs
        6. Return created interviewer
        
        Implements rollback: if any step fails, attempts cleanup of created Retell resources.
        """
        # Validate required fields
        if not request.name or not request.name.strip():
            raise InterviewerServiceError("Interviewer name is required")
        if not request.title or not request.title.strip():
            raise InterviewerServiceError("Interviewer title is required")
        if not request.tagline or not request.tagline.strip():
            raise InterviewerServiceError("Interviewer tagline is required")
        if not request.personality or not request.personality.strip():
            raise InterviewerServiceError("Interviewer personality is required")
        if not request.speaking_style or not request.speaking_style.strip():
            raise InterviewerServiceError("Interviewer speaking style is required")
        if not request.greeting or not request.greeting.strip():
            raise InterviewerServiceError("Interviewer greeting is required")
        if not request.avatar_initials or not request.avatar_initials.strip():
            raise InterviewerServiceError("Interviewer avatar initials are required")
        if request.voice_id not in RETELL_VOICE_IDS:
            raise InterviewerServiceError(
                "Choose a Retell voice. Sarvam and other provider voice IDs cannot be used to create a Retell interviewer."
            )
        
        client = self._get_retell_client()
        created_llm_id = None
        created_agent_id = None
        current_step = "Retell LLM creation"
        
        try:
            # Step 1: Generate unique slug
            slug = self._generate_slug(request.name)
            
            # Step 2: Create Retell LLM
            llm_prompt = self._build_llm_prompt_for_creation(request)
            
            logger.info(f"Creating Retell LLM for interviewer: {request.name}")
            llm_response = client.llm.create(
                model="gpt-5.6-terra",
                general_prompt=llm_prompt,
                general_tools=[
                    {
                        "type": "end_call",
                        "name": "end_call",
                        "description": "End the interview when the candidate says goodbye or the interview is complete.",
                    },
                ],
            )
            created_llm_id = llm_response.llm_id
            logger.info(f"Created Retell LLM: {created_llm_id}")
            
            # Step 3: Create Retell Agent
            current_step = "Retell agent creation"
            logger.info(f"Creating Retell Agent for interviewer: {request.name}")
            agent_response = client.agent.create(**build_retell_agent_create_args(
                llm_id=created_llm_id,
                name=request.name,
                voice_id=request.voice_id,
                voice_model=request.voice_model,
            ))
            created_agent_id = agent_response.agent_id
            logger.info(f"Created Retell Agent: {created_agent_id}")
            
            # Step 4: Save interviewer to database
            current_step = "database persistence"
            interviewer = DynamicInterviewer(
                slug=slug,
                name=request.name.strip(),
                title=request.title.strip(),
                tagline=request.tagline.strip(),
                description=request.description,
                personality=request.personality.strip(),
                speaking_style=request.speaking_style.strip(),
                greeting=request.greeting.strip(),
                avatar_initials=request.avatar_initials.strip().upper()[:10],
                accent=request.accent,
                avatar_url=request.avatar_url,
                voice_id=request.voice_id,
                voice_model=request.voice_model,
                language_code=request.language_code,
                pace=request.pace,
                retell_llm_id=created_llm_id,
                retell_agent_id=created_agent_id,
                is_active=True,
                created_by=created_by.id if created_by else None,
            )
            
            self.db.add(interviewer)
            self.db.commit()
            self.db.refresh(interviewer)
            
            logger.info(f"Created dynamic interviewer: {interviewer.slug} (LLM: {created_llm_id}, Agent: {created_agent_id})")
            
            return InterviewerCreationResult(
                interviewer=interviewer,
                retell_llm_id=created_llm_id,
                retell_agent_id=created_agent_id,
            )
            
        except Exception as e:
            # Rollback: attempt to clean up created Retell resources
            self.db.rollback()
            logger.exception("Failed to create interviewer during %s", current_step)
            await self._cleanup_retell_resources(client, created_llm_id, created_agent_id)
            if current_step != "database persistence":
                raise InterviewerServiceError(
                    f"{current_step} failed: {e}",
                    retell_error=True,
                ) from e
            raise InterviewerServiceError(
                f"Interviewer database save failed: {e}",
            ) from e
    
    def _build_llm_prompt_for_creation(self, request: InterviewerCreateRequest) -> str:
        """Build LLM prompt for a new interviewer creation request."""
        traits = [t.strip() for t in request.personality.split(",") if t.strip()]
        trait_lines = "\n".join(f"- {t}" for t in traits)
        
        speaking_style = request.speaking_style or "Natural and conversational"
        
        return f"""You are {request.name}, {request.title}.

{request.tagline}

Your personality:
{trait_lines}

Your speaking style:
{speaking_style}

You are a professional interviewer conducting a campus placement interview for an engineering student.

CRITICAL RULES - These are inviolable:
- You NEVER lecture or explain the answer
- You NEVER repeat what the candidate just said back to them
- You NEVER ask two questions in one response
- Maximum 2 sentences in your response
- Sound human, not like a bot reading a script

You receive interview actions from the EDI5 interview engine. The engine decides:
- What question to ask
- Whether to follow up
- When the interview ends
- Candidate scoring

Your job is ONLY to deliver the interviewer's response naturally with your personality.
The EDI5 engine will provide you with:
- The current question or follow-up
- The candidate's answer
- The action to take (ASK_QUESTION, FOLLOW_UP, CLARIFY, END_INTERVIEW, etc.)
- The next question (if applicable)

Deliver the response in your voice and style. Do not add assessment logic or change the question intent.
""".strip()
    
    async def _cleanup_retell_resources(
        self,
        client: Any,
        llm_id: Optional[str],
        agent_id: Optional[str],
    ) -> None:
        """Attempt to clean up Retell resources on failure."""
        if agent_id:
            try:
                client.agent.delete(agent_id)
                logger.info(f"Cleaned up Retell Agent: {agent_id}")
            except Exception as e:
                logger.warning(f"Failed to cleanup Retell Agent {agent_id}: {e}")
        
        if llm_id:
            try:
                client.llm.delete(llm_id)
                logger.info(f"Cleaned up Retell LLM: {llm_id}")
            except Exception as e:
                logger.warning(f"Failed to cleanup Retell LLM {llm_id}: {e}")
    
    async def update_interviewer(
        self,
        interviewer_id: int,
        request: InterviewerUpdateRequest,
    ) -> DynamicInterviewer:
        """Update an existing dynamic interviewer."""
        interviewer = self.db.execute(
            select(DynamicInterviewer).where(DynamicInterviewer.id == interviewer_id)
        ).scalar_one_or_none()
        
        if not interviewer:
            raise InterviewerServiceError("Interviewer not found")
        
        # Track what changed for Retell updates
        voice_changed = False
        personality_changed = False
        
        # Update fields
        if request.name is not None:
            interviewer.name = request.name.strip()
        if request.title is not None:
            interviewer.title = request.title.strip()
        if request.tagline is not None:
            interviewer.tagline = request.tagline.strip()
        if request.description is not None:
            interviewer.description = request.description
        if request.personality is not None:
            interviewer.personality = request.personality.strip()
            personality_changed = True
        if request.speaking_style is not None:
            interviewer.speaking_style = request.speaking_style.strip()
        if request.greeting is not None:
            interviewer.greeting = request.greeting.strip()
        if request.avatar_initials is not None:
            interviewer.avatar_initials = request.avatar_initials.strip().upper()[:10]
        if request.accent is not None:
            interviewer.accent = request.accent
        if request.avatar_url is not None:
            interviewer.avatar_url = request.avatar_url
        if request.voice_id is not None:
            interviewer.voice_id = request.voice_id
            voice_changed = True
        if request.voice_model is not None:
            interviewer.voice_model = request.voice_model
        if request.language_code is not None:
            interviewer.language_code = request.language_code
        if request.pace is not None:
            interviewer.pace = request.pace
            voice_changed = True
        if request.is_active is not None:
            interviewer.is_active = request.is_active
        
        # If voice or personality changed and we have Retell IDs, we might need to update
        # For now, we just update the DB. Full Retell agent update would require
        # creating a new agent version or using agent override at call time.
        
        self.db.commit()
        self.db.refresh(interviewer)
        
        logger.info(f"Updated dynamic interviewer: {interviewer.slug}")
        return interviewer
    
    def deactivate_interviewer(self, interviewer_id: int) -> DynamicInterviewer:
        """Deactivate (soft delete) an interviewer."""
        interviewer = self.db.execute(
            select(DynamicInterviewer).where(DynamicInterviewer.id == interviewer_id)
        ).scalar_one_or_none()
        
        if not interviewer:
            raise InterviewerServiceError("Interviewer not found")
        
        interviewer.is_active = False
        self.db.commit()
        self.db.refresh(interviewer)
        
        logger.info(f"Deactivated dynamic interviewer: {interviewer.slug}")
        return interviewer
    
    def get_interviewer(self, interviewer_id: int) -> Optional[DynamicInterviewer]:
        """Get interviewer by ID."""
        return self.db.execute(
            select(DynamicInterviewer).where(DynamicInterviewer.id == interviewer_id)
        ).scalar_one_or_none()
    
    def get_interviewer_by_slug(self, slug: str) -> Optional[DynamicInterviewer]:
        """Get interviewer by slug."""
        return self.db.execute(
            select(DynamicInterviewer).where(DynamicInterviewer.slug == slug)
        ).scalar_one_or_none()
    
    def list_interviewers(
        self,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> List[DynamicInterviewer]:
        """List dynamic interviewers."""
        query = select(DynamicInterviewer)
        if active_only:
            query = query.where(DynamicInterviewer.is_active == True)
        query = query.order_by(DynamicInterviewer.created_at.desc()).limit(limit).offset(offset)
        return list(self.db.execute(query).scalars().all())
    
    def count_interviewers(self, active_only: bool = True) -> int:
        """Count dynamic interviewers."""
        query = select(func.count(DynamicInterviewer.id))
        if active_only:
            query = query.where(DynamicInterviewer.is_active == True)
        return self.db.execute(query).scalar() or 0


def get_interviewer_service(db: Session) -> InterviewerService:
    """Dependency injection for InterviewerService."""
    return InterviewerService(db)