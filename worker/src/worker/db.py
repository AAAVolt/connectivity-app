"""Synchronous database engine for the worker pipeline."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from worker.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    echo=(settings.environment == "local"),
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine)


def get_session() -> Session:
    """Create a new database session."""
    return SessionLocal()
