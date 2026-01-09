#!/usr/bin/env python3
"""
Sync dashboard data to cache table.
Run this periodically (e.g., every 5-10 minutes) to pre-compute data.

This reduces database load on free tier PostgreSQL by:
- Running queries once per sync period
- Storing results in cache table
- Frontend reads from cache (fast, single query)
"""

import sys
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any

from database import SessionLocal
from sqlalchemy import text
from models import User, Tenant

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import cache model
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


def sync_tenant_metrics(db, tenant_id: int) -> Dict[str, Any]:
    """Pre-compute tenant metrics."""
    logger.info(f"Syncing metrics for tenant {tenant_id}")
    
    # Query 1: Count active devices and devices with telemetry
    count_query = text("""
        SELECT 
            COUNT(*) FILTER (WHERE (payload->>'is_active')::text = 'true') as active_devices,
            COUNT(*) FILTER (WHERE payload->'telemetry' IS NOT NULL) as devices_with_telemetry
        FROM devices_snapshot
        WHERE tenant_id = :tenant_id
    """)
    
    count_result = db.execute(count_query, {"tenant_id": tenant_id}).fetchone()
    active_devices = count_result[0] or 0
    devices_with_telemetry = count_result[1] or 0
    
    # Query 2: Get protocol distribution (separate query to avoid nested aggregates)
    protocol_query = text("""
        SELECT 
            COALESCE(payload->'device_type'->>'protocol', 'HTTP') as protocol,
            COUNT(*) as count
        FROM devices_snapshot
        WHERE tenant_id = :tenant_id
        GROUP BY payload->'device_type'->>'protocol'
    """)
    
    protocol_rows = db.execute(protocol_query, {"tenant_id": tenant_id}).fetchall()
    protocol_distribution = {}
    for row in protocol_rows:
        protocol = row[0] or "HTTP"
        count = row[1] or 0
        protocol_distribution[protocol] = count
    
    return {
        "active_devices": active_devices,
        "messages": {
            "total_received": devices_with_telemetry,
            "total_published": 0,
            "total_rejected": 0,
        },
        "sources": protocol_distribution,
    }


def sync_devices_page(db, tenant_id: int, page: int = 1, limit: int = 50) -> Dict[str, Any]:
    """Pre-compute devices page."""
    logger.info(f"Syncing devices page {page} for tenant {tenant_id}")
    
    # Limit tenant 2 to 10 devices
    if tenant_id == 2:
        limit = 10
    
    offset = (page - 1) * limit
    
    # Single query for devices page
    devices_query = text("""
        SELECT 
            device_id,
            payload,
            COUNT(*) OVER() as total_count
        FROM devices_snapshot
        WHERE tenant_id = :tenant_id
        ORDER BY device_id
        LIMIT :limit OFFSET :offset
    """)
    
    rows = db.execute(devices_query, {
        "tenant_id": tenant_id,
        "limit": limit,
        "offset": offset
    }).fetchall()
    
    devices = []
    total = 0
    for row in rows:
        if not total:
            total = row[2] or 0
        devices.append({
            "device_id": row[0],
            "payload": row[1],
        })
    
    return {
        "devices": devices,
        "total": total,
        "page": page,
        "limit": limit,
    }


def sync_health_data(db, tenant_id: int) -> Dict[str, Any]:
    """Pre-compute device health data."""
    logger.info(f"Syncing health data for tenant {tenant_id}")
    
    # Single query for all health data
    health_query = text("""
        SELECT 
            device_id,
            payload->'health' as health_data,
            payload->'telemetry'->'data' as telemetry_data
        FROM devices_snapshot
        WHERE tenant_id = :tenant_id
        ORDER BY device_id
    """)
    
    rows = db.execute(health_query, {"tenant_id": tenant_id}).fetchall()
    
    health_data = []
    for row in rows:
        health_data.append({
            "device_id": row[0],
            "health": row[1] or {},
            "telemetry": row[2] or {},
        })
    
    return {
        "devices": health_data,
        "total": len(health_data),
    }


def save_to_cache(db, tenant_id: int, cache_key: str, data: Dict[str, Any], ttl_minutes: int = 10):
    """Save data to cache table."""
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
    
    # Check if exists
    existing = db.query(DashboardCache).filter(
        DashboardCache.tenant_id == tenant_id,
        DashboardCache.cache_key == cache_key
    ).first()
    
    if existing:
        existing.data = data
        existing.expires_at = expires_at
        existing.updated_at = datetime.now(timezone.utc)
    else:
        cache_entry = DashboardCache(
            tenant_id=tenant_id,
            cache_key=cache_key,
            data=data,
            expires_at=expires_at
        )
        db.add(cache_entry)
    
    db.commit()
    logger.info(f"✅ Cached {cache_key} for tenant {tenant_id}")


def sync_all_tenants():
    """Sync cache for all tenants."""
    db = SessionLocal()
    try:
        # Get all tenants
        tenants = db.query(Tenant).filter(Tenant.is_active == True).all()
        logger.info(f"Syncing cache for {len(tenants)} tenants")
        
        for tenant in tenants:
            try:
                # Sync metrics
                metrics = sync_tenant_metrics(db, tenant.id)
                save_to_cache(db, tenant.id, "metrics", metrics, ttl_minutes=10)
                
                # Sync first page of devices
                devices_page1 = sync_devices_page(db, tenant.id, page=1, limit=50)
                save_to_cache(db, tenant.id, "devices_page_1", devices_page1, ttl_minutes=10)
                
                # Sync health data
                health = sync_health_data(db, tenant.id)
                save_to_cache(db, tenant.id, "health", health, ttl_minutes=10)
                
                logger.info(f"✅ Synced tenant {tenant.id} ({tenant.name})")
            except Exception as e:
                logger.error(f"❌ Error syncing tenant {tenant.id}: {e}", exc_info=True)
                continue
        
        logger.info("✅ Cache sync complete")
    except Exception as e:
        logger.error(f"❌ Cache sync failed: {e}", exc_info=True)
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    sync_all_tenants()

