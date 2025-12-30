#!/usr/bin/env python3
"""Fix ES-RP-2 device registration - RUN THIS DIRECTLY"""
import json
from database import SessionLocal
from models import Device, Tenant, DeviceType

db = SessionLocal()
try:
    print("=" * 60)
    print("FIXING ES-RP-2 DEVICE REGISTRATION")
    print("=" * 60)
    
    # Get ES-RP-1 for reference
    es_rp1 = db.query(Device).filter(Device.device_id == "ES-RP-1").first()
    if not es_rp1:
        print("ERROR: ES-RP-1 not found!")
        exit(1)
    
    print(f"ES-RP-1 found: tenant_id={es_rp1.tenant_id}, device_type_id={es_rp1.device_type_id}")
    
    # Check ES-RP-2
    es_rp2 = db.query(Device).filter(Device.device_id == "ES-RP-2").first()
    
    if es_rp2:
        print(f"\nES-RP-2 EXISTS - Updating...")
        print(f"  Current active: {es_rp2.is_active}")
        print(f"  Current metadata: {es_rp2.device_metadata}")
    else:
        print(f"\nES-RP-2 DOES NOT EXIST - Creating...")
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
        print("  Created new device")
    
    # Ensure correct metadata
    es_rp2.device_metadata = json.dumps({"access_token": "murraba", "mqtt_topic": "device/ES-RP-2/telemetry"})
    es_rp2.is_active = True
    es_rp2.tenant_id = es_rp1.tenant_id
    es_rp2.device_type_id = es_rp1.device_type_id
    
    db.commit()
    db.refresh(es_rp2)
    
    print("\n" + "=" * 60)
    print("✅ ES-RP-2 FIXED!")
    print("=" * 60)
    print(f"Device ID: {es_rp2.device_id}")
    print(f"Active: {es_rp2.is_active}")
    print(f"Tenant ID: {es_rp2.tenant_id}")
    print(f"Device Type ID: {es_rp2.device_type_id}")
    print(f"Metadata: {es_rp2.device_metadata}")
    print("=" * 60)
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    db.rollback()
finally:
    db.close()

