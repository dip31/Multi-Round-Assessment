"""
Script to create or promote an admin user.

Usage:
    python create_admin.py

This script will:
1. Check if admin@assessai.com exists
2. If exists: promote to admin role
3. If not: create new admin user with default credentials

Default credentials:
    Email: admin@assessai.com
    Password: admin123

To manually promote existing user via psql:
    UPDATE users SET role = 'admin' WHERE email = 'your@email.com';
"""

import sys
import os

# Add the project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database.db import SessionLocal
from app.models.user import User
from app.config.security import hash_password


def create_admin():
    """Create or promote an admin user."""
    db = SessionLocal()
    try:
        existing = db.query(User).filter(
            User.email == "admin@assessai.com"
        ).first()

        if existing:
            existing.role = "admin"
            db.commit()
            print(f"[OK] Updated {existing.email} to admin role")
        else:
            admin = User(
                email="admin@assessai.com",
                password_hash=hash_password("admin123"),
                name="Admin User",
                role="admin",
                is_active=True,
                is_verified=True
            )
            db.add(admin)
            db.commit()
            print("[OK] Admin created: admin@assessai.com / admin123")
            print("     WARNING: Change this password in production!")
    except Exception as e:
        db.rollback()
        print(f"[ERROR] {e}")
        raise
    finally:
        db.close()


def promote_user(email: str):
    """Promote an existing user to admin by email."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            print(f"[ERROR] User not found: {email}")
            return False

        user.role = "admin"
        db.commit()
        print(f"[OK] Promoted {email} to admin role")
        return True
    except Exception as e:
        db.rollback()
        print(f"[ERROR] {e}")
        return False
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Promote specific user
        email = sys.argv[1]
        promote_user(email)
    else:
        # Create default admin
        create_admin()
