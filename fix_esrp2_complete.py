#!/usr/bin/env python3
"""Complete fix for ES-RP-2 - creates device, verifies config, and provides diagnostics"""
import sys
import os
import subprocess
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
from models import Device, Tenant, DeviceType

print("=" * 70)
print("ES-RP-2 COMPLETE FIX SCRIPT")
print("=" * 70)

db = SessionLocal()
try:
    # Step 1: Get ES-RP-1 reference
    print("\n[1] Checking ES-RP-1 reference...")
    es_rp1 = db.query(Device).filter(Device.device_id == "ES-RP-1").first()
    if not es_rp1:
        print("   ❌ ERROR: ES-RP-1 not found! Cannot proceed.")
        sys.exit(1)
    print(f"   ✓ ES-RP-1 found: tenant_id={es_rp1.tenant_id}, device_type_id={es_rp1.device_type_id}")
    
    # Step 2: Check/Create ES-RP-2
    print("\n[2] Checking ES-RP-2 device...")
    es_rp2 = db.query(Device).filter(Device.device_id == "ES-RP-2").first()
    
    if es_rp2:
        print(f"   ✓ ES-RP-2 exists (ID: {es_rp2.id})")
        print(f"     Current active: {es_rp2.is_active}")
        print(f"     Current metadata: {es_rp2.device_metadata}")
    else:
        print("   ⚠ ES-RP-2 does not exist - creating...")
        es_rp2 = Device(
            device_id="ES-RP-2",
            name="E-Scooter 2",
            device_type_id=es_rp1.device_type_id,
            tenant_id=es_rp1.tenant_id,
            is_active=True,
            is_provisioned=False,
            device_metadata=json.dumps({"access_token": "murraba", "mqtt_topic": "device/ES-RP-2/telemetry"})
        )
        db.add(es_rp2)
        print("   ✓ Created ES-RP-2")
    
    # Step 3: Fix metadata and ensure active
    print("\n[3] Updating ES-RP-2 configuration...")
    es_rp2.device_metadata = json.dumps({"access_token": "murraba", "mqtt_topic": "device/ES-RP-2/telemetry"})
    es_rp2.is_active = True
    es_rp2.tenant_id = es_rp1.tenant_id
    es_rp2.device_type_id = es_rp1.device_type_id
    
    db.commit()
    db.refresh(es_rp2)
    print("   ✓ Configuration updated")
    
    # Step 4: Verify
    print("\n[4] Verification:")
    print(f"   Device ID: {es_rp2.device_id}")
    print(f"   Name: {es_rp2.name}")
    print(f"   Active: {es_rp2.is_active}")
    print(f"   Tenant ID: {es_rp2.tenant_id}")
    print(f"   Device Type ID: {es_rp2.device_type_id}")
    print(f"   Metadata: {es_rp2.device_metadata}")
    
    # Step 5: Check simulator
    print("\n[5] Checking simulator status...")
    try:
        result = subprocess.run(['pgrep', '-f', 'escooter_esrp2'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
            print(f"   ✓ Simulator is running (PIDs: {', '.join(pids)})")
        else:
            print("   ⚠ Simulator is NOT running")
            print("   → Start it with: python scripts/escooter_esrp2_sim.py")
    except Exception as e:
        print(f"   ⚠ Could not check simulator status: {e}")
    
    print("\n" + "=" * 70)
    print("✅ ES-RP-2 IS NOW CONFIGURED CORRECTLY!")
    print("=" * 70)
    print("\nNext steps:")
    print("1. Make sure simulator is running: python scripts/escooter_esrp2_sim.py")
    print("2. Check logs: tail -f /tmp/escooter_esrp2.log")
    print("3. Check backend: docker logs iot-backend -f | grep ES-RP-2")
    print("4. Device should appear online within 10 minutes")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    db.rollback()
finally:
    db.close()

