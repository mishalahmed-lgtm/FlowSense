#!/usr/bin/env python3
"""
Seed protocol distribution metrics for demo.

This script simulates message activity to populate the metrics collector
so that protocol distribution cards show up on the dashboard.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from metrics import metrics
from database import SessionLocal
from models import Device, DeviceType

def seed_protocol_metrics():
    """Seed the metrics collector with protocol distribution data."""
    print("Seeding protocol distribution metrics...")
    
    db = SessionLocal()
    try:
        # Get all demo devices
        devices = db.query(Device).filter(Device.tenant_id == 4).all()  # Demo tenant ID
        
        print(f"Found {len(devices)} devices")
        
        # Simulate message activity for each device based on their protocol
        for device in devices:
            device_type = db.query(DeviceType).filter(DeviceType.id == device.device_type_id).first()
            if not device_type:
                continue
            
            protocol = device_type.protocol or "MQTT"
            
            # Simulate 50-200 messages per device
            message_count = 50 + (hash(device.device_id) % 150)
            
            for i in range(message_count):
                # Record message as received and published
                metrics.record_message_received(device.device_id, protocol)
                metrics.record_message_published(device.device_id)
            
            print(f"  ✓ Seeded {message_count} messages for {device.device_id} ({protocol})")
        
        print(f"\n✓ Protocol distribution metrics seeded!")
        print(f"   Total messages: {sum(50 + (hash(d.device_id) % 150) for d in devices)}")
        print(f"   Protocols: {set(d.device_type.protocol for d in devices if d.device_type)}")
        
    finally:
        db.close()

if __name__ == "__main__":
    seed_protocol_metrics()

