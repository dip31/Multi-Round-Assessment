"""
Pydantic schemas for user-related request / response payloads.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# ── Request schemas ───────────────────────────────────────────────────

class UserCreate(BaseModel):
    """Payload for user registration."""

    name: str = Field(..., min_length=1, max_length=100, examples=["Alice Smith"])
    email: EmailStr = Field(..., examples=["alice@example.com"])
    password: str = Field(..., min_length=8, max_length=128)


class UserLogin(BaseModel):
    """Payload for user login."""

    email: EmailStr = Field(..., examples=["alice@example.com"])
    password: str = Field(...)


# ── Response schemas ──────────────────────────────────────────────────

class UserResponse(BaseModel):
    """Public representation of a user returned by the API."""

    id: int
    name: str
    email: str
    role: str
    is_active: bool
    is_verified: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """Payload returned after successful authentication."""

    access_token: str
    token_type: str = "bearer"
