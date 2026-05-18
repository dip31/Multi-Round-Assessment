"""
Authentication dependency for FastAPI routes.

Provides ``get_current_user`` which decodes the JWT from the
``Authorization: Bearer <token>`` header and returns the authenticated
``User`` ORM instance.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.config.security import decode_access_token
from app.database.db import get_db
from app.models.user import User
from app.services.auth_service import get_user_by_id

# Use HTTPBearer for simple Bearer token authentication in Swagger
security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Decode the JWT bearer token and return the corresponding user.

    Raises:
        HTTPException (401): If the token is invalid, expired, or the
            user does not exist.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Extract token from credentials
    token = credentials.credentials

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    user_id: int | None = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    user = get_user_by_id(db, user_id=int(user_id))
    if user is None:
        raise credentials_exception

    return user
