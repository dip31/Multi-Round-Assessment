"""
Manually create the approved_question_pools and interview_turns tables if they don't exist.
"""

from app.database.db import engine
from sqlalchemy import text

def create_tables():
    conn = engine.connect()
    trans = conn.begin()
    
    try:
        # Create approved_question_pools table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS approved_question_pools (
                id SERIAL PRIMARY KEY,
                session_id INTEGER NOT NULL REFERENCES assessment_sessions(id) ON DELETE CASCADE,
                extracted_skills JSONB NOT NULL DEFAULT '[]'::jsonb,
                extracted_projects JSONB NOT NULL DEFAULT '{}'::jsonb,
                question_pool JSONB NOT NULL,
                admin_approved BOOLEAN NOT NULL DEFAULT false,
                approved_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
                approved_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        print("✓ Created approved_question_pools table")
        
        # Create indexes
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_approved_pool_session 
            ON approved_question_pools(session_id)
        """))
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_approved_pool_approved 
            ON approved_question_pools(admin_approved)
        """))
        print("✓ Created indexes for approved_question_pools")
        
        # Create interview_turns table if it doesn't exist
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS interview_turns (
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
        print("✓ Created interview_turns table")
        
        # Create indexes
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_interview_turns_interview 
            ON interview_turns(interview_id)
        """))
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_interview_turns_turn 
            ON interview_turns(interview_id, turn_number)
        """))
        print("✓ Created indexes for interview_turns")
        
        trans.commit()
        print("\n✓ All tables created successfully!")
        
    except Exception as e:
        trans.rollback()
        print(f"✗ Error: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    create_tables()
