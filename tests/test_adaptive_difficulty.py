"""
Test script to verify adaptive difficulty is working.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.database.db import get_db
from app.modules.aptitude.services.aptitude_service import (
    get_current_difficulty,
    get_next_question,
    submit_answer_and_adapt,
)
from app.models.user import User
from app.models.assessment import AssessmentSession
from app.models.aptitude import RLSession


async def test_adaptive_difficulty():
    """Test that difficulty changes after submitting answers."""
    
    print("🧪 Testing Adaptive Difficulty System...")
    
    # Create database session
    db = next(get_db())
    
    try:
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
        
        # Test 1: First question should be medium difficulty
        print("\n📝 Test 1: First question (should be medium)")
        current_difficulty = get_current_difficulty(db, test_session.id, test_user.id)
        print(f"   Current difficulty from RL: {current_difficulty}")
        
        question1 = get_next_question(db, difficulty="medium")
        print(f"   Question difficulty: {question1['difficulty']}")
        
        # Simulate answering correctly (should increase difficulty)
        print("\n📝 Test 2: Submit correct answer (should increase difficulty)")
        result = submit_answer_and_adapt(
            db=db,
            user_id=test_user.id,
            session_id=test_session.id,
            round_id=1,  # This would be created by session start
            question_id=1,
            selected_option="A",
            response_time=15.0,
        )
        print(f"   Submitted answer: A")
        print(f"   Was correct: {result['correct']}")
        print(f"   Next difficulty: {result['next_difficulty']}")
        
        # Test 3: Check if current difficulty updated
        print("\n📝 Test 3: Next question (should be harder)")
        current_difficulty_2 = get_current_difficulty(db, test_session.id, test_user.id)
        print(f"   Current difficulty from RL: {current_difficulty_2}")
        
        question2 = get_next_question(db, difficulty=result['next_difficulty'])
        print(f"   Question difficulty: {question2['difficulty']}")
        
        # Test 4: Simulate answering incorrectly (should decrease difficulty)
        print("\n📝 Test 4: Submit wrong answer (should decrease difficulty)")
        result2 = submit_answer_and_adapt(
            db=db,
            user_id=test_user.id,
            session_id=test_session.id,
            round_id=1,
            question_id=2,
            selected_option="B",
            response_time=20.0,
        )
        print(f"   Submitted answer: B")
        print(f"   Was correct: {result2['correct']}")
        print(f"   Next difficulty: {result2['next_difficulty']}")
        
        print("\n✅ Adaptive difficulty test completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    asyncio.run(test_adaptive_difficulty())
