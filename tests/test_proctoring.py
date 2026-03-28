"""
Simple test script to verify proctoring system functionality.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.database.db import get_db
from app.models.proctoring import ProctoringEvent
from app.models.assessment import AssessmentSession
from app.models.user import User
from app.services.proctoring_service import log_proctoring_event, get_session_proctoring_events
from sqlalchemy import text


async def test_proctoring_system():
    """Test the proctoring system components."""
    
    print("🧪 Testing Proctoring System...")
    
    # Create database session
    db = next(get_db())
    
    try:
        # Check if tables exist
        print("\n📋 Checking database tables...")
        
        # Check proctoring_events table
        proctoring_table_exists = db.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'proctoring_events'
            );
        """)).scalar()
        
        if proctoring_table_exists:
            print("✅ proctoring_events table exists")
        else:
            print("❌ proctoring_events table missing")
            
        # Check relationships
        print("\n🔗 Testing relationships...")
        
        # Create a test user and session
        import random
        random_id = random.randint(1000, 9999)
        
        test_user = User(
            name=f"Test User {random_id}",
            email=f"test{random_id}@example.com",
            password_hash="test_hash",
            role="student"
        )
        db.add(test_user)
        db.flush()
        
        test_session = AssessmentSession(
            user_id=test_user.id,
            status="in_progress"
        )
        db.add(test_session)
        db.flush()
        
        print(f"✅ Created test session: {test_session.id}")
        
        # Test logging events
        print("\n📝 Testing event logging...")
        
        event_types = [
            "camera_permission_denied",
            "tab_switch", 
            "fullscreen_exit",
            "page_reload",
            "idle_activity"
        ]
        
        for event_type in event_types:
            event = log_proctoring_event(
                db=db,
                session_id=test_session.id,
                event_type=event_type,
                event_metadata={"test": True}
            )
            print(f"✅ Logged {event_type}: {event.id}")
        
        # Test retrieving events
        print("\n📖 Testing event retrieval...")
        
        events = get_session_proctoring_events(db, test_session.id)
        print(f"✅ Retrieved {len(events)} events")
        
        for event in events:
            print(f"   - {event.event_type} at {event.created_at}")
        
        # Cleanup
        db.rollback()
        print("\n🧹 Test completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(test_proctoring_system())
