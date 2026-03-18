"""
Debug the next-question endpoint issue.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.database.db import get_db
from app.models.user import User
from app.models.assessment import AssessmentSession, AssessmentRound
from app.modules.aptitude.services.aptitude_service import get_current_difficulty, get_next_question


def debug_next_question():
    """Debug the next question endpoint."""
    
    print("🔍 Debugging next-question endpoint...")
    
    db = next(get_db())
    
    try:
        # Find the test user
        test_user = db.query(User).filter(User.email == "test@example.com").first()
        if not test_user:
            print("❌ Test user not found")
            return
        
        print(f"✅ Found test user: {test_user.id}")
        
        # Find the latest session
        latest_session = db.query(AssessmentSession)\
            .filter(AssessmentSession.user_id == test_user.id)\
            .order_by(AssessmentSession.id.desc())\
            .first()
        
        if not latest_session:
            print("❌ No session found")
            return
        
        print(f"✅ Found session: {latest_session.id}")
        
        # Find the latest round
        latest_round = db.query(AssessmentRound)\
            .filter(AssessmentRound.session_id == latest_session.id)\
            .order_by(AssessmentRound.id.desc())\
            .first()
        
        if not latest_round:
            print("❌ No round found")
            return
        
        print(f"✅ Found round: {latest_round.id}")
        
        # Test get_current_difficulty
        try:
            current_difficulty = get_current_difficulty(db, latest_round.id, test_user.id)
            print(f"✅ Current difficulty: {current_difficulty}")
        except Exception as e:
            print(f"❌ get_current_difficulty failed: {e}")
            return
        
        # Test get_next_question
        try:
            question = get_next_question(db, difficulty=current_difficulty)
            if question:
                print(f"✅ Question found: {question['difficulty']}")
            else:
                print("❌ No question found")
        except Exception as e:
            print(f"❌ get_next_question failed: {e}")
        
    except Exception as e:
        print(f"❌ Debug failed: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    debug_next_question()
