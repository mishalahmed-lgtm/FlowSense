#!/usr/bin/env python3
"""
Fix demo data issues:
1. Add more device rules
2. Update FOTA job statuses
3. Update device firmware status
4. Send messages to fix protocol distribution
"""

import sys
import os
import random
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models import (
    Device, DeviceRule, FOTAJob, FOTAJobStatus, FOTAJobDevice, 
    FirmwareUpdateStatus, DeviceFirmwareStatus, FirmwareVersion
)
import requests

def add_more_device_rules(db: SessionLocal):
    """Add more device rules."""
    print("\nAdding device rules...")
    
    devices = db.query(Device).filter(Device.tenant_id == 4).all()
    
    # Rule 1: Auto-alert on high temperature for benches
    bench_devices = [d for d in devices if "BENCH" in d.device_id]
    for bench in bench_devices[:3]:
        existing = db.query(DeviceRule).filter(
            DeviceRule.device_id == bench.id,
            DeviceRule.name == "High Temperature Alert"
        ).first()
        
        if not existing:
            rule = DeviceRule(
                device_id=bench.id,
                name="High Temperature Alert",
                description="Send alert when temperature exceeds 40°C",
                priority=90,
                is_active=True,
                rule_type="event",
                condition={"field": "environment.temperature", "operator": ">", "value": 40},
                action={
                    "type": "alert",
                    "priority": "high",
                    "message": "Temperature alert triggered"
                }
            )
            db.add(rule)
            print(f"  ✓ Added rule for {bench.device_id}")
    
    # Rule 2: Collection scheduling for bins
    bin_devices = [d for d in devices if "BIN" in d.device_id]
    for bin_dev in bin_devices:
        existing = db.query(DeviceRule).filter(
            DeviceRule.device_id == bin_dev.id,
            DeviceRule.name == "Auto-schedule collection when full"
        ).first()
        
        if not existing:
            rule = DeviceRule(
                device_id=bin_dev.id,
                name="Auto-schedule collection when full",
                description="Schedule collection when bin reaches 85% capacity",
                priority=100,
                is_active=True,
                rule_type="event",
                condition={"field": "fillLevel.generalWaste", "operator": ">=", "value": 85},
                action={
                    "type": "webhook",
                    "url": "https://api.flowsense.com/collection/schedule",
                    "method": "POST"
                }
            )
            db.add(rule)
            print(f"  ✓ Added rule for {bin_dev.device_id}")
    
    # Rule 3: Power optimization for kiosks
    kiosk_devices = [d for d in devices if "KIOSK" in d.device_id]
    for kiosk in kiosk_devices[:2]:
        existing = db.query(DeviceRule).filter(
            DeviceRule.device_id == kiosk.id,
            DeviceRule.name == "Reduce brightness on low battery"
        ).first()
        
        if not existing:
            rule = DeviceRule(
                device_id=kiosk.id,
                name="Reduce brightness on low battery",
                description="Reduce display brightness when battery is below 30%",
                priority=70,
                is_active=True,
                rule_type="event",
                condition={"field": "battery", "operator": "<", "value": 30},
                action={
                    "type": "device_command",
                    "command": {"action": "set_brightness", "value": 30}
                }
            )
            db.add(rule)
            print(f"  ✓ Added rule for {kiosk.device_id}")
    
    db.commit()
    count = db.query(DeviceRule).count()
    print(f"✓ Total device rules: {count}")

def update_fota_jobs(db: SessionLocal):
    """Update FOTA job statuses to show variety."""
    print("\nUpdating FOTA job statuses...")
    
    jobs = db.query(FOTAJob).filter(FOTAJob.tenant_id == 4).all()
    
    if len(jobs) > 0:
        # Make some completed
        for job in jobs[:3]:
            job.status = FOTAJobStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc) - timedelta(days=random.randint(1, 5))
            print(f"  ✓ {job.name}: COMPLETED")
        
        # Make some in progress
        for job in jobs[3:5]:
            job.status = FOTAJobStatus.RUNNING
            job.started_at = datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 12))
            print(f"  ✓ {job.name}: RUNNING")
        
        # Make one failed
        if len(jobs) > 5:
            jobs[5].status = FOTAJobStatus.FAILED
            jobs[5].started_at = datetime.now(timezone.utc) - timedelta(days=2)
            jobs[5].completed_at = datetime.now(timezone.utc) - timedelta(days=2, hours=1)
            print(f"  ✓ {jobs[5].name}: FAILED")
        
        # Rest remain scheduled
        db.commit()
    
    print(f"✓ Updated {len(jobs)} FOTA jobs")

