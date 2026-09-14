"""Authentication endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config.security import create_access_token, decode_access_token
from app.core.auth import get_current_user
from app.database.db import get_db
from app.models.user import User
from app.schemas.user import TokenResponse, UserCreate, UserLogin, UserResponse
from app.services.auth_service import create_user, get_user_by_email, verify_user_credentials

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> UserResponse:
    """Create a user with an explicit application role."""
    if get_user_by_email(db, payload.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    return create_user(
        db,
        name=payload.name,
        email=payload.email,
        password=payload.password,
        role=payload.role,
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> TokenResponse:
    """Verify credentials and return a signed JWT access token."""
    user = verify_user_credentials(db, email=payload.email, password=payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    access_token = create_access_token(data={"sub": str(user.id), "is_admin": user.role == "admin"})
    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=TokenResponse)
def refresh(token: str, db: Session = Depends(get_db)) -> TokenResponse:
    """Issue a fresh token for a valid existing token."""
    payload = decode_access_token(token)
    if payload is None or "sub" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return TokenResponse(
        access_token=create_access_token(data={"sub": str(user.id), "is_admin": user.role == "admin"})
    )


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Return the authenticated user's profile."""
    return current_user
