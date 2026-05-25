"""Test if interview session can be created."""

from app.database.db import engine
from sqlalchemy import text

def test_interview_start():
    conn = engine.connect()
    trans = conn.begin()
    
    try:
        print("Testing interview session creation...")
        
        # Check if we have an approved question pool
        result = conn.execute(text("""
            SELECT id, session_id, admin_approved 
            FROM approved_question_pools 
            WHERE admin_approved = true 
            ORDER BY id DESC LIMIT 1
        """))
        pool = result.fetchone()
        
        if not pool:
            print("✗ No approved question pool found")
            print("  Please upload a resume first")
            return False
        
        print(f"✓ Found approved pool: ID={pool[0]}, Session={pool[1]}")
        
        # Try to create an interview session
        print("\nTrying to create interview session...")
        result = conn.execute(text("""
            INSERT INTO interview_sessions (session_id, phase, current_turn, total_turns, rl_state)
            VALUES (:session_id, 'HR', 0, 10, '{}'::jsonb)
            RETURNING id, session_id, phase
        """), {"session_id": pool[1]})
        
        interview = result.fetchone()
        print(f"✓ Interview session created: ID={interview[0]}, Session={interview[1]}, Phase={interview[2]}")
        
        trans.rollback()  # Don't actually save it
        print("\n✓ Test successful! Interview can be created.")
        print("\nNow try uploading a resume and clicking 'Start Interview' again!")
        return True
        
    except Exception as e:
        trans.rollback()
        print(f"\n✗ Error: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    test_interview_start()