def update_device_firmware_status(db: SessionLocal):
    """Update device firmware status."""
    print("\nUpdating device firmware status...")
    
    devices = db.query(Device).filter(Device.tenant_id == 4).all()
    
    # Get firmware versions
    from models import Firmware, FirmwareVersion
    
    for device in devices:
        device_type_name = device.device_type.name if device.device_type else ""
        
        # Find matching firmware
        firmware_name = None
        if "Bench" in device_type_name:
            firmware_name = "Smart Bench Firmware"
        elif "Bin" in device_type_name:
            firmware_name = "Smart Bin Firmware"
        elif "Kiosk" in device_type_name:
            firmware_name = "Digital Kiosk Firmware"
        elif "LPG" in device_type_name:
            firmware_name = "LPG Meter Firmware"
        elif "GPS" in device_type_name:
            firmware_name = "GPS Tracker Firmware"
        
        if firmware_name:
            firmware = db.query(Firmware).filter(Firmware.name == firmware_name).first()
            if firmware:
                # Get version 1.0.0 or 1.1.0
                version = db.query(FirmwareVersion).filter(
                    FirmwareVersion.firmware_id == firmware.id,
                    FirmwareVersion.version.in_(["1.0.0", "1.1.0"])
                ).first()
                
                if version:
                    # Check if status exists
                    status = db.query(DeviceFirmwareStatus).filter(
                        DeviceFirmwareStatus.device_id == device.id
                    ).first()
                    
                    if not status:
                        status = DeviceFirmwareStatus(
                            device_id=device.id,
                            current_version=version.version,
                            last_update_at=datetime.now(timezone.utc) - timedelta(days=random.randint(5, 30))
                        )
                        db.add(status)
    
    db.commit()
    print("✓ Updated device firmware status")

def send_protocol_messages(db: SessionLocal):
    """Send messages via API to populate protocol metrics."""
    print("\nSending messages to populate protocol metrics...")
    
    devices = db.query(Device).filter(Device.tenant_id == 4).all()
    
    total_sent = 0
    for device in devices:
        if not device.provisioning_key:
            continue
        
        key = device.provisioning_key.key
        device_type_name = device.device_type.name if device.device_type else ""
        
        # Generate payload based on device type
        if "Bench" in device_type_name:
            payload = {
                "data": {
                    "battery": {"soc": 85, "voltage": 12.6},
                    "environment": {"temperature": 32.5, "co2": 650}
                }
            }
        elif "Bin" in device_type_name:
            payload = {
                "data": {
                    "fillLevel": {"generalWaste": 65},
                    "battery": 80
                }
            }
        elif "Kiosk" in device_type_name:
            payload = {
                "data": {
                    "cpu_usage": 45.2,
                    "battery": 90
                }
            }
        elif "LPG" in device_type_name:
            payload = {
                "data": {
                    "level": 75.5,
                    "pressure": 2.2
                }
            }
        elif "GPS" in device_type_name:
            payload = {
                "data": {
                    "latitude": 24.7136,
                    "longitude": 46.6753,
                    "speed": 45.0
                }
            }
        else:
            payload = {"data": {"value": 100}}
        
        headers = {
            "X-Device-Key": key,
            "Content-Type": "application/json"
        }
        
        try:
            resp = requests.post(
                "http://localhost:5000/api/v1/telemetry/http",
                json=payload,
                headers=headers,
                timeout=5
            )
            if resp.status_code in [200, 202]:
                total_sent += 1
        except Exception as e:
            print(f"  ⚠️  Error for {device.device_id}: {e}")
    
    print(f"✓ Sent {total_sent} messages")

def main():
    print("======================================================================")
    print("FIXING DEMO DATA")
    print("======================================================================")
    
    db = SessionLocal()
    try:
        add_more_device_rules(db)
        update_fota_jobs(db)
        update_device_firmware_status(db)
        send_protocol_messages(db)
        
        print("\n======================================================================")
        print("DEMO DATA FIXED SUCCESSFULLY!")
        print("======================================================================")
    finally:
        db.close()

if __name__ == "__main__":
    main()

