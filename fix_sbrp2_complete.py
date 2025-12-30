#!/usr/bin/env python3
"""Complete fix for SB-RP-2 - creates device, verifies config, and provides diagnostics"""
import sys
import os
import subprocess
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
from models import Device, Tenant, DeviceType

print("=" * 70)
print("SB-RP-2 COMPLETE FIX SCRIPT")
print("=" * 70)

db = SessionLocal()
try:
    # Step 1: Get SB-RP-1 reference
    print("\n[1] Checking SB-RP-1 reference...")
    sb_rp1 = db.query(Device).filter(Device.device_id == "SB-RP-1").first()
    if not sb_rp1:
        print("   ❌ ERROR: SB-RP-1 not found! Cannot proceed.")
        sys.exit(1)
    print(f"   ✓ SB-RP-1 found: tenant_id={sb_rp1.tenant_id}, device_type_id={sb_rp1.device_type_id}")
    
    # Step 2: Check/Create SB-RP-2
    print("\n[2] Checking SB-RP-2 device...")
    sb_rp2 = db.query(Device).filter(Device.device_id == "SB-RP-2").first()
    
    if sb_rp2:
        print(f"   ✓ SB-RP-2 exists (ID: {sb_rp2.id})")
        print(f"     Current active: {sb_rp2.is_active}")
        print(f"     Current metadata: {sb_rp2.device_metadata}")
    else:
        print("   ⚠ SB-RP-2 does not exist - creating...")
        sb_rp2 = Device(
            device_id="SB-RP-2",
            name="Smart Bin 2",
            device_type_id=sb_rp1.device_type_id,
            tenant_id=sb_rp1.tenant_id,
            is_active=True,
            is_provisioned=False,
            device_metadata=json.dumps({"access_token": "murraba", "mqtt_topic": "device/SB-RP-2/telemetry"})
        )
        db.add(sb_rp2)
        print("   ✓ Created SB-RP-2")
    
    # Step 3: Fix metadata and ensure active
    print("\n[3] Updating SB-RP-2 configuration...")
    sb_rp2.device_metadata = json.dumps({"access_token": "murraba", "mqtt_topic": "device/SB-RP-2/telemetry"})
    sb_rp2.is_active = True
    sb_rp2.tenant_id = sb_rp1.tenant_id
    sb_rp2.device_type_id = sb_rp1.device_type_id
    
    db.commit()
    db.refresh(sb_rp2)
    print("   ✓ Configuration updated")
    
    # Step 4: Verify
    print("\n[4] Verification:")
    print(f"   Device ID: {sb_rp2.device_id}")
    print(f"   Name: {sb_rp2.name}")
    print(f"   Active: {sb_rp2.is_active}")
    print(f"   Tenant ID: {sb_rp2.tenant_id}")
    print(f"   Device Type ID: {sb_rp2.device_type_id}")
    print(f"   Metadata: {sb_rp2.device_metadata}")
    
    # Step 5: Check simulator
    print("\n[5] Checking simulator status...")
    try:
        result = subprocess.run(['pgrep', '-f', 'smart_bin_sbrp2'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
            print(f"   ✓ Simulator is running (PIDs: {', '.join(pids)})")
        else:
            print("   ⚠ Simulator is NOT running")
            print("   → Start it with: python scripts/smart_bin_sbrp2_sim.py")
    except Exception as e:
        print(f"   ⚠ Could not check simulator status: {e}")
    
    print("\n" + "=" * 70)
    print("✅ SB-RP-2 IS NOW CONFIGURED CORRECTLY!")
    print("=" * 70)
    print("\nNext steps:")
    print("1. Make sure simulator is running: python scripts/smart_bin_sbrp2_sim.py")
    print("2. Check logs: tail -f /tmp/smart_bin_sbrp2.log")
    print("3. Check backend: docker logs iot-backend -f | grep SB-RP-2")
    print("4. Device should appear online within 10 minutes")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    db.rollback()
finally:
    db.close()

