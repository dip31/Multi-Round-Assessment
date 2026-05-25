"""
Temporary authentication bypass for interview system.
Provides mock login/register endpoints that return a dummy token.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["Authentication (Bypass)"])


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


@router.post("/register", response_model=AuthResponse)
async def register(req: RegisterRequest):
    """Mock registration endpoint - always succeeds."""
    return AuthResponse(
        access_token="dummy_token_12345",
        user={
            "id": 1,
            "name": req.name,
            "email": req.email,
        }
    )


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest):
    """Mock login endpoint - always succeeds."""
    return AuthResponse(
        access_token="dummy_token_12345",
        user={
            "id": 1,
            "name": "Test User",
            "email": req.email,
        }
    )
