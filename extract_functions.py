import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import subprocess
import os

# Connect to postgres database to create test database
conn = psycopg2.connect('postgresql://postgres:Firstiqoo%402023@localhost/postgres')
conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
cur = conn.cursor()

# Drop and create test database
cur.execute("DROP DATABASE IF EXISTS backup_restore")
cur.execute("CREATE DATABASE backup_restore")
print("Created test database: backup_restore")
conn.close()

# Restore backup
print("Restoring backup...")
result = subprocess.run(
    ['pg_restore', '-d', 'postgresql://postgres:Firstiqoo%402023@localhost/backup_restore', 'EDI5_phase0_baseline_2026-09-16.dump'],
    capture_output=True,
    text=True
)
print("STDOUT:", result.stdout)
print("STDERR:", result.stderr)
print(f"Return code: {result.returncode}")

# Extract functions
conn = psycopg2.connect('postgresql://postgres:Firstiqoo%402023@localhost/backup_restore')
cur = conn.cursor()

# Get function definitions
cur.execute("""
    SELECT p.proname, pg_get_functiondef(p.oid) as definition
    FROM pg_proc p
    JOIN pg_namespace n ON p.pronamespace = n.oid
    WHERE n.nspname = 'public'
    AND p.prokind = 'f'
    ORDER BY p.proname
""")
functions = cur.fetchall()
print(f"\nFound {len(functions)} functions:")
for name, defn in functions:
    print(f"\n--- {name} ---")
    print(defn)

# Get triggers
cur.execute("""
    SELECT t.tgname, pg_get_triggerdef(t.oid) as definition
    FROM pg_trigger t
    JOIN pg_class c ON t.tgrelid = c.oid
    JOIN pg_namespace n ON c.relnamespace = n.oid
    WHERE n.nspname = 'public'
    AND NOT t.tgisinternal
    ORDER BY c.relname, t.tgname
""")
triggers = cur.fetchall()
print(f"\nFound {len(triggers)} triggers:")
for name, defn in triggers:
    print(f"\n--- {name} ---")
    print(defn)

conn.close()

# Cleanup
conn = psycopg2.connect('postgresql://postgres:Firstiqoo%402023@localhost/postgres')
conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
cur = conn.cursor()
cur.execute("DROP DATABASE backup_restore")
print("\nCleaned up test database")
conn.close()