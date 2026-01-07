"""Database connection and session management."""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import settings

# Create database engine
# Increased pool size to handle background services + API requests + WebSocket
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,        # Test connections before using (detect stale connections)
    pool_size=5,                # Increased from 1 to 5 to handle background services
    max_overflow=3,             # Allow 3 overflow connections (total max: 8)
    pool_recycle=3600,          # Recycle connections every hour (prevent timeout)
    pool_timeout=30,            # Wait up to 30s for a connection from pool
    echo_pool=False,            # Set to True to debug connection pool usage
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """Dependency for getting database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

