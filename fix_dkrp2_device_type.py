#!/usr/bin/env python3
"""Fix DK-RP-2 device type - change from Valve Controller to MQTT generic or Digital Kiosk"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
from models import Device, DeviceType

db = SessionLocal()
try:
    print("=" * 70)
    print("FIXING DK-RP-2 DEVICE TYPE")
    print("=" * 70)
    
    # Find DK-RP-2
    dk_rp2 = db.query(Device).filter(Device.device_id == "DK-RP-2").first()
    if not dk_rp2:
        print("❌ DK-RP-2 device not found!")
        sys.exit(1)
    
    print(f"\nCurrent configuration:")
    print(f"  Device ID: {dk_rp2.device_id}")
    print(f"  Name: {dk_rp2.name}")
    current_type = db.query(DeviceType).filter(DeviceType.id == dk_rp2.device_type_id).first()
    print(f"  Current Device Type: {current_type.name if current_type else 'Unknown'} (ID: {dk_rp2.device_type_id})")
    
    # Find Digital Kiosk device type (if exists)
    digital_kiosk_type = db.query(DeviceType).filter(DeviceType.name == "Digital Kiosk").first()
    
    # Find generic MQTT device type
    mqtt_generic_type = db.query(DeviceType).filter(
        DeviceType.name == "MQTT",
        DeviceType.protocol == "MQTT"
    ).first()
    
    # Prefer Digital Kiosk, fallback to generic MQTT
    target_type = digital_kiosk_type or mqtt_generic_type
    
    if not target_type:
        print("\n❌ ERROR: Neither 'Digital Kiosk' nor generic 'MQTT' device type found!")
        print("Available MQTT device types:")
        mqtt_types = db.query(DeviceType).filter(DeviceType.protocol == "MQTT").all()
        for dt in mqtt_types:
            print(f"  - {dt.name} (ID: {dt.id})")
        sys.exit(1)
    
    print(f"\nTarget Device Type: {target_type.name} (ID: {target_type.id})")
    
    if dk_rp2.device_type_id == target_type.id:
        print("\n✅ Device type is already correct!")
    else:
        print(f"\nUpdating device type from '{current_type.name}' to '{target_type.name}'...")
        dk_rp2.device_type_id = target_type.id
        db.commit()
        print("✅ Device type updated!")
    
    print("\n" + "=" * 70)
    print("DK-RP-2 FIXED!")
    print("=" * 70)
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    db.rollback()
finally:
    db.close()

