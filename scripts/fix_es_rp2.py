#!/usr/bin/env python3
"""Fix ES-RP-2 device registration and access token."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models import Device, Tenant, DeviceType
import json

db = SessionLocal()
try:
    # Check if ES-RP-2 exists
    es_rp2 = db.query(Device).filter(Device.device_id == "ES-RP-2").first()
    
    if not es_rp2:
        print("ES-RP-2 device not found in database!")
        print("\nChecking ES-RP-1 for reference...")
        es_rp1 = db.query(Device).filter(Device.device_id == "ES-RP-1").first()
        if es_rp1:
            print(f"ES-RP-1 found:")
            print(f"  ID: {es_rp1.id}")
            print(f"  Name: {es_rp1.name}")
            print(f"  Active: {es_rp1.is_active}")
            print(f"  Tenant ID: {es_rp1.tenant_id}")
            print(f"  Device Type ID: {es_rp1.device_type_id}")
            print(f"  Metadata: {es_rp1.device_metadata}")
            
            # Get Murabba tenant
            tenant = db.query(Tenant).filter(Tenant.code == "1234").first()
            if tenant:
                print(f"\nCreating ES-RP-2 device...")
                mqtt_type = db.query(DeviceType).filter(DeviceType.protocol == "MQTT").first()
                
                es_rp2 = Device(
                    device_id="ES-RP-2",
                    name="E-Scooter 2",
                    device_type_id=mqtt_type.id if mqtt_type else es_rp1.device_type_id,
                    tenant_id=tenant.id,
                    is_active=True,
                    is_provisioned=False,
                    device_metadata=json.dumps({"access_token": "murraba", "mqtt_topic": "device/ES-RP-2/telemetry"})
                )
                db.add(es_rp2)
                db.commit()
                print("✓ ES-RP-2 device created successfully!")
            else:
                print("ERROR: Murabba tenant not found!")
        else:
            print("ES-RP-1 also not found!")
    else:
        print(f"ES-RP-2 found:")
        print(f"  ID: {es_rp2.id}")
        print(f"  Name: {es_rp2.name}")
        print(f"  Active: {es_rp2.is_active}")
        print(f"  Current Metadata: {es_rp2.device_metadata}")
        
        # Update metadata with access token
        metadata = {}
        if es_rp2.device_metadata:
            if isinstance(es_rp2.device_metadata, str):
                try:
                    metadata = json.loads(es_rp2.device_metadata)
                except:
                    metadata = {}
            elif isinstance(es_rp2.device_metadata, dict):
                metadata = es_rp2.device_metadata.copy()
        
        metadata["access_token"] = "murraba"
        metadata["mqtt_topic"] = "device/ES-RP-2/telemetry"
        es_rp2.device_metadata = json.dumps(metadata)
        es_rp2.is_active = True
        db.commit()
        print("\n✓ ES-RP-2 metadata updated with access_token: murraba")
        print(f"  Updated Metadata: {es_rp2.device_metadata}")
finally:
    db.close()

