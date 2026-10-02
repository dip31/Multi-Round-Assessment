"""
Interviewer Management API Endpoints.

Provides CRUD operations for dynamic interviewers with Retell integration.
Admin-only access for creation/modification.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.core.auth import get_current_user
from app.database.db import get_db
from app.models.user import User
from app.models.interview import DynamicInterviewer
from app.modules.interview.config import interviewer_profiles
from app.modules.interview.services.interviewer_service import (
    InterviewerService,
    InterviewerCreateRequest,
    InterviewerUpdateRequest,
    InterviewerServiceError,
    get_interviewer_service,
)
from app.modules.interview.schemas.interview_schema import (
    InterviewerProfileResponse,
    InterviewerVoiceInfo,
    InterviewerListResponse,
)

router = APIRouter(
    prefix="/interviewers",
    tags=["Interviewer Management"],
)


# ── Request/Response Schemas ──────────────────────────────────────────────

class CreateInterviewerRequest(BaseModel):
    """Request to create a new dynamic interviewer."""
    name: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=200)
    tagline: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    personality: str = Field(..., min_length=1)
    speaking_style: str = Field(..., min_length=1)
    greeting: str = Field(..., min_length=1)
    avatar_initials: str = Field(..., min_length=1, max_length=10)
    accent: str = Field(default="indigo", max_length=20)
    avatar_url: Optional[str] = None
    voice_id: Literal["retell-Cimo", "retell-Jessica"] = "retell-Cimo"
    voice_model: Optional[str] = None
    language_code: str = Field(default="en-US", max_length=10)
    pace: float = Field(default=0.95, ge=0.5, le=2.0)


class UpdateInterviewerRequest(BaseModel):
    """Request to update an existing dynamic interviewer."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    tagline: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    personality: Optional[str] = None
    speaking_style: Optional[str] = None
    greeting: Optional[str] = None
    avatar_initials: Optional[str] = Field(None, min_length=1, max_length=10)
    accent: Optional[str] = Field(None, max_length=20)
    avatar_url: Optional[str] = None
    voice_id: Optional[Literal["retell-Cimo", "retell-Jessica"]] = None
    voice_model: Optional[str] = None
    language_code: Optional[str] = Field(None, max_length=10)
    pace: Optional[float] = Field(None, ge=0.5, le=2.0)
    is_active: Optional[bool] = None


class InterviewerDetailResponse(BaseModel):
    """Detailed interviewer response for management UI."""
    id: int
    slug: str
    name: str
    title: str
    tagline: str
    description: Optional[str]
    personality: str
    speaking_style: str
    greeting: str
    avatar_initials: str
    accent: str
    avatar_url: Optional[str]
    voice_id: str
    voice_model: Optional[str]
    voice_provider: str
    language_code: str
    pace: float
    retell_llm_id: Optional[str]
    retell_agent_id: Optional[str]
    is_active: bool
    created_by: Optional[int]
    created_at: Optional[str]
    updated_at: Optional[str]
    
    # Computed field for UI
    is_dynamic: bool = True


class InterviewerListItemResponse(BaseModel):
    """Interviewer item for list view."""
    id: int
    slug: str
    name: str
    title: str
    tagline: str
    avatar_initials: str
    accent: str
    voice_id: str
    is_active: bool
    is_dynamic: bool = True


class VoiceOptionResponse(BaseModel):
    """Available voice option for interviewer creation."""
    voice_id: str
    name: str
    provider: str
    description: str


class CreateInterviewerResponse(BaseModel):
    """Response after creating interviewer."""
    interviewer: InterviewerDetailResponse
    retell_llm_id: str
    retell_agent_id: str
    message: str = "Interviewer created successfully"


# ── Helper Functions ──────────────────────────────────────────────────────

