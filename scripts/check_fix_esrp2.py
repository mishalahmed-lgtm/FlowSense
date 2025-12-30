#!/usr/bin/env python3
"""Check and fix ES-RP-2 device registration."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models import Device, Tenant, DeviceType
import json

db = SessionLocal()
try:
    print("Checking ES-RP-2 device registration...")
    print("=" * 60)
    
    # Check if ES-RP-2 exists
    es_rp2 = db.query(Device).filter(Device.device_id == "ES-RP-2").first()
    
    if not es_rp2:
        print("❌ ES-RP-2 device NOT FOUND in database!")
        print("\nCreating ES-RP-2 device...")
        
        # Get ES-RP-1 as reference
        es_rp1 = db.query(Device).filter(Device.device_id == "ES-RP-1").first()
        if not es_rp1:
            print("ERROR: ES-RP-1 not found! Cannot create ES-RP-2 without reference.")
            sys.exit(1)
        
        # Get Murabba tenant
        tenant = db.query(Tenant).filter(Tenant.code == "1234").first()
        if not tenant:
            print("ERROR: Murabba tenant (code: 1234) not found!")
            sys.exit(1)
        
        # Get MQTT device type
        mqtt_type = db.query(DeviceType).filter(DeviceType.protocol == "MQTT").first()
        if not mqtt_type:
            print("ERROR: MQTT device type not found!")
            sys.exit(1)
        
        # Create ES-RP-2
        es_rp2 = Device(
            device_id="ES-RP-2",
            name="E-Scooter 2",
            device_type_id=mqtt_type.id,
            tenant_id=tenant.id,
            is_active=True,
            is_provisioned=False,
            device_metadata=json.dumps({
                "access_token": "murraba",
                "mqtt_topic": "device/ES-RP-2/telemetry"
            })
        )
        db.add(es_rp2)
        db.commit()
        print("✅ ES-RP-2 device created successfully!")
    else:
        print("✅ ES-RP-2 device found!")
        print(f"   ID: {es_rp2.id}")
        print(f"   Name: {es_rp2.name}")
        print(f"   Active: {es_rp2.is_active}")
        print(f"   Tenant ID: {es_rp2.tenant_id}")
        
        # Check and update metadata
        metadata = {}
        if es_rp2.device_metadata:
            if isinstance(es_rp2.device_metadata, str):
                try:
                    metadata = json.loads(es_rp2.device_metadata)
                except:
                    metadata = {}
            elif isinstance(es_rp2.device_metadata, dict):
                metadata = es_rp2.device_metadata.copy()
        
        current_token = metadata.get("access_token")
        print(f"   Current access_token: {current_token}")
        
        if current_token != "murraba":
            print(f"\n⚠️  Access token mismatch! Updating to 'murraba'...")
            metadata["access_token"] = "murraba"
            metadata["mqtt_topic"] = "device/ES-RP-2/telemetry"
            es_rp2.device_metadata = json.dumps(metadata)
            es_rp2.is_active = True
            db.commit()
            print("✅ Access token updated to 'murraba'")
        else:
            print("✅ Access token is correct: 'murraba'")
        
        if not es_rp2.is_active:
            print("\n⚠️  Device is inactive! Activating...")
            es_rp2.is_active = True
            db.commit()
            print("✅ Device activated")
    
    print("\n" + "=" * 60)
    print("ES-RP-2 is ready!")
    print("=" * 60)
    
finally:
    db.close()

