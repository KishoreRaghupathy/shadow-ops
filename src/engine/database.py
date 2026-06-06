"""
Database engine, sessionmaker, and helper functions for Shadow-Ops.

Automatically connects to the database specified in settings.DATABASE_URL
and provides connection initialization with robust SQLite compatibility.
"""

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from config.settings import settings, logger
from src.engine.models import Base

# Setup connection arguments. SQLite requires check_same_thread=False
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

try:
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args=connect_args,
        pool_pre_ping=True
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
except Exception as e:
    logger.critical(f"Failed to initialize database engine for {settings.DATABASE_URL}: {str(e)}")
    raise e


def init_db() -> None:
    """
    Creates all database tables defined in the metadata models.
    """
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Successfully initialized database tables in database")
    except Exception as e:
        logger.error(f"Error initializing database tables: {str(e)}")
        raise e


def get_db() -> Generator[Session, None, None]:
    """
    Dependency generator yielding db session, closing automatically after usage.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
