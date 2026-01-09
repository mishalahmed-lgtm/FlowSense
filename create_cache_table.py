#!/usr/bin/env python3
"""
Create a cache table for pre-computed dashboard data.
This reduces database load on free tier PostgreSQL.
"""

import sys
from database import SessionLocal, engine
from sqlalchemy import Column, Integer, String, JSON, DateTime, text
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class DashboardCache(Base):
    """Cache table for pre-computed dashboard data."""
    __tablename__ = "dashboard_cache"
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    cache_key = Column(String(100), nullable=False, index=True)  # e.g., "metrics", "devices_page_1"
    data = Column(JSON, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

def create_cache_table():
    """Create the cache table if it doesn't exist."""
    try:
        DashboardCache.__table__.create(bind=engine, checkfirst=True)
        print("✅ Cache table created/verified")
        return True
    except Exception as e:
        print(f"❌ Error creating cache table: {e}")
        return False

if __name__ == "__main__":
    create_cache_table()

