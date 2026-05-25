"""
Create test user for adaptive difficulty testing.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.database.db import get_db
from app.models.user import User
from app.config.security import hash_password


async def create_test_user():
    """Create a test user for API testing."""
    
    print("Creating test user...")
    
    db = next(get_db())
    
    try:
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == "test@example.com").first()
        if existing_user:
            print("Test user already exists")
            return
        
        # Create new test user
        test_user = User(
            name="Test User",
            email="test@example.com",
            password_hash=hash_password("testpass"),
            role="student"
        )
        
        db.add(test_user)
        db.commit()
        print(f"Created test user: {test_user.id}")
        
    except Exception as e:
        print(f"Failed to create test user: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(create_test_user())
