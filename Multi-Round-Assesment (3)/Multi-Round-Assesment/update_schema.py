"""
Direct database schema update for proctoring_events table.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.database.db import get_db
from sqlalchemy import text


def update_proctoring_schema():
    """Update the proctoring_events table schema."""
    
    print("🔄 Updating proctoring_events table schema...")
    
    # Create database session
    db = next(get_db())
    
    try:
        # Drop existing table if it exists
        print("🗑️  Dropping existing proctoring_events table...")
        db.execute(text("DROP TABLE IF EXISTS proctoring_events CASCADE"))
        
        # Create new table with correct schema
        print("📝 Creating new proctoring_events table...")
        db.execute(text("""
            CREATE TABLE proctoring_events (
                id SERIAL PRIMARY KEY,
                session_id INTEGER NOT NULL,
                event_type VARCHAR(50) NOT NULL,
                event_metadata JSONB,
                created_at TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (session_id)
                    REFERENCES assessment_sessions(id) ON DELETE CASCADE
            )
        """))
        
        # Create index
        print("📊 Creating index...")
        db.execute(text("""
            CREATE INDEX idx_proctoring_session
            ON proctoring_events(session_id)
        """))
        
        # Commit changes
        db.commit()
        print("✅ Schema updated successfully!")
        
        # Verify table exists
        result = db.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'proctoring_events'
            );
        """)).scalar()
        
        if result:
            print("✅ proctoring_events table verified")
        else:
            print("❌ Table verification failed")
            
    except Exception as e:
        print(f"❌ Error updating schema: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    update_proctoring_schema()
