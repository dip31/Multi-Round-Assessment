"""
Role-based access control rules.
Defines who can access what across the system.
"""
from enum import Enum
from fastapi import HTTPException


class Role(str, Enum):
    ADMIN = "admin"
    RECRUITER = "recruiter"
    HIRING_MANAGER = "hiring_manager"
    VIEWER = "viewer"


# Permission matrix: role -> set of allowed actions
PERMISSIONS = {
    Role.ADMIN: {
        "jobs:create", "jobs:read", "jobs:update", "jobs:delete",
        "candidates:read", "candidates:update",
        "postings:create", "postings:read",
        "resumes:upload", "resumes:parse",
        "scrape:profiles",
        "audit:read",
    },
    Role.RECRUITER: {
        "jobs:create", "jobs:read", "jobs:update",
        "candidates:read", "candidates:update",
        "postings:create", "postings:read",
        "resumes:upload", "resumes:parse",
        "scrape:profiles",
    },
    Role.HIRING_MANAGER: {
        "jobs:create", "jobs:read",
        "candidates:read",
        "postings:read",
    },
    Role.VIEWER: {
        "jobs:read",
        "candidates:read",
        "postings:read",
    },
}


def check_permission(user: dict, action: str):
    """Raise 403 if user's role doesn't permit the action."""
    role = user.get("role", "viewer")
    try:
        role_enum = Role(role)
    except ValueError:
        role_enum = Role.VIEWER

    if action not in PERMISSIONS.get(role_enum, set()):
        raise HTTPException(
            status_code=403,
            detail=f"Role '{role}' is not permitted to perform '{action}'",
        )
