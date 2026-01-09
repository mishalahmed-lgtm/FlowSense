#!/usr/bin/env python3
"""
Sync cache data to remote Render database.
Run this locally - connects to your Render PostgreSQL.

Set this up as a cron job on your local machine:
  */10 * * * * cd /path/to/project && python sync_cache_remote.py
"""

import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Your Render database URL
RENDER_DB_URL = os.environ.get("RENDER_DB_URL", "postgresql://iot_user:cuhaltp9kZ7eeCPzrD5roodGh7IIMgZc@dpg-d5afr5euk2gs73enm170-a.virginia-postgres.render.com/iot_platform")

def sync_remote_cache():
    """Sync cache data to remote Render DB."""
    print("🔌 Connecting to Render database...")
    
    # Create engine for remote DB
    remote_engine = create_engine(RENDER_DB_URL, pool_pre_ping=True)
    RemoteSessionLocal = sessionmaker(bind=remote_engine)
    
    # Override database connection
    import database
    original_session = database.SessionLocal
    database.SessionLocal = RemoteSessionLocal
    
    try:
        # Import and run sync
        from sync_dashboard_cache import sync_all_tenants
        sync_all_tenants()
        print("✅ Cache sync complete!")
        return True
    except Exception as e:
        print(f"❌ Error syncing: {e}", exc_info=True)
        return False
    finally:
        database.SessionLocal = original_session

if __name__ == "__main__":
    success = sync_remote_cache()
    sys.exit(0 if success else 1)

