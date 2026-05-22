import sys
from pathlib import Path

# Ensure repository root is on PYTHONPATH for imports like `app.*`
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Workaround: make PostgreSQL JSONB available as SQLAlchemy JSON for SQLite tests
try:
	from sqlalchemy import JSON
	import sqlalchemy.dialects.postgresql as _pg
	_pg.JSONB = JSON
except Exception:
	pass
