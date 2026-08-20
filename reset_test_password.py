"""
Reset test user password to fix hash issue.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.database.db import get_db
from app.models.user import User
from app.config.security import hash_password


def reset_test_user_password():
    """Reset the test user's password with a proper hash."""
    
    print("🔧 Resetting test user password...")
    
    db = next(get_db())
    
    try:
        # Find the test user
        test_user = db.query(User).filter(User.email == "test@example.com").first()
        
        if not test_user:
            print("❌ Test user not found")
            return
        
        # Reset password with proper hash
        test_user.password_hash = hash_password("testpass")
        db.commit()
        
        print(f"✅ Reset password for user: {test_user.id}")
        print("✅ Password hash updated successfully")
        
    except Exception as e:
        print(f"❌ Failed to reset password: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    reset_test_user_password()
