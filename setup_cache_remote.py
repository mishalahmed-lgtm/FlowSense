#!/usr/bin/env python3
"""
Setup cache table and sync data to remote Render database.
Run this locally - it connects to your Render PostgreSQL.
"""

import os
import sys
from database import SessionLocal, engine
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Your Render database URL
RENDER_DB_URL = os.environ.get("RENDER_DB_URL", "postgresql://iot_user:cuhaltp9kZ7eeCPzrD5roodGh7IIMgZc@dpg-d5afr5euk2gs73enm170-a.virginia-postgres.render.com/iot_platform")

def setup_remote_cache():
    """Create cache table and sync data on remote Render DB."""
    print("🔌 Connecting to Render database...")
    
    # Create engine for remote DB
    remote_engine = create_engine(RENDER_DB_URL, pool_pre_ping=True)
    RemoteSessionLocal = sessionmaker(bind=remote_engine)
    
    # Step 1: Create cache table
    print("\n📦 Step 1: Creating cache table...")
    from sqlalchemy import Column, Integer, String, JSON, DateTime
    from sqlalchemy.sql import func
    from sqlalchemy.ext.declarative import declarative_base
    
    Base = declarative_base()
    
    class DashboardCache(Base):
        __tablename__ = "dashboard_cache"
        id = Column(Integer, primary_key=True)
        tenant_id = Column(Integer, nullable=False, index=True)
        cache_key = Column(String(100), nullable=False, index=True)
        data = Column(JSON, nullable=False)
        expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
        created_at = Column(DateTime(timezone=True), server_default=func.now())
        updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    try:
        DashboardCache.__table__.create(bind=remote_engine, checkfirst=True)
        print("✅ Cache table created/verified")
    except Exception as e:
        print(f"❌ Error creating table: {e}")
        return False
    
    # Step 2: Sync data
    print("\n🔄 Step 2: Syncing data to cache...")
    
    # Import sync function
    sys.path.insert(0, '.')
    from sync_dashboard_cache import sync_all_tenants
    
    # Override database connection
    import database
    original_session = database.SessionLocal
    database.SessionLocal = RemoteSessionLocal
    
    try:
        sync_all_tenants()
        print("✅ Data synced successfully!")
        return True
    except Exception as e:
        print(f"❌ Error syncing data: {e}", exc_info=True)
        return False
    finally:
        # Restore original session
        database.SessionLocal = original_session

if __name__ == "__main__":
    success = setup_remote_cache()
    if success:
        print("\n🎉 Cache setup complete on Render database!")
        print("\nNext: Set up Render Cron Job to run sync_dashboard_cache.py every 10 minutes")
    else:
        print("\n❌ Setup failed. Check errors above.")
        sys.exit(1)

