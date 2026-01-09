#!/usr/bin/env python3
"""Query all devices from database and post results to health endpoint."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import create_engine, text
from config import settings
import requests
import json

# Connect to database
print("🔌 Connecting to database...")
engine = create_engine(settings.database_url, pool_pre_ping=True)

# Query all devices
print("📊 Querying all devices from database...")
with engine.connect() as conn:
    query = text("""
        SELECT 
            d.id,
            d.device_id,
            d.name,
            d.is_active,
            d.tenant_id,
            t.name as tenant_name,
            dt.name as device_type_name
        FROM devices d
        LEFT JOIN tenants t ON d.tenant_id = t.id
        LEFT JOIN device_types dt ON d.device_type_id = dt.id
        ORDER BY d.id
    """)
    
    result = conn.execute(query)
    devices = []
    for row in result:
        devices.append({
            'id': row.id,
            'device_id': row.device_id,
            'name': row.name,
            'is_active': row.is_active,
            'tenant_id': row.tenant_id,
            'tenant_name': row.tenant_name,
            'device_type': row.device_type_name
        })
    
    print(f"\n✅ Found {len(devices)} devices in database\n")
    print("=" * 80)
    print("ALL DEVICES DATA:")
    print("=" * 80)
    print(f"{'ID':<6} {'Device ID':<20} {'Name':<30} {'Active':<8} {'Tenant':<20}")
    print("-" * 80)
    
    for device in devices[:50]:  # Show first 50
        active = "Yes" if device['is_active'] else "No"
        name = device['name'] or device['device_id']
        tenant = device['tenant_name'] or f"Tenant {device['tenant_id']}"
        print(f"{device['id']:<6} {device['device_id']:<20} {name[:28]:<30} {active:<8} {tenant[:18]:<20}")
    
    if len(devices) > 50:
        print(f"\n... and {len(devices) - 50} more devices")
    
    print("=" * 80)
    print(f"\n📊 Total devices: {len(devices)}")
    
    # Calculate summary stats
    active_count = sum(1 for d in devices if d['is_active'])
    inactive_count = len(devices) - active_count
    
    # Get health endpoint URL
    api_base = settings.api_base_url or "https://flowsense-772d.onrender.com"
    health_endpoint = f"{api_base}/devices/health"
    
    print(f"\n🌐 Querying health endpoint: {health_endpoint}")
    print(f"   (This endpoint returns health data for devices)")
    print(f"   Verifying devices are accessible via health API...\n")
    
    # Query the health endpoint to see what devices have health data
    try:
        # Try to get health data (this requires auth, but let's try)
        response = requests.get(health_endpoint, timeout=30)
        if response.status_code == 200:
            health_data = response.json()
            print(f"✅ Health endpoint returned {len(health_data)} devices with health data")
            if len(health_data) > 0:
                print(f"\n   Sample health data (first device):")
                sample = health_data[0]
                print(f"   - Device ID: {sample.get('device_id', 'N/A')}")
                print(f"   - Device Name: {sample.get('device_name', 'N/A')}")
                print(f"   - Status: {sample.get('current_status', 'N/A')}")
        elif response.status_code == 401:
            print("⚠️  Health endpoint requires authentication")
            print(f"   Status: {response.status_code}")
            print(f"   (This is expected - the endpoint requires a valid JWT token)")
        else:
            print(f"⚠️  Health endpoint returned status: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
    except requests.exceptions.ConnectionError as e:
        print(f"⚠️  Could not connect to health endpoint: {e}")
        print(f"   (The backend may not be running locally)")
    except Exception as e:
        print(f"❌ Error querying health endpoint: {e}")
    
    print(f"\n📋 DEVICE DATA SUMMARY FOR HEALTH ENDPOINT:")
    print(f"   Total devices in database: {len(devices)}")
    print(f"   Active devices: {active_count}")
    print(f"   Inactive devices: {inactive_count}")
    print(f"   These devices should be accessible via: {health_endpoint}")
    print(f"   (Requires authentication token)")
    
    # Also show summary
    print("\n" + "=" * 80)
    print("SUMMARY:")
    print("=" * 80)
    print(f"Total devices: {len(devices)}")
    print(f"Active devices: {active_count}")
    print(f"Inactive devices: {inactive_count}")
    
    # Group by tenant
    tenants = {}
    for device in devices:
        tenant_id = device['tenant_id']
        if tenant_id not in tenants:
            tenants[tenant_id] = {'name': device['tenant_name'], 'count': 0}
        tenants[tenant_id]['count'] += 1
    
    print(f"\nDevices by tenant:")
    for tenant_id, info in sorted(tenants.items()):
        tenant_name = info['name'] or f"Tenant {tenant_id}"
        print(f"  {tenant_name}: {info['count']} devices")
    
    print("\n" + "=" * 80)
    print("✅ Query complete!")
    print("=" * 80)

