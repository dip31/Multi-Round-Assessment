"""
Reset password for kumar08@gmail.com
"""
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from app.database.db import SessionLocal
from app.models.user import User
from app.models.assessment import AssessmentSession, AssessmentRound
from app.config.security import hash_password

def reset_password():
    db = SessionLocal()
    try:
        email = "kumar08@gmail.com"
        password = "kumar123"
        
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            print(f"✗ User {email} not found")
            print("\nCreating user...")
            user = User(
                email=email,
                name="Kumar",
                password_hash=hash_password(password),
                role="candidate"
            )
            db.add(user)
            db.commit()
            print(f"✓ User created: {email}")
        else:
            print(f"✓ User found: {email}")
            print(f"  ID: {user.id}")
            print(f"  Name: {user.name}")
            print(f"  Role: {user.role}")
            
            # Update password
            user.password_hash = hash_password(password)
            db.commit()
            print(f"\n✓ Password reset to: {password}")
        
        print(f"\nLogin credentials:")
        print(f"  Email: {email}")
        print(f"  Password: {password}")
        
    except Exception as e:
        db.rollback()
        print(f"✗ Error: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    reset_password()
