"""Check interview tables structure and data."""

from app.database.db import engine
from sqlalchemy import text, inspect

def check_tables():
    conn = engine.connect()
    inspector = inspect(engine)
    
    print("=" * 70)
    print("INTERVIEW TABLES CHECK")
    print("=" * 70)
    
    # Check interview_sessions table
    print("\n1. Checking interview_sessions table...")
    if 'interview_sessions' in inspector.get_table_names():
        print("   ✓ Table exists")
        
        # Get columns
        columns = inspector.get_columns('interview_sessions')
        print("\n   Columns:")
        for col in columns:
            nullable = "NULL" if col['nullable'] else "NOT NULL"
            default = f" DEFAULT {col['default']}" if col['default'] else ""
            print(f"     - {col['name']}: {col['type']} {nullable}{default}")
        
        # Check foreign keys
        fks = inspector.get_foreign_keys('interview_sessions')
        if fks:
            print("\n   Foreign Keys:")
            for fk in fks:
                print(f"     - {fk['constrained_columns']} -> {fk['referred_table']}.{fk['referred_columns']}")
    else:
        print("   ✗ Table does NOT exist")
    
    # Check approved_question_pools table
    print("\n2. Checking approved_question_pools table...")
    if 'approved_question_pools' in inspector.get_table_names():
        print("   ✓ Table exists")
        
        # Count records
        result = conn.execute(text("SELECT COUNT(*) FROM approved_question_pools"))
        count = result.fetchone()[0]
        print(f"   Records: {count}")
        
        if count > 0:
            # Show recent records
            result = conn.execute(text("""
                SELECT id, session_id, admin_approved, created_at 
                FROM approved_question_pools 
                ORDER BY id DESC LIMIT 5
            """))
            print("\n   Recent records:")
            for row in result:
                print(f"     - ID: {row[0]}, Session: {row[1]}, Approved: {row[2]}, Created: {row[3]}")
    else:
        print("   ✗ Table does NOT exist")
    
    # Check assessment_sessions table
    print("\n3. Checking assessment_sessions table...")
    if 'assessment_sessions' in inspector.get_table_names():
        print("   ✓ Table exists")
        
        # Count records
        result = conn.execute(text("SELECT COUNT(*) FROM assessment_sessions"))
        count = result.fetchone()[0]
        print(f"   Records: {count}")
        
        if count > 0:
            # Show recent records
            result = conn.execute(text("""
                SELECT id, user_id, status, created_at 
                FROM assessment_sessions 
                ORDER BY id DESC LIMIT 5
            """))
            print("\n   Recent records:")
            for row in result:
                print(f"     - ID: {row[0]}, User: {row[1]}, Status: {row[2]}, Created: {row[3]}")
    else:
        print("   ✗ Table does NOT exist")
    
    # Check interview_sessions records
    print("\n4. Checking interview_sessions records...")
    if 'interview_sessions' in inspector.get_table_names():
        result = conn.execute(text("SELECT COUNT(*) FROM interview_sessions"))
        count = result.fetchone()[0]
        print(f"   Records: {count}")
        
        if count > 0:
            result = conn.execute(text("""
                SELECT id, session_id, phase, current_turn, created_at 
                FROM interview_sessions 
                ORDER BY id DESC LIMIT 5
            """))
            print("\n   Recent records:")
            for row in result:
                print(f"     - ID: {row[0]}, Session: {row[1]}, Phase: {row[2]}, Turn: {row[3]}, Created: {row[4]}")
    
    conn.close()
    print("\n" + "=" * 70)

if __name__ == "__main__":
    check_tables()
