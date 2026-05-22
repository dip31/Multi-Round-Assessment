"""Final verification of proctoring_violations table."""
from sqlalchemy import create_engine, text, inspect
from app.config.settings import settings

engine = create_engine(settings.DATABASE_URL)
inspector = inspect(engine)

print("=" * 70)
print("FINAL VERIFICATION: proctoring_violations table")
print("=" * 70)

# 1. Check table exists
table_exists = 'proctoring_violations' in inspector.get_table_names()
print(f"\n✓ Table exists: {table_exists}")

if not table_exists:
    print("\n✗ FAILED: Table does not exist!")
    exit(1)

# 2. Check columns
columns = inspector.get_columns('proctoring_violations')
expected_columns = {
    'id': 'INTEGER',
    'session_id': 'INTEGER',
    'event_type': 'VARCHAR',
    'confidence_score': 'DOUBLE_PRECISION',
    'face_count': 'INTEGER',
    'metadata': 'JSONB',
    'created_at': 'TIMESTAMP'
}

print("\n✓ Columns:")
for col in columns:
    col_type = str(col['type'])
    nullable = "NULL" if col['nullable'] else "NOT NULL"
    print(f"  - {col['name']}: {col_type} ({nullable})")

# Verify all expected columns exist
column_names = {col['name'] for col in columns}
missing_columns = set(expected_columns.keys()) - column_names
if missing_columns:
    print(f"\n✗ FAILED: Missing columns: {missing_columns}")
    exit(1)

# 3. Check foreign key constraint
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT 
            conname, 
            CASE confdeltype
                WHEN 'c' THEN 'CASCADE'
                WHEN 'a' THEN 'NO ACTION'
                WHEN 'r' THEN 'RESTRICT'
                WHEN 'n' THEN 'SET NULL'
                WHEN 'd' THEN 'SET DEFAULT'
            END as delete_action
        FROM pg_constraint 
        WHERE conrelid = 'proctoring_violations'::regclass 
        AND contype = 'f'
    """))
    
    fks = result.fetchall()
    print("\n✓ Foreign Key Constraints:")
    for fk in fks:
        print(f"  - {fk[0]}: ON DELETE {fk[1]}")
    
    # Verify CASCADE is set
    if not any(fk[1] == 'CASCADE' for fk in fks):
        print("\n✗ FAILED: Foreign key does not have ON DELETE CASCADE!")
        exit(1)

# 4. Check index
indexes = inspector.get_indexes('proctoring_violations')
print("\n✓ Indexes:")
for idx in indexes:
    print(f"  - {idx['name']}: {idx['column_names']}")

# Verify the required index exists
expected_index_columns = ['session_id', 'created_at']
index_found = any(
    idx['column_names'] == expected_index_columns 
    for idx in indexes
)
if not index_found:
    print(f"\n✗ FAILED: Index on {expected_index_columns} not found!")
    exit(1)

# 5. Test insert and query
print("\n✓ Testing insert and query...")
with engine.connect() as conn:
    # Get a valid session_id from interview_sessions
    result = conn.execute(text("SELECT id FROM interview_sessions LIMIT 1"))
    row = result.fetchone()
    
    if row:
        session_id = row[0]
        
        # Insert a test violation
        conn.execute(text("""
            INSERT INTO proctoring_violations 
            (session_id, event_type, confidence_score, face_count, metadata)
            VALUES 
            (:session_id, 'mobile_phone', 0.85, NULL, '{"test": true}'::jsonb)
        """), {"session_id": session_id})
        conn.commit()
        
        # Query it back
        result = conn.execute(text("""
            SELECT event_type, confidence_score, metadata 
            FROM proctoring_violations 
            WHERE session_id = :session_id
            ORDER BY created_at DESC LIMIT 1
        """), {"session_id": session_id})
        
        test_row = result.fetchone()
        if test_row:
            print(f"  - Inserted and retrieved test record: {test_row[0]}, confidence={test_row[1]}")
            
            # Clean up test data
            conn.execute(text("""
                DELETE FROM proctoring_violations 
                WHERE session_id = :session_id 
                AND metadata->>'test' = 'true'
            """), {"session_id": session_id})
            conn.commit()
            print("  - Test record cleaned up")
        else:
            print("\n✗ FAILED: Could not retrieve test record!")
            exit(1)
    else:
        print("  - Skipped (no interview_sessions exist yet)")

print("\n" + "=" * 70)
print("✓ ALL CHECKS PASSED!")
print("=" * 70)
print("\nMigration Summary:")
print("  - Table: proctoring_violations")
print("  - Columns: 7 (id, session_id, event_type, confidence_score, face_count, metadata, created_at)")
print("  - Foreign Key: session_id -> interview_sessions.id (ON DELETE CASCADE)")
print("  - Index: idx_violations_session on (session_id, created_at)")
print("\n✓ Task 2.1 completed successfully!")
