#!/usr/bin/env python3
"""Complete fix for RS-RP-1 - creates device, verifies config, and provides diagnostics"""
import sys
import os
import subprocess
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
from models import Device, Tenant, DeviceType

print("=" * 70)
print("RS-RP-1 COMPLETE FIX SCRIPT")
print("=" * 70)

db = SessionLocal()
try:
    # Step 1: Find a reference device from Murabba tenant (e.g., AN-RP-1 or ES-RP-1)
    print("\n[1] Finding reference device from Murabba tenant...")
    murabba_tenant = db.query(Tenant).filter(Tenant.code == "1234").first()
    if not murabba_tenant:
        print("   ❌ ERROR: Murabba tenant (code: 1234) not found!")
        sys.exit(1)
    print(f"   ✓ Murabba tenant found (ID: {murabba_tenant.id})")
    
    # Try to find AN-RP-1 (noise sensor) or ES-RP-1 (e-scooter) as reference
    reference_device = db.query(Device).filter(
        Device.device_id.in_(["AN-RP-1", "ES-RP-1", "SW-RP-1"]),
        Device.tenant_id == murabba_tenant.id
    ).first()
    
    if not reference_device:
        print("   ❌ ERROR: No reference device found (AN-RP-1, ES-RP-1, or SW-RP-1)")
        sys.exit(1)
    print(f"   ✓ Reference device found: {reference_device.device_id} (tenant_id={reference_device.tenant_id}, device_type_id={reference_device.device_type_id})")
    
    # Step 2: Check/Create RS-RP-1
    print("\n[2] Checking RS-RP-1 device...")
    rs_rp1 = db.query(Device).filter(Device.device_id == "RS-RP-1").first()
    
    if rs_rp1:
        print(f"   ✓ RS-RP-1 exists (ID: {rs_rp1.id})")
        print(f"     Current active: {rs_rp1.is_active}")
        print(f"     Current metadata: {rs_rp1.device_metadata}")
    else:
        print("   ⚠ RS-RP-1 does not exist - creating...")
        rs_rp1 = Device(
            device_id="RS-RP-1",
            name="Rain Sensor 1",
            device_type_id=reference_device.device_type_id,
            tenant_id=reference_device.tenant_id,
            is_active=True,
            is_provisioned=False,
            device_metadata=json.dumps({"access_token": "murraba", "mqtt_topic": "device/RS-RP-1/telemetry"})
        )
        db.add(rs_rp1)
        print("   ✓ Created RS-RP-1")
    
    # Step 3: Fix metadata and ensure active
    print("\n[3] Updating RS-RP-1 configuration...")
    rs_rp1.device_metadata = json.dumps({"access_token": "murraba", "mqtt_topic": "device/RS-RP-1/telemetry"})
    rs_rp1.is_active = True
    rs_rp1.tenant_id = reference_device.tenant_id
    rs_rp1.device_type_id = reference_device.device_type_id
    
    db.commit()
    db.refresh(rs_rp1)
    print("   ✓ Configuration updated")
    
    # Step 4: Verify
    print("\n[4] Verification:")
    print(f"   Device ID: {rs_rp1.device_id}")
    print(f"   Name: {rs_rp1.name}")
    print(f"   Active: {rs_rp1.is_active}")
    print(f"   Tenant ID: {rs_rp1.tenant_id}")
    print(f"   Device Type ID: {rs_rp1.device_type_id}")
    print(f"   Metadata: {rs_rp1.device_metadata}")
    
    # Step 5: Check simulator
    print("\n[5] Checking simulator status...")
    try:
        result = subprocess.run(['pgrep', '-f', 'rain_sensor_rsrp1'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
            print(f"   ✓ Simulator is running (PIDs: {', '.join(pids)})")
        else:
            print("   ⚠ Simulator is NOT running")
            print("   → Start it with: MQTT_HOST=localhost MQTT_PORT=1884 ACCESS_TOKEN=murraba python3 scripts/rain_sensor_rsrp1_sim.py")
    except Exception as e:
        print(f"   ⚠ Could not check simulator status: {e}")
    
    print("\n" + "=" * 70)
    print("✅ RS-RP-1 IS NOW CONFIGURED CORRECTLY!")
    print("=" * 70)
    print("\nNext steps:")
    print("1. Make sure simulator is running:")
    print("   MQTT_HOST=localhost MQTT_PORT=1884 ACCESS_TOKEN=murraba python3 scripts/rain_sensor_rsrp1_sim.py")
    print("2. Check backend logs: docker logs iot-backend -f | grep RS-RP-1")
    print("3. Device should appear online within 10 minutes")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    db.rollback()
finally:
    db.close()

