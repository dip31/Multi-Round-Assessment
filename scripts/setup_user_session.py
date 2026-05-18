"""
Quick setup script to:
1. Seed problem bank
2. Create/verify test user
3. Create assessment session with coding round

Run this before testing the frontend.
"""
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from app.database.db import SessionLocal
from app.models.user import User
from app.models.assessment import AssessmentSession, AssessmentRound
from app.models.coding import CodingProblem
from app.config.security import hash_password
from datetime import datetime

def setup():
    db = SessionLocal()
    try:
        # 1. Check if problems exist
        problem_count = db.query(CodingProblem).count()
        print(f"✓ Found {problem_count} problems in database")
        
        if problem_count == 0:
            print("⚠ No problems found! Run: python -m scripts.seed_problem_bank")
            return
        
        # 2. Find or create test user
        email = "kumar08@gmail.com"
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            user = User(
                email=email,
                full_name="Kumar Test User",
                hashed_password=hash_password("kumar123"),
                role="candidate"
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"✓ Created user: {email} / kumar123")
        else:
            print(f"✓ User exists: {email}")
        
        # 3. Check for active session
        active_session = db.query(AssessmentSession).filter(
            AssessmentSession.user_id == user.id,
            AssessmentSession.status == "in_progress"
        ).first()
        
        if active_session:
            print(f"✓ Active session exists (ID: {active_session.id})")
            
            # Check for coding round
            coding_round = db.query(AssessmentRound).filter(
                AssessmentRound.session_id == active_session.id,
                AssessmentRound.round_type == "coding"
            ).first()
            
            if coding_round:
                print(f"✓ Coding round exists (ID: {coding_round.id}, Status: {coding_round.status})")
            else:
                # Create coding round for existing session
                coding_round = AssessmentRound(
                    session_id=active_session.id,
                    round_type="coding",
                    status="pending"
                )
                db.add(coding_round)
                db.commit()
                print(f"✓ Created coding round (ID: {coding_round.id})")
        else:
            # Create new session with coding round
            new_session = AssessmentSession(
                user_id=user.id,
                status="in_progress",
                started_at=datetime.utcnow()
            )
            db.add(new_session)
            db.flush()
            
            # Create coding round
            coding_round = AssessmentRound(
                session_id=new_session.id,
                round_type="coding",
                status="pending"
            )
            db.add(coding_round)
            db.commit()
            
            print(f"✓ Created new session (ID: {new_session.id})")
            print(f"✓ Created coding round (ID: {coding_round.id})")
        
        print("\n" + "="*60)
        print("SETUP COMPLETE!")
        print("="*60)
        print(f"\nLogin credentials:")
        print(f"  Email: {email}")
        print(f"  Password: kumar123")
        print(f"\nYou can now:")
        print(f"  1. Login at http://localhost:3001")
        print(f"  2. Start the coding round")
        
    except Exception as e:
        db.rollback()
        print(f"\n✗ Error: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    setup()
