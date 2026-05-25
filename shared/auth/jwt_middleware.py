"""
JWT token validation middleware — imported by every service.
"""
import jwt
from datetime import datetime, timedelta
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRY_HOURS

security = HTTPBearer(auto_error=False)


def create_token(user_id: str, role: str = "recruiter") -> str:
    """Create a JWT token for a user."""
    payload = {
        "sub": user_id,
        "role": role,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """FastAPI dependency to extract the current user from JWT.
    Returns a dev user if no token is provided (for testing).
    """
    if credentials is None:
        # Dev mode: return a default test user
        return {"sub": "dev-user", "role": "admin"}
    return decode_token(credentials.credentials)
