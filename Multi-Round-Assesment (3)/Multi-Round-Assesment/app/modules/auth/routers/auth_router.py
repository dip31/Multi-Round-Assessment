"""
Authentication endpoints.

Handles user registration, login (JWT issuance), and token refresh.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config.security import create_access_token, decode_access_token
from app.core.auth import get_current_user
from app.database.db import get_db
from app.models.user import User
from app.schemas.user import TokenResponse, UserCreate, UserLogin, UserResponse
from app.services.auth_service import create_user, get_user_by_email, verify_user_credentials

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> UserResponse:
    """Create a new user account.

    Raises:
        HTTPException (409): If the email is already registered.
    """
    existing = get_user_by_email(db, payload.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = create_user(db, name=payload.name, email=payload.email, password=payload.password)
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in and receive a JWT access token",
)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> TokenResponse:
    """Verify credentials and return a signed JWT.

    Raises:
        HTTPException (401): If credentials are invalid.
    """
    user = verify_user_credentials(db, email=payload.email, password=payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    access_token = create_access_token(data={"sub": str(user.id), "is_admin": user.role == "admin"})
    return TokenResponse(access_token=access_token)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh an access token",
)
def refresh(token: str, db: Session = Depends(get_db)) -> TokenResponse:
    """Decode an existing (valid) access token and issue a fresh one.

    This is a lightweight refresh mechanism. For production, consider
    opaque refresh tokens stored in the ``refresh_tokens`` table.

    Raises:
        HTTPException (401): If the token is invalid or expired.
    """
    payload = decode_access_token(token)
    if payload is None or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    new_token = create_access_token(data={"sub": payload["sub"], "is_admin": payload.get("is_admin", False)})
    return TokenResponse(access_token=new_token)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get the currently authenticated user",
)
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Return profile details for the user represented by the JWT bearer token."""
    return current_user
