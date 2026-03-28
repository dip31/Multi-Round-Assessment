from app.database.db import engine
from sqlalchemy import text

conn = engine.connect()
result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name='approved_question_pools'"))
exists = result.fetchone() is not None
print(f"Table 'approved_question_pools' exists: {exists}")

if not exists:
    print("\nAvailable tables:")
    result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name"))
    for row in result:
        print(f"  - {row[0]}")

conn.close()
