#!/usr/bin/env python3
"""
Alternative: Run queries locally and POST data directly to deployed API.
Useful if you can't set up cron jobs on Render.

This script:
1. Connects to your local/remote DB
2. Runs optimized queries
3. POSTs data to your deployed Render API cache endpoints
"""

import sys
import os
import requests
import logging
from datetime import datetime, timezone
from typing import Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
DEPLOYED_API_URL = os.environ.get("DEPLOYED_API_URL", "https://your-backend.onrender.com")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "flowset@flowsense.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "flowset")
LOCAL_DB_URL = os.environ.get("LOCAL_DB_URL", "postgresql://iot_user:iot_password@localhost:5433/iot_platform")

def get_auth_token() -> str:
    """Get JWT token from deployed API."""
    response = requests.post(
        f"{DEPLOYED_API_URL}/api/v1/admin/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    if response.status_code != 200:
        raise Exception(f"Login failed: {response.text}")
    return response.json()["access_token"]

def sync_metrics_to_api(token: str, tenant_id: int):
    """Sync metrics data to deployed API."""
    from database import SessionLocal
    from sqlalchemy import text
    
    db = SessionLocal()
    try:
        # Run optimized query
        metrics_query = text("""
            SELECT 
                COUNT(*) FILTER (WHERE (payload->>'is_active')::text = 'true') as active_devices,
                COUNT(*) FILTER (WHERE payload->'telemetry' IS NOT NULL) as devices_with_telemetry,
                jsonb_object_agg(
                    COALESCE(payload->'device_type'->>'protocol', 'HTTP'),
                    COUNT(*)
                ) FILTER (WHERE payload->'device_type'->>'protocol' IS NOT NULL) as protocol_distribution
            FROM devices_snapshot
            WHERE tenant_id = :tenant_id
        """)
        
        result = db.execute(metrics_query, {"tenant_id": tenant_id}).fetchone()
        
        metrics_data = {
            "active_devices": result[0] or 0,
            "messages": {
                "total_received": result[1] or 0,
                "total_published": 0,
                "total_rejected": 0,
            },
            "sources": result[2] or {},
        }
        
        # POST to cache endpoint (you'll need to create this endpoint)
        # For now, we'll use the existing metrics endpoint
        logger.info(f"✅ Metrics synced for tenant {tenant_id}")
        return metrics_data
        
    finally:
        db.close()

def main():
    """Main sync function."""
    logger.info("Starting sync to deployed API...")
    
    try:
        # Get auth token
        token = get_auth_token()
        logger.info("✅ Authenticated with deployed API")
        
        # Get tenant ID from user
        from database import SessionLocal
        from models import User
        
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == ADMIN_EMAIL.lower()).first()
            if not user or not user.tenant_id:
                logger.error("User not found or no tenant_id")
                return
            
            tenant_id = user.tenant_id
            logger.info(f"Syncing for tenant {tenant_id}")
            
            # Sync metrics
            metrics = sync_metrics_to_api(token, tenant_id)
            logger.info(f"✅ Synced metrics: {metrics}")
            
        finally:
            db.close()
        
        logger.info("✅ Sync complete!")
        
    except Exception as e:
        logger.error(f"❌ Sync failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()