def _require_admin(current_user: User) -> None:
    """Check if user has admin permission."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required for interviewer management"
        )


def _dynamic_to_detail(di: DynamicInterviewer) -> InterviewerDetailResponse:
    """Convert DynamicInterviewer to detail response."""
    return InterviewerDetailResponse(
        id=di.id,
        slug=di.slug,
        name=di.name,
        title=di.title,
        tagline=di.tagline,
        description=di.description,
        personality=di.personality,
        speaking_style=di.speaking_style,
        greeting=di.greeting,
        avatar_initials=di.avatar_initials,
        accent=di.accent,
        avatar_url=di.avatar_url,
        voice_id=di.voice_id,
        voice_model=di.voice_model,
        voice_provider=di.voice_provider,
        language_code=di.language_code,
        pace=di.pace,
        retell_llm_id=di.retell_llm_id,
        retell_agent_id=di.retell_agent_id,
        is_active=di.is_active,
        created_by=di.created_by,
        created_at=di.created_at.isoformat() if di.created_at else None,
        updated_at=di.updated_at.isoformat() if di.updated_at else None,
    )


def _dynamic_to_list_item(di: DynamicInterviewer) -> InterviewerListItemResponse:
    """Convert DynamicInterviewer to list item response."""
    return InterviewerListItemResponse(
        id=di.id,
        slug=di.slug,
        name=di.name,
        title=di.title,
        tagline=di.tagline,
        avatar_initials=di.avatar_initials,
        accent=di.accent,
        voice_id=di.voice_id,
        is_active=di.is_active,
    )


def _profile_to_list_item(p: InterviewerProfile) -> InterviewerListItemResponse:
    """Convert static InterviewerProfile to list item response."""
    return InterviewerListItemResponse(
        id=0,  # Static profiles don't have DB IDs
        slug=p.id,
        name=p.name,
        title=p.title,
        tagline=p.tagline,
        avatar_initials=p.avatar_initials,
        accent=p.accent,
        voice_id=p.voice.speaker,
        is_active=True,
        is_dynamic=False,
    )


# ── Endpoints ──────────────────────────────────────────────────────────────

# GET /interview/interviewers/voices - Get available voices
@router.get("/voices", response_model=List[VoiceOptionResponse])
async def get_available_voices(
    current_user: User = Depends(get_current_user),
):
    """Get the Retell voices supported for dynamic interviewer creation."""
    voices = [
        VoiceOptionResponse(
            voice_id="retell-Cimo",
            name="Cimo (Retell)",
            provider="retell",
            description="Professional male voice"
        ),
        VoiceOptionResponse(
            voice_id="retell-Jessica",
            name="Jessica (Retell)",
            provider="retell",
            description="Professional female voice"
        ),
    ]
    return voices


# GET /interview/interviewers/manage - List dynamic interviewers for admin management
@router.get("/manage", response_model=List[InterviewerDetailResponse])
async def list_interviewers_for_management(
    active_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = InterviewerService(db)
    """List dynamic interviewers for admin management UI."""
    _require_admin(current_user)
    
    interviewers = service.list_interviewers(active_only=active_only, limit=limit, offset=offset)
    return [_dynamic_to_detail(di) for di in interviewers]


# GET /interview/interviewers/manage/{interviewer_id} - Get interviewer detail
@router.get("/manage/{interviewer_id}", response_model=InterviewerDetailResponse)
async def get_interviewer_detail(
    interviewer_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = InterviewerService(db)
    """Get detailed interviewer information for admin management."""
    _require_admin(current_user)
    
    interviewer = service.get_interviewer(interviewer_id)
    if not interviewer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interviewer not found"
        )
    
    return _dynamic_to_detail(interviewer)


# POST /interview/interviewers - Create new dynamic interviewer
@router.post("", response_model=CreateInterviewerResponse, status_code=status.HTTP_201_CREATED)
async def create_interviewer(
    request: CreateInterviewerRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = InterviewerService(db)
    """
    Create a new dynamic interviewer with Retell LLM and Agent.
    
    This endpoint:
    1. Validates the request
    2. Creates a Retell LLM with the interviewer's personality prompt
    3. Creates a Retell Agent using that LLM
    4. Saves the interviewer to the database with Retell IDs
    5. Returns the created interviewer
    
    Requires admin role.
    """
    _require_admin(current_user)
    
    # Convert to service request
    svc_request = InterviewerCreateRequest(
        name=request.name,
        title=request.title,
        tagline=request.tagline,
        description=request.description,
        personality=request.personality,
        speaking_style=request.speaking_style,
        greeting=request.greeting,
        avatar_initials=request.avatar_initials,
        accent=request.accent,
        avatar_url=request.avatar_url,
        voice_id=request.voice_id,
        voice_model=request.voice_model,
        language_code=request.language_code,
        pace=request.pace,
    )
    
    try:
        result = await service.create_interviewer(svc_request, created_by=current_user)
        return CreateInterviewerResponse(
            interviewer=_dynamic_to_detail(result.interviewer),
            retell_llm_id=result.retell_llm_id,
            retell_agent_id=result.retell_agent_id,
        )
    except InterviewerServiceError as e:
        if e.retell_error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Retell service error: {e.message}"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message
        )


# PATCH /interview/interviewers/manage/{interviewer_id} - Update interviewer
@router.patch("/manage/{interviewer_id}", response_model=InterviewerDetailResponse)
async def update_interviewer(
    interviewer_id: int,
    request: UpdateInterviewerRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = InterviewerService(db)
    """Update an existing dynamic interviewer."""
    _require_admin(current_user)
    
    svc_request = InterviewerUpdateRequest(
        name=request.name,
        title=request.title,
        tagline=request.tagline,
        description=request.description,
        personality=request.personality,
        speaking_style=request.speaking_style,
        greeting=request.greeting,
        avatar_initials=request.avatar_initials,
        accent=request.accent,
        avatar_url=request.avatar_url,
        voice_id=request.voice_id,
        voice_model=request.voice_model,
        language_code=request.language_code,
        pace=request.pace,
        is_active=request.is_active,
    )
    
    try:
        interviewer = await service.update_interviewer(interviewer_id, svc_request)
        return _dynamic_to_detail(interviewer)
    except InterviewerServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message
        )


# DELETE /interview/interviewers/manage/{interviewer_id} - Deactivate interviewer
@router.delete("/manage/{interviewer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_interviewer(
    interviewer_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = InterviewerService(db)
    """Deactivate (soft delete) a dynamic interviewer."""
    _require_admin(current_user)
    
    try:
        service.deactivate_interviewer(interviewer_id)
    except InterviewerServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message
        )


# POST /interview/interviewers/preview-voice - Preview interviewer voice
@router.post("/preview-voice")
async def preview_voice(
    voice_id: str = Query(...),
    text: str = Query(default="Hello, this is a preview of my voice."),
    current_user: User = Depends(get_current_user),
):
    """Preview a voice using the existing TTS service."""
    if voice_id not in {"shubh", "kavya", "ishita", "priya"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only Sarvam voices can be previewed here. Retell voices are played during a configured Retell interview.",
        )

    from app.services.sarvam_service import text_to_speech
    from fastapi.responses import Response
    
    try:
        audio_bytes = await text_to_speech(
            text,
            speaker=voice_id,
            model="bulbul:v3",
            language_code="en-IN",
            pace=0.95,
        )
        return Response(
            content=audio_bytes,
            media_type="audio/wav",
            headers={"Cache-Control": "public, max-age=3600"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Voice preview failed: {str(e)}"
        )