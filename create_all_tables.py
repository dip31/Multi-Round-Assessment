"""Create all tables from SQLAlchemy models in SQLite database."""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath('.'))

from sqlalchemy import create_engine
from app.database.base import Base

# Import all models to register them
import app.models.user
import app.models.assessment
import app.models.aptitude
import app.models.proctoring
import app.models.interview
import app.models.coding
import app.models.rl
import app.models.session_problem
import app.models.advanced_proctoring
import app.models.admin_question_feedback

# Use SQLite database
sqlite_engine = create_engine('sqlite:///database.db')

print("Creating all tables in SQLite...")
Base.metadata.create_all(bind=sqlite_engine)
print("All tables created successfully!")

# Verify
import sqlite3
conn = sqlite3.connect('database.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print('All tables:', [t[0] for t in tables])
conn.close()