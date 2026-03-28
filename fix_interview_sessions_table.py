"""
Fix the interview_sessions table structure.

The table has the wrong columns. We need to drop and recreate it.
"""

from app.database.db import engine
from sqlalchemy import text

def fix_table():
    conn = engine.connect()
    trans = conn.begin()
    
    try:
        print("Fixing interview_sessions table...")
        
        # Drop the old table
        print("1. Dropping old interview_sessions table...")
        conn.execute(text("DROP TABLE IF EXISTS interview_sessions CASCADE"))
        print("   ✓ Dropped")
        
        # Create the correct table structure
        print("2. Creating new interview_sessions table...")
        conn.execute(text("""
            CREATE TABLE interview_sessions (
                id SERIAL PRIMARY KEY,
                session_id INTEGER NOT NULL REFERENCES assessment_sessions(id) ON DELETE CASCADE,
                phase VARCHAR(20) NOT NULL DEFAULT 'HR',
                current_turn INTEGER NOT NULL DEFAULT 0,
                total_turns INTEGER NOT NULL DEFAULT 10,
                rl_state JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        print("   ✓ Created")
        
        # Create indexes
        print("3. Creating indexes...")
        conn.execute(text("""
            CREATE INDEX idx_interview_session 
            ON interview_sessions(session_id)
        """))
        print("   ✓ Index created")
        
        # Recreate interview_turns table (it depends on interview_sessions)
        print("4. Recreating interview_turns table...")
        conn.execute(text("DROP TABLE IF EXISTS interview_turns CASCADE"))
        conn.execute(text("""
            CREATE TABLE interview_turns (
                id SERIAL PRIMARY KEY,
                interview_id INTEGER NOT NULL REFERENCES interview_sessions(id) ON DELETE CASCADE,
                turn_number INTEGER NOT NULL,
                question_text TEXT NOT NULL,
                question_difficulty VARCHAR(10),
                candidate_response TEXT,
                response_time_sec FLOAT,
                content_score FLOAT,
                behavioral_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
                rl_reward FLOAT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        print("   ✓ interview_turns created")
        
        # Create indexes for interview_turns
        print("5. Creating interview_turns indexes...")
        conn.execute(text("""
            CREATE INDEX idx_interview_turns_interview 
            ON interview_turns(interview_id)
        """))
        conn.execute(text("""
            CREATE INDEX idx_interview_turns_turn 
            ON interview_turns(interview_id, turn_number)
        """))
        print("   ✓ Indexes created")
        
        trans.commit()
        print("\n✓ All tables fixed successfully!")
        print("\nNew interview_sessions structure:")
        print("  - id (PRIMARY KEY)")
        print("  - session_id (FK to assessment_sessions)")
        print("  - phase (VARCHAR)")
        print("  - current_turn (INTEGER)")
        print("  - total_turns (INTEGER)")
        print("  - rl_state (JSONB)")
        print("  - created_at (TIMESTAMP)")
        
    except Exception as e:
        trans.rollback()
        print(f"\n✗ Error: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    fix_table()
