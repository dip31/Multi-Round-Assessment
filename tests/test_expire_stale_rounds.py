#!/usr/bin/env python
"""Test if _expire_stale_rounds() function works correctly."""

import sys
sys.path.insert(0, '.')

from app.database.db import get_db
from app.services.session_service import _expire_stale_rounds, get_active_round
from datetime import datetime

print("=" * 80)
print("TESTING _expire_stale_rounds() FUNCTION")
print("=" * 80)

db = next(get_db())

# Check for expired rounds that are still active
from app.models.assessment import AssessmentRound
expired_active = db.query(AssessmentRound).filter(
    AssessmentRound.status == "active",
    AssessmentRound.expires_at.isnot(None),
    AssessmentRound.expires_at <= datetime.utcnow()
).all()

print(f"\n[1] Expired rounds still marked as 'active': {len(expired_active)}")
for r in expired_active:
    print(f"  Round {r.id}: {r.round_type} (session {r.session_id})")
    print(f"    Expired at: {r.expires_at}")
    print(f"    Current time: {datetime.utcnow()}")

if expired_active:
    print(f"\n[2] Testing _expire_stale_rounds() on session {expired_active[0].session_id}")
    session_id = expired_active[0].session_id
    
    print(f"  Before: Round {expired_active[0].id} status = {expired_active[0].status}")
    
    # Call the function
    _expire_stale_rounds(db, session_id)
    
    # Check if it worked
    db.refresh(expired_active[0])
    print(f"  After:  Round {expired_active[0].id} status = {expired_active[0].status}")
    
    if expired_active[0].status == "expired":
        print("  ✓ Function works correctly!")
    else:
        print("  ✗ Function did NOT expire the round!")
        print("\n  Checking why...")
        
        # Debug the SQL filter
        print(f"  Round details:")
        print(f"    status: {expired_active[0].status}")
        print(f"    expires_at: {expired_active[0].expires_at}")
        print(f"    expires_at IS NOT NULL: {expired_active[0].expires_at is not None}")
        print(f"    expires_at <= NOW: {expired_active[0].expires_at <= datetime.utcnow()}")
else:
    print("\n✓ No expired 'active' rounds found - database is clean!")
    print("  Creating a test round to verify the function works...")
    
    # Create a test round that's already expired
    from app.models.assessment import AssessmentSession
    from datetime import timedelta
    
    # Find or create a test session
    test_session = db.query(AssessmentSession).filter(
        AssessmentSession.user_id == 21,
        AssessmentSession.status == "in_progress"
    ).first()
    
    if test_session:
        print(f"\n  Using session {test_session.id} for testing")
        
        # Create an expired test round
        now = datetime.utcnow()
        expired_time = now - timedelta(minutes=10)
        
        test_round = AssessmentRound(
            session_id=test_session.id,
            round_type="aptitude",
            status="active",
            started_at=expired_time,
            expires_at=expired_time + timedelta(minutes=5)  # Already expired
        )
        db.add(test_round)
        db.commit()
        db.refresh(test_round)
        
        print(f"  Created test round {test_round.id} (expired 5 minutes ago)")
        print(f"  Status before: {test_round.status}")
        
        # Test the function
        _expire_stale_rounds(db, test_session.id)
        db.refresh(test_round)
        
        print(f"  Status after: {test_round.status}")
        
        if test_round.status == "expired":
            print("  ✓ Function works correctly!")
        else:
            print("  ✗ Function did NOT work!")
        
        # Clean up
        db.delete(test_round)
        db.commit()
        print("  Test round deleted")
    else:
        print("  ✗ No test session available")

print("\n" + "=" * 80)
