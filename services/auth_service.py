"""
Business logic for user authentication and management.

All database operations related to user accounts are centralised here so
that routers remain thin.
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.config.security import hash_password, verify_password
from shared.db.user import User


def create_user(db: Session, name: str, email: str, password: str) -> User:
    """Register a new user with a hashed password.

    Args:
        db: Active database session.
        name: Display name.
        email: Unique email address.
        password: Plain-text password (will be hashed before storage).

    Returns:
        The newly created ``User`` instance (already committed).
    """
    # Truncate password to 72 bytes for bcrypt compatibility
    if len(password.encode('utf-8')) > 72:
        password = password.encode('utf-8')[:72].decode('utf-8', errors='ignore')
    
    user = User(
        name=name,
        email=email,
        password_hash=hash_password(password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Look up a user by their email address.

    Returns:
        The ``User`` if found, otherwise ``None``.
    """
    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Look up a user by primary key.

    Returns:
        The ``User`` if found, otherwise ``None``.
    """
    return db.query(User).filter(User.id == user_id).first()


def verify_user_credentials(db: Session, email: str, password: str) -> Optional[User]:
    """Authenticate a user by email and password.

    Args:
        db: Active database session.
        email: User email.
        password: Plain-text password to verify.

    Returns:
        The ``User`` if credentials are valid, otherwise ``None``.
    """
    # Truncate password to 72 bytes for bcrypt compatibility
    if len(password.encode('utf-8')) > 72:
        password = password.encode('utf-8')[:72].decode('utf-8', errors='ignore')
    
    user = get_user_by_email(db, email)
    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user

