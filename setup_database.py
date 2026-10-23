import os
import sys
from urllib.parse import urlparse
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError

# Add the current directory to Python path so it can import app
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.config.settings import settings
from app.database.base import Base
# IMPORTANT: Import all models so they are registered with Base metadata
import app.models

def setup_database():
    db_url = settings.DATABASE_URL
    print(f"Database URL configured in .env: {db_url}")
    
    parsed_url = urlparse(db_url)
    db_name = parsed_url.path.lstrip('/')
    
    # Create a connection URL to the default 'postgres' database
    # This allows us to issue the CREATE DATABASE command
    server_url = db_url.replace(f"/{db_name}", "/postgres")
    
    # Connect to the PostgreSQL server (not the target db yet)
    # Using AUTOCOMMIT is required for CREATE DATABASE
    engine_server = create_engine(server_url, isolation_level="AUTOCOMMIT")
    
    try:
        with engine_server.connect() as conn:
            # Check if the database exists
            result = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
                {"dbname": db_name}
            )
            exists = result.scalar() == 1
            
            if not exists:
                print(f"Database '{db_name}' does not exist. Creating it now...")
                # Cannot parameterize database names, so we use string formatting safely
                conn.execute(text(f'CREATE DATABASE "{db_name}"'))
                print(f"Database '{db_name}' created successfully.")
            else:
                print(f"Database '{db_name}' already exists.")
    except Exception as e:
        print(f"Error checking/creating database. Ensure PostgreSQL is running and credentials are correct.")
        print(f"Details: {e}")
        print("Will attempt to proceed with table creation anyway just in case...")
    finally:
        engine_server.dispose()

    # Now connect to the actual target database to create the schema
    print(f"\nConnecting to '{db_name}' to create tables...")
    target_engine = create_engine(db_url)
    
    try:
        # Create all tables declared in the SQLAlchemy models
        Base.metadata.create_all(bind=target_engine)
        print("✅ All database tables and relationships created successfully!")
        print("The database is fully set up and ready to use.")
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        sys.exit(1)

if __name__ == "__main__":
    setup_database()
