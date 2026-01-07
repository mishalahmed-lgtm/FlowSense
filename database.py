"""Database connection and session management."""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import settings

# Create database engine
# For Render free tier: ONLY 1 connection allowed, so we set min=1, max=2 for safety
# This prevents connection exhaustion and ensures connection reuse
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,        # Test connections before using (detect stale connections)
    pool_size=1,                # Keep 1 connection in pool (free tier limit)
    max_overflow=1,             # Allow 1 overflow connection if needed (total max: 2)
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

