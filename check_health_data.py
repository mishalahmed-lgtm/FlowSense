#!/usr/bin/env python3
"""Check health data for all devices in database."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import create_engine, text
from config import settings

# Connect to database
print("🔌 Connecting to database...")
engine = create_engine(settings.database_url, pool_pre_ping=True)

print("📊 Checking health data for all devices...\n")

with engine.connect() as conn:
    # Check devices_snapshot table (for tenant admins)
    query_snapshot = text("""
        SELECT 
            COUNT(*) as total_snapshots,
            COUNT(DISTINCT device_id) as unique_devices,
            COUNT(CASE WHEN payload->'health' IS NOT NULL THEN 1 END) as devices_with_health
        FROM devices_snapshot
        WHERE tenant_id = 2
    """)
    
    result = conn.execute(query_snapshot)
    row = result.fetchone()
    print("=" * 80)
    print("DEVICES_SNAPSHOT TABLE (Tenant Admin View):")
    print("=" * 80)
    print(f"Total snapshots: {row.total_snapshots}")
    print(f"Unique devices: {row.unique_devices}")
    print(f"Devices with health data: {row.devices_with_health}")
    
    # Check DeviceHealthMetrics table (for admin view)
    query_health = text("""
        SELECT 
            COUNT(*) as total_health_metrics,
            COUNT(DISTINCT device_id) as unique_devices
        FROM device_health_metrics
    """)
    
    result = conn.execute(query_health)
    row = result.fetchone()
    print("\n" + "=" * 80)
    print("DEVICE_HEALTH_METRICS TABLE (Admin View):")
    print("=" * 80)
    print(f"Total health metrics: {row.total_health_metrics}")
    print(f"Unique devices: {row.unique_devices}")
    
    # Check devices table
    query_devices = text("""
        SELECT 
            COUNT(*) as total_devices,
            COUNT(CASE WHEN is_active = true THEN 1 END) as active_devices
        FROM devices
        WHERE tenant_id = 2
    """)
    
    result = conn.execute(query_devices)
    row = result.fetchone()
    print("\n" + "=" * 80)
    print("DEVICES TABLE:")
    print("=" * 80)
    print(f"Total devices: {row.total_devices}")
    print(f"Active devices: {row.active_devices}")
    
    # Sample health data from snapshot
    query_sample = text("""
        SELECT 
            device_id,
            payload->'health'->>'current_status' as status,
            payload->'health'->>'last_seen_at' as last_seen,
            payload->'health'->>'uptime_24h_percent' as uptime_24h,
            payload->'health'->>'connectivity_score' as connectivity
        FROM devices_snapshot
        WHERE tenant_id = 2
        AND payload->'health' IS NOT NULL
        LIMIT 10
    """)
    
    result = conn.execute(query_sample)
    samples = result.fetchall()
    
    print("\n" + "=" * 80)
    print("SAMPLE HEALTH DATA (First 10 devices with health data):")
    print("=" * 80)
    print(f"{'Device ID':<20} {'Status':<10} {'Last Seen':<25} {'Uptime 24h':<12} {'Connectivity':<12}")
    print("-" * 80)
    for sample in samples:
        device_id = sample.device_id or "N/A"
        status = sample.status or "N/A"
        last_seen = str(sample.last_seen)[:24] if sample.last_seen else "N/A"
        uptime = sample.uptime_24h or "N/A"
        connectivity = sample.connectivity or "N/A"
        print(f"{device_id:<20} {status:<10} {last_seen:<25} {str(uptime):<12} {str(connectivity):<12}")
    
    print("\n" + "=" * 80)
    print("✅ Health data check complete!")
    print("=" * 80)

