#!/usr/bin/env python3
"""
Register the 6 new devices for Murabba Linear Park tenant.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from database import SessionLocal
from models import Device, DeviceType, Tenant, ProvisioningKey
import secrets

db = SessionLocal()

try:
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
    
    # Device definitions
    devices_data = [
        {
            "device_id": "emscooter_01",
            "name": "E-Scooter 01",
            "mqtt_topic": "device/emscooter_01/telemetry"
        },
        {
            "device_id": "lightpole_12",
            "name": "Adaptive Pathway Lighting 12",
            "mqtt_topic": "device/lightpole_12/telemetry"
        },
        {
            "device_id": "washroom_03",
            "name": "Smart Washroom 03",
            "mqtt_topic": "device/washroom_03/telemetry"
        },
        {
            "device_id": "fitness_rower_02",
            "name": "Smart Fitness Rower 02",
            "mqtt_topic": "device/fitness_rower_02/telemetry"
        },
        {
            "device_id": "noise_sensor_08",
            "name": "Ambient Noise Sensor 08",
            "mqtt_topic": "device/noise_sensor_08/telemetry"
        },
        {
            "device_id": "recycle_kiosk_01",
            "name": "Smart Recycling Kiosk 01",
            "mqtt_topic": "device/recycle_kiosk_01/telemetry"
        }
    ]
    
    created_count = 0
    for device_info in devices_data:
        # Check if device already exists
        existing = db.query(Device).filter(Device.device_id == device_info["device_id"]).first()
        if existing:
            print(f"  Device {device_info['device_id']} already exists, skipping...")
            continue
        
        # Create device
        device = Device(
            device_id=device_info["device_id"],
            name=device_info["name"],
            device_type_id=mqtt_type.id,
            tenant_id=tenant.id,
            is_active=True,
            is_provisioned=False,  # MQTT devices don't need provisioning keys
            device_metadata=f'{{"mqtt_topic": "{device_info["mqtt_topic"]}"}}'
        )
        db.add(device)
        db.flush()
        
        print(f"  ✓ Created device: {device_info['device_id']} - {device_info['name']}")
        created_count += 1
    
    db.commit()
    print(f"\n✓ Successfully registered {created_count} devices for Murabba Linear Park")
    
except Exception as e:
    print(f"ERROR: {e}")
    db.rollback()
    sys.exit(1)
finally:
    db.close()

