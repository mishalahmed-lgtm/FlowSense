#!/usr/bin/env python3
"""
Seed protocol distribution metrics by sending actual telemetry messages.

This sends real HTTP requests to the backend to populate the metrics collector.
"""

import sys
import os
import requests
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models import Device, DeviceType

API_BASE = "http://localhost:5000"

def seed_metrics():
    """Send telemetry messages to seed metrics."""
    print("Seeding protocol distribution via API...")
    
    db = SessionLocal()
    try:
        # Get all demo devices with their provisioning keys
        devices = db.query(Device).filter(Device.tenant_id == 4).all()  # Demo tenant ID
        
        print(f"Found {len(devices)} devices")
        
        total_sent = 0
        for device in devices:
            device_type = db.query(DeviceType).filter(DeviceType.id == device.device_type_id).first()
            if not device_type:
                continue
            
            protocol = device_type.protocol or "MQTT"
            
            # Get provisioning key from relationship
            if not device.provisioning_key:
                print(f"  ⚠️  Skipping {device.device_id} - no provisioning key")
                continue
            
            key_string = device.provisioning_key.key
            
            # Send 3-5 messages per device
            message_count = 3 + (hash(device.device_id) % 3)
            
            for i in range(message_count):
                try:
                    # Generate a simple payload based on device type
                    type_name = device_type.name.lower()
                    if "bench" in type_name:
                        payload = {"battery_level": 85.0, "temperature": 22.5}
                    elif "bin" in type_name:
                        payload = {"level": 45.0, "temperature": 18.0}
                    elif "kiosk" in type_name:
                        payload = {"status": "online", "uptime": 3600}
                    elif "lpg" in type_name:
                        payload = {"level": 75.0, "pressure": 2.5}
                    elif "gps" in type_name:
                        payload = {"latitude": 24.7136, "longitude": 46.6753, "speed": 45.0}
                    else:
                        payload = {"value": 100.0}
                    
                    headers = {
                        "X-Device-Key": key_string,
                        "Content-Type": "application/json"
                    }
                    
                    response = requests.post(
                        f"{API_BASE}/telemetry/http",
                        json={"data": payload},
                        headers=headers,
                        timeout=5
                    )
                    
                    if response.status_code in [200, 202]:
                        total_sent += 1
                    else:
                        print(f"  ⚠️  Failed for {device.device_id}: {response.status_code}")
                    
                    # Small delay
                    time.sleep(0.1)
                    
                except Exception as e:
                    print(f"  ⚠️  Error for {device.device_id}: {e}")
            
            print(f"  ✓ Sent {message_count} messages for {device.device_id} ({protocol})")
        
        print(f"\n✓ Protocol distribution metrics seeded via API!")
        print(f"   Total messages sent: {total_sent}")
        
    finally:
        db.close()

if __name__ == "__main__":
    seed_metrics()

