"""
Pytest configuration and fixture module.

Ensures that environment credentials are pre-populated and database engines
are configured to run on an isolated test SQLite database.
"""

import os
import sys

# Seed environment configuration variables before importing settings/database
os.environ["ENV"] = "testing"
os.environ["LOG_LEVEL"] = "WARNING"
os.environ["GROQ_API_KEY"] = "gsk_valid_test_api_key"
os.environ["NOTION_TOKEN"] = "secret_valid_test_notion_token"
os.environ["NOTION_DATABASE_ID"] = "valid_database_uuid"
os.environ["DATABASE_URL"] = "sqlite:///./test_shadow_ops.db"

import pytest
from src.engine.models import Base
from src.engine.database import engine, SessionLocal, init_db


@pytest.fixture(scope="session", autouse=True)
def init_test_database():
    """
    Initializes the schema once for the entire test session.
    Cleans up the database file afterwards.
    """
    # Create tables
    init_db()
    
    yield
    
    # Dispose of engine connection pool to release file locks on Windows
    engine.dispose()
    
    # Delete the test sqlite db file
    db_file = "./test_shadow_ops.db"
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
        except Exception:
            pass


@pytest.fixture(scope="function")
def db_session():
    """
    Provides a database session for each test function, cleaning rows after.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        
        # Clean up database row data between tests to ensure complete isolation
        cleanup_session = SessionLocal()
        try:
            for table in reversed(Base.metadata.sorted_tables):
                cleanup_session.execute(table.delete())
            cleanup_session.commit()
        except Exception:
            cleanup_session.rollback()
        finally:
            cleanup_session.close()
