"""
Pydantic schemas for proctoring events API.

Defines request/response models for proctoring event logging.
"""

from typing import Optional

from pydantic import BaseModel, Field


class ProctorEventRequest(BaseModel):
    """Request schema for logging a proctoring event."""
    
    session_id: int = Field(..., description="ID of the assessment session")
    event_type: str = Field(..., description="Type of proctoring event")
    event_metadata: Optional[dict] = Field(None, description="Additional event data")


class ProctorEventResponse(BaseModel):
    """Response schema for successful event logging."""
    
    status: str = Field("logged", description="Event logging status")
    event_id: Optional[int] = Field(None, description="ID of the logged event")
