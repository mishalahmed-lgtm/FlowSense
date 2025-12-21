#!/usr/bin/env python3
"""
Comprehensive Demo Profile Setup Script

Creates a fully configured demo tenant with:
- 15 realistic devices with proper names
- Comprehensive alert rules
- Device rules for automation
- FOTA jobs and firmware versions
- Utility billing data (tariffs, contracts, consumption, invoices)
- Telemetry data to make the system look full
- Device health metrics

Usage: python scripts/create_demo_profile.py
"""

import sys
import os
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
import random
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from admin_auth import hash_password
from models import (
    Tenant, User, UserRole, Device, DeviceType, ProvisioningKey,
    AlertRule, AlertPriority, DeviceRule, DeviceHealthMetrics, DeviceHealthHistory,
    Firmware, FirmwareVersion, FOTAJob, FOTAJobStatus, FOTAJobDevice,
    FirmwareUpdateStatus, DeviceFirmwareStatus, DeviceDashboard,
    TelemetryLatest, TelemetryTimeseries,
    UtilityTariff, UtilityDeviceContract, UtilityConsumption, UtilityInvoice
)

def create_demo_tenant(db: Session):
    """Create or get demo tenant."""
    print("Setting up demo tenant...")
    tenant = db.query(Tenant).filter(
        (Tenant.code == "DEMO") | (Tenant.name.contains("Demo"))
    ).first()
    
    if not tenant:
        tenant = Tenant(
            name="FlowSense Demo City",
            code="DEMO",
            is_active=True
        )
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
        print(f"✓ Created demo tenant: {tenant.name} (ID: {tenant.id})")
    else:
        print(f"✓ Using existing tenant: {tenant.name} (ID: {tenant.id})")
    
    return tenant

def create_demo_user(db: Session, tenant: Tenant):
    """Create or update demo user with all modules enabled."""
    print("Setting up demo user...")
    user = db.query(User).filter(User.email == "demo@flowsense.com").first()
    
    if user:
        # Update existing user to ensure all modules are enabled
        user.enabled_modules = [
            "devices", "dashboards", "utility", "rules", "alerts",
            "health", "firmware", "analytics"
        ]
        user.tenant_id = tenant.id
        user.is_active = True
        db.commit()
        print(f"✓ Updated demo user: {user.email}")
    else:
        user = User(
            email="demo@flowsense.com",
            hashed_password=hash_password("demo123"),
            full_name="Demo Administrator",
            role=UserRole.TENANT_ADMIN,
            tenant_id=tenant.id,
            enabled_modules=[
                "devices", "dashboards", "utility", "rules", "alerts",
                "health", "firmware", "analytics"
            ],
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"✓ Created demo user: {user.email} (Password: demo123)")
    
    return user

def get_or_create_device_type(db: Session, name: str, protocol: str, description: str = None):
    """Get or create a device type."""
    device_type = db.query(DeviceType).filter(DeviceType.name == name).first()
    if device_type:
        return device_type
    
    device_type = DeviceType(
        name=name,
        protocol=protocol,
        description=description or f"{name} device type"
    )
    db.add(device_type)
    db.commit()
    db.refresh(device_type)
    return device_type

def create_devices(db: Session, tenant: Tenant):
    """Create 15 realistic devices with proper names."""
    print("\nCreating 15 demo devices...")
    
    # Get or create device types
    smart_bench_type = get_or_create_device_type(db, "Smart Bench", "MQTT", "Smart bench with sensors and charging")
    smart_bin_type = get_or_create_device_type(db, "Smart Bin", "MQTT", "Smart waste bin with fill level sensors")
    digital_kiosk_type = get_or_create_device_type(db, "Digital Kiosk", "MQTT", "Digital information kiosk")
    lpg_meter_type = get_or_create_device_type(db, "LPG Meter", "HTTP", "LPG gas meter")
    gps_tracker_type = get_or_create_device_type(db, "GPS Tracker", "MQTT", "GPS tracking device")
    
    devices_data = [
        # Smart Benches (4 devices)
        {"device_id": "BENCH-CP-001", "name": "Central Park Main Entrance Bench", "type": smart_bench_type, "location": "Central Park, Main Entrance"},
        {"device_id": "BENCH-CP-002", "name": "Central Park Lake View Bench", "type": smart_bench_type, "location": "Central Park, Near Lake"},
        {"device_id": "BENCH-DT-001", "name": "Downtown Plaza East Bench", "type": smart_bench_type, "location": "Downtown Plaza, East Side"},
        {"device_id": "BENCH-RW-001", "name": "Riverside Walk North Bench", "type": smart_bench_type, "location": "Riverside Walk, North End"},
        
        # Smart Bins (5 devices)
        {"device_id": "BIN-MS-001", "name": "Main Street Block 1 Waste Bin", "type": smart_bin_type, "location": "Main Street, Block 1"},
        {"device_id": "BIN-SM-001", "name": "Shopping Mall Entrance Bin", "type": smart_bin_type, "location": "Shopping Mall, Main Entrance"},
        {"device_id": "BIN-CP-SG", "name": "Central Park South Gate Bin", "type": smart_bin_type, "location": "Central Park, South Gate"},
        {"device_id": "BIN-CP-NG", "name": "Central Park North Gate Bin", "type": smart_bin_type, "location": "Central Park, North Gate"},
        {"device_id": "BIN-RA-001", "name": "Residential Area Block A Bin", "type": smart_bin_type, "location": "Residential Block A"},
        
        # Digital Kiosks (3 devices)
        {"device_id": "KIOSK-CC-001", "name": "City Center Main Square Kiosk", "type": digital_kiosk_type, "location": "City Center, Main Square"},
        {"device_id": "KIOSK-TS-001", "name": "Central Train Station Kiosk", "type": digital_kiosk_type, "location": "Central Train Station"},
        {"device_id": "KIOSK-AP-001", "name": "International Airport Terminal 1 Kiosk", "type": digital_kiosk_type, "location": "International Airport, Terminal 1"},
        
        # LPG Meters (2 devices)
        {"device_id": "LPG-RA-101", "name": "Residential Block A Unit 101 LPG Meter", "type": lpg_meter_type, "location": "Residential Block A, Unit 101"},
        {"device_id": "LPG-CB-001", "name": "Commercial Building Floor 1 LPG Meter", "type": lpg_meter_type, "location": "Commercial Building, Floor 1"},
        
        # GPS Trackers (1 device)
        {"device_id": "GPS-FM-001", "name": "Fleet Management Vehicle #1", "type": gps_tracker_type, "location": "Fleet Management"},
    ]
    
    created_devices = []
    for device_info in devices_data:
        device = db.query(Device).filter(Device.device_id == device_info["device_id"]).first()
        if device:
            print(f"  Device {device_info['device_id']} already exists")
            created_devices.append(device)
            continue
        
        device = Device(
            device_id=device_info["device_id"],
            name=device_info["name"],
            device_type_id=device_info["type"].id,
            tenant_id=tenant.id,
            is_active=True,
            is_provisioned=True,
            device_metadata=json.dumps({
                "location": device_info["location"],
                "installation_date": (datetime.now() - timedelta(days=random.randint(30, 365))).isoformat()
            })
        )
        db.add(device)
        db.flush()
        
        # Create provisioning key
        key = ProvisioningKey(
            device_id=device.id,
            key=f"demo-key-{device_info['device_id'].lower()}",
            is_active=True
        )
        db.add(key)
        
        created_devices.append(device)
        print(f"  ✓ Created {device_info['device_id']}: {device_info['name']}")
    
    db.commit()
    print(f"\n✓ Created/updated {len(created_devices)} devices")
    return created_devices

def create_telemetry_data(db: Session, devices: list):
    """Create telemetry data to make the system look full."""
    print("\nCreating telemetry data...")
    
    now = datetime.now(timezone.utc)
    created_count = 0
    
    for device in devices:
        device_type_name = device.device_type.name if device.device_type else ""
        
        # Create latest telemetry
        latest_data = {}
        
        if "Smart Bench" in device_type_name:
            # Use same payload structure as Murabba smart_bench_sim.py
            seat1 = random.choice([True, False])
            seat2 = random.choice([True, False])
            seat3 = random.choice([True, False])
            latest_data = {
                "timestamp": now.isoformat() + "Z",
                "benchId": device.device_id,
                "location": {
                    "latitude": 24.7136,
                    "longitude": 46.6753,
                },
                "battery": {
                    "voltage": round(random.uniform(12.4, 12.8), 2),
                    "soc": random.randint(75, 90),
                    "solarPowerW": random.randint(100, 160),
                    "loadPowerW": random.randint(40, 70),
                },
                "occupancy": {
                    "seat1": seat1,
                    "seat2": seat2,
                    "seat3": seat3,
                    "total": sum([seat1, seat2, seat3]),
                },
                "charging": {
                    "usbActivePorts": random.randint(0, 4),
                    "wirelessActive": random.choice([True, False]),
                    "powerW": random.randint(0, 60),
                    "sessionsToday": random.randint(0, 40),
                },
                "environment": {
                    "pm25": random.randint(20, 80),
                    "pm10": random.randint(30, 100),
                    "co2": random.randint(600, 1200),
                    "temperature": round(random.uniform(30.0, 42.0), 1),
                    "humidity": random.randint(30, 70),
                },
                "system": {
                    "uptimeHours": random.randint(200, 300),
                    "cpuTemp": round(random.uniform(45.0, 65.0), 1),
                    "network": random.choice(["LTE", "5G", "WiFi"]),
                    "rssi": random.randint(-80, -60),
                },
            }
        elif "Smart Bin" in device_type_name:
            # Use same payload structure as Murabba smart_bin_sim.py
            timestamp_ms = int(now.timestamp() * 1000)
            hour = now.hour
            is_daytime = 6 <= hour <= 18
            last_cycle_hours_ago = random.randint(0, 24)
            last_cycle_time = now - timedelta(hours=last_cycle_hours_ago)
            
            latest_data = {
                "deviceId": device.device_id.lower().replace("-", "_"),  # e.g., "bin_ms_001"
                "timestamp": timestamp_ms,
                "fillLevel": {
                    "generalWaste": random.randint(50, 90),
                    "recyclables": random.randint(30, 60),
                    "organic": random.randint(20, 50)
                },
                "temperature": round(random.uniform(25.0, 35.0), 1),
                "fireAlert": random.random() < 0.01,  # 1% chance
                "movementAlert": random.random() < 0.05,  # 5% chance
                "battery": random.randint(75, 95),
                "solarPanel": {
                    "voltage": round(random.uniform(12.0, 13.5) if is_daytime else random.uniform(11.5, 12.2), 1),
                    "charging": is_daytime and random.random() > 0.2  # 80% chance during day
                },
                "compactionStatus": {
                    "lastCycleTime": last_cycle_time.isoformat() + "Z",
                    "ratio": random.randint(3, 7)
                },
                "odorControl": {
                    "status": random.choice(["active", "active", "active", "standby"]),  # Mostly active
                    "filterLifePercent": random.randint(60, 90)
                }
            }
        elif "Digital Kiosk" in device_type_name:
            latest_data = {
                "timestamp": now.isoformat(),
                "kioskId": device.device_id,
                "display": {
                    "status": "active",
                    "brightness": random.randint(70, 100)
                },
                "cpu_usage": round(random.uniform(20, 60), 1),
                "memory_usage": round(random.uniform(40, 75), 1),
                "network_status": "connected",
                "battery": round(random.uniform(50, 100), 1)
            }
        elif "LPG Meter" in device_type_name:
            latest_data = {
                "timestamp": now.isoformat(),
                "meterId": device.device_id,
                "level": round(random.uniform(10, 90), 1),
                "pressure": round(random.uniform(1.5, 2.8), 2),
                "temperature": round(random.uniform(20, 35), 1),
                "flow_rate": round(random.uniform(0.1, 2.5), 2)
            }
        elif "GPS Tracker" in device_type_name:
            latest_data = {
                "timestamp": now.isoformat(),
                "trackerId": device.device_id,
                "location": {
                    "latitude": round(random.uniform(24.6, 24.8), 6),
                    "longitude": round(random.uniform(46.6, 46.8), 6)
                },
                "speed": round(random.uniform(0, 80), 1),
                "heading": random.randint(0, 360),
                "battery": round(random.uniform(40, 100), 1),
                "signal_strength": random.randint(70, 100)
            }
        
        # Update or create TelemetryLatest
        latest = db.query(TelemetryLatest).filter(TelemetryLatest.device_id == device.id).first()
        if latest:
            latest.data = latest_data
            latest.event_timestamp = now
        else:
            latest = TelemetryLatest(
                device_id=device.id,
                data=latest_data,
                event_timestamp=now
            )
            db.add(latest)
        
        # Create recent time-series data for charts (last 60 minutes, every 5 minutes = 12 points)
        # This ensures charts have data to display
        for minute_offset in range(0, 60, 5):  # 0, 5, 10, 15, ..., 55 minutes ago
            reading_time = now - timedelta(minutes=minute_offset)
            
            # Create time-series points based on device type
            if "Smart Bench" in device_type_name:
                ts_points = [
                    ("environment.temperature", random.uniform(30.0, 42.0)),
                    ("environment.co2", random.randint(600, 1200)),
                    ("environment.pm25", random.randint(20, 80)),
                    ("battery.soc", random.uniform(75, 90)),
                    ("battery.voltage", random.uniform(12.4, 12.8)),
                    ("occupancy.total", random.randint(0, 3))
                ]
            elif "Smart Bin" in device_type_name:
                ts_points = [
                    ("fillLevel.generalWaste", random.randint(50, 90)),
                    ("fillLevel.recyclables", random.randint(30, 60)),
                    ("fillLevel.organic", random.randint(20, 50)),
                    ("temperature", random.uniform(25.0, 35.0)),
                    ("battery", random.randint(75, 95))
                ]
            elif "Digital Kiosk" in device_type_name:
                ts_points = [
                    ("cpu_usage", random.uniform(20, 60)),
                    ("memory_usage", random.uniform(40, 75)),
                    ("display.brightness", random.randint(70, 100))
                ]
            elif "LPG Meter" in device_type_name:
                ts_points = [
                    ("level", random.uniform(10, 90)),
                    ("pressure", random.uniform(1.5, 2.8)),
                    ("flow_rate", random.uniform(0.1, 2.5))
                ]
            elif "GPS Tracker" in device_type_name:
                ts_points = [
                    ("speed", random.uniform(0, 80)),
                    ("battery", random.uniform(40, 100)),
                    ("signal_strength", random.randint(70, 100))
                ]
            else:
                ts_points = []
            
            for key, value in ts_points:
                ts = TelemetryTimeseries(
                    device_id=device.id,
                    ts=reading_time,
                    key=key,
                    value=round(value, 2)
                )
                db.add(ts)
                created_count += 1
        
        # Also create time-series data for last 7 days (multiple readings per day) for longer history
        for day_offset in range(7):
            day_start = now - timedelta(days=day_offset)
            # Create 4 readings per day
            for hour_offset in [0, 6, 12, 18]:
                reading_time = day_start.replace(hour=hour_offset, minute=0, second=0, microsecond=0)
                
                # Create time-series points based on device type
                if "Smart Bench" in device_type_name:
                    ts_points = [
                        ("environment.temperature", random.uniform(30.0, 42.0)),
                        ("environment.co2", random.randint(600, 1200)),
                        ("environment.pm25", random.randint(20, 80)),
                        ("battery.soc", random.uniform(75, 90)),
                        ("battery.voltage", random.uniform(12.4, 12.8)),
                        ("occupancy.total", random.randint(0, 3))
                    ]
                elif "Smart Bin" in device_type_name:
                    ts_points = [
                        ("fillLevel.generalWaste", random.randint(50, 90)),
                        ("fillLevel.recyclables", random.randint(30, 60)),
                        ("fillLevel.organic", random.randint(20, 50)),
                        ("temperature", random.uniform(25.0, 35.0)),
                        ("battery", random.randint(75, 95))
                    ]
                elif "Digital Kiosk" in device_type_name:
                    ts_points = [
                        ("cpu_usage", random.uniform(20, 60)),
                        ("memory_usage", random.uniform(40, 75)),
                        ("display.brightness", random.randint(70, 100))
                    ]
                elif "LPG Meter" in device_type_name:
                    ts_points = [
                        ("level", random.uniform(10, 90)),
                        ("pressure", random.uniform(1.5, 2.8)),
                        ("flow_rate", random.uniform(0.1, 2.5))
                    ]
                elif "GPS Tracker" in device_type_name:
                    ts_points = [
                        ("speed", random.uniform(0, 80)),
                        ("battery", random.uniform(40, 100)),
                        ("signal_strength", random.randint(70, 100))
                    ]
                else:
                    ts_points = []
                
                for key, value in ts_points:
                    ts = TelemetryTimeseries(
                        device_id=device.id,
                        ts=reading_time,
                        key=key,
                        value=round(value, 2)
                    )
                    db.add(ts)
                    created_count += 1
        
        print(f"  ✓ Added telemetry for {device.device_id}")
    
    db.commit()
    print(f"\n✓ Created {created_count} time-series telemetry points")
    return created_count

def create_alert_rules(db: Session, tenant: Tenant, devices: list):
    """Create comprehensive alert rules."""
    print("\nCreating alert rules...")
    
    smart_benches = [d for d in devices if "BENCH" in d.device_id]
    smart_bins = [d for d in devices if "BIN" in d.device_id]
    kiosks = [d for d in devices if "KIOSK" in d.device_id]
    
    alert_rules = [
        {
            "name": "Low Battery Alert - Smart Benches",
            "description": "Alert when smart bench battery drops below 20%",
            "device_id": None,
            "tenant_id": tenant.id,
            "condition": {"field": "battery.soc", "operator": "<", "value": 20},
            "priority": AlertPriority.HIGH,
            "title_template": "Low Battery: {device_name}",
            "message_template": "Battery level is at {battery.soc}%. Please schedule maintenance.",
            "notify_email": True,
            "is_active": True
        },
        {
            "name": "High Temperature Alert",
            "description": "Alert when temperature exceeds 40°C",
            "device_id": None,
            "tenant_id": tenant.id,
            "condition": {"field": "environment.temperature", "operator": ">", "value": 40},
            "priority": AlertPriority.MEDIUM,
            "title_template": "High Temperature: {device_name}",
            "message_template": "Temperature is {environment.temperature}°C. Device may need cooling.",
            "is_active": True
        },
        {
            "name": "Bin Full Alert",
            "description": "Alert when bin fill level exceeds 90%",
            "device_id": None,
            "tenant_id": tenant.id,
            "condition": {"field": "fill_level", "operator": ">", "value": 90},
            "priority": AlertPriority.HIGH,
            "title_template": "Bin Full: {device_name}",
            "message_template": "Bin is {fill_level}% full. Collection needed.",
            "is_active": True
        },
        {
            "name": "Bin Overflow Alert",
            "description": "Critical alert when bin is completely full",
            "device_id": None,
            "tenant_id": tenant.id,
            "condition": {"field": "fill_level", "operator": ">=", "value": 100},
            "priority": AlertPriority.CRITICAL,
            "title_template": "URGENT: Bin Overflow - {device_name}",
            "message_template": "Bin is overflowing at {fill_level}%. Immediate collection required!",
            "escalation_enabled": True,
            "escalation_delay_minutes": 15,
            "escalation_priority": AlertPriority.CRITICAL,
            "is_active": True
        },
        {
            "name": "Device Offline Alert",
            "description": "Alert when device hasn't sent data in 30 minutes",
            "device_id": None,
            "tenant_id": tenant.id,
            "condition": {"field": "_last_seen_minutes", "operator": ">", "value": 30},
            "priority": AlertPriority.HIGH,
            "title_template": "Device Offline: {device_name}",
            "message_template": "Device has not sent data for {_last_seen_minutes} minutes.",
            "is_active": True
        },
        {
            "name": "Kiosk Display Error",
            "description": "Alert when kiosk reports display errors",
            "device_id": None,
            "tenant_id": tenant.id,
            "condition": {"field": "display.status", "operator": "==", "value": "error"},
            "priority": AlertPriority.MEDIUM,
            "title_template": "Display Error: {device_name}",
            "message_template": "Kiosk display is reporting errors. Technical support needed.",
            "is_active": True
        },
        {
            "name": "High CO2 Level Alert",
            "description": "Alert when air quality CO2 exceeds 800ppm",
            "device_id": None,
            "tenant_id": tenant.id,
            "condition": {"field": "environment.co2", "operator": ">", "value": 800},
            "priority": AlertPriority.MEDIUM,
            "title_template": "Poor Air Quality: {device_name}",
            "message_template": "CO2 level is {environment.co2}ppm. Air quality is poor.",
            "is_active": True
        },
        {
            "name": "LPG Meter Low Level",
            "description": "Alert when LPG meter level drops below 20%",
            "device_id": None,
            "tenant_id": tenant.id,
            "condition": {"field": "level", "operator": "<", "value": 20},
            "priority": AlertPriority.HIGH,
            "title_template": "Low LPG Level: {device_name}",
            "message_template": "LPG level is at {level}%. Refill needed soon.",
            "is_active": True
        },
    ]
    
    created_rules = []
    for rule_data in alert_rules:
        existing = db.query(AlertRule).filter(
            AlertRule.name == rule_data["name"],
            AlertRule.tenant_id == tenant.id
        ).first()
        if existing:
            print(f"  Alert rule '{rule_data['name']}' already exists")
            created_rules.append(existing)
            continue
        
        rule = AlertRule(**rule_data)
        db.add(rule)
        created_rules.append(rule)
        print(f"  ✓ Created alert rule: {rule_data['name']}")
    
    db.commit()
    print(f"\n✓ Created {len(created_rules)} alert rules")
    return created_rules

def create_device_rules(db: Session, devices: list):
    """Create device rules for automation."""
    print("\nCreating device rules...")
    
    created_rules = []
    
    # Rules for smart bins
    smart_bins = [d for d in devices if "BIN" in d.device_id]
    for bin_device in smart_bins[:3]:
        rule = db.query(DeviceRule).filter(
            DeviceRule.device_id == bin_device.id,
            DeviceRule.name == "Auto-schedule collection when full"
        ).first()
        
        if not rule:
            rule = DeviceRule(
                device_id=bin_device.id,
                name="Auto-schedule collection when full",
                description="Automatically schedule waste collection when bin reaches 90% capacity",
                priority=100,
                is_active=True,
                rule_type="event",
                condition={"field": "fill_level", "operator": ">=", "value": 90},
                action={
                    "type": "webhook",
                    "url": "https://api.flowsense.com/waste-collection/schedule",
                    "method": "POST",
                    "body": {
                        "device_id": bin_device.device_id,
                        "priority": "high",
                        "reason": "Bin reached capacity threshold"
                    }
                }
            )
            db.add(rule)
            created_rules.append(rule)
            print(f"  ✓ Created rule for {bin_device.device_id}: Auto-schedule collection")
    
    # Rules for smart benches
    smart_benches = [d for d in devices if "BENCH" in d.device_id]
    for bench in smart_benches[:2]:
        rule = db.query(DeviceRule).filter(
            DeviceRule.device_id == bench.id,
            DeviceRule.name == "Reduce power on low battery"
        ).first()
        
        if not rule:
            rule = DeviceRule(
                device_id=bench.id,
                name="Reduce power on low battery",
                description="Reduce charging power when battery drops below 30%",
                priority=80,
                is_active=True,
                rule_type="event",
                condition={"field": "battery.soc", "operator": "<", "value": 30},
                action={
                    "type": "device_command",
                    "command": {"action": "reduce_power", "charging_power": 5},
                    "topic": f"devices/{bench.device_id}/commands",
                    "qos": 1
                }
            )
            db.add(rule)
            created_rules.append(rule)
            print(f"  ✓ Created rule for {bench.device_id}: Reduce power on low battery")
    
    # Scheduled rule example
    if smart_bins:
        bin_device = smart_bins[0]
        rule = db.query(DeviceRule).filter(
            DeviceRule.device_id == bin_device.id,
            DeviceRule.name == "Daily health check"
        ).first()
        
        if not rule:
            rule = DeviceRule(
                device_id=bin_device.id,
                name="Daily health check",
                description="Run daily health diagnostics at 2 AM",
                priority=50,
                is_active=True,
                rule_type="scheduled",
                cron_schedule="0 2 * * *",
                condition={},
                action={"type": "device_command", "command": {"action": "run_diagnostics"}}
            )
            db.add(rule)
            created_rules.append(rule)
            print(f"  ✓ Created scheduled rule for {bin_device.device_id}: Daily health check")
    
    db.commit()
    print(f"\n✓ Created {len(created_rules)} device rules")
    return created_rules

def create_firmware_and_fota(db: Session, tenant: Tenant, devices: list, user: User):
    """Create firmware versions and FOTA jobs."""
    print("\nCreating firmware and FOTA jobs...")
    
    device_types = {}
    for device in devices:
        device_type_id = device.device_type_id
        if device_type_id not in device_types:
            device_types[device_type_id] = []
        device_types[device_type_id].append(device)
    
    created_firmwares = []
    created_jobs = []
    
    for device_type_id, type_devices in device_types.items():
        device_type = db.query(DeviceType).filter(DeviceType.id == device_type_id).first()
        if not device_type:
            continue
        
        # Create firmware
        firmware = db.query(Firmware).filter(
            Firmware.name == f"{device_type.name} Firmware",
            Firmware.device_type_id == device_type_id
        ).first()
        
        if not firmware:
            firmware = Firmware(
                name=f"{device_type.name} Firmware",
                device_type_id=device_type_id,
                description=f"Firmware for {device_type.name} devices"
            )
            db.add(firmware)
            db.flush()
            print(f"  ✓ Created firmware: {firmware.name}")
        
        # Create firmware versions
        versions = [
            {"version": "1.0.0", "is_recommended": False, "is_mandatory": False},
            {"version": "1.1.0", "is_recommended": True, "is_mandatory": False},
            {"version": "2.0.0", "is_recommended": False, "is_mandatory": False},
        ]
        
        firmware_versions = []
        for v_data in versions:
            version = db.query(FirmwareVersion).filter(
                FirmwareVersion.firmware_id == firmware.id,
                FirmwareVersion.version == v_data["version"]
            ).first()
            
            if not version:
                version = FirmwareVersion(
                    firmware_id=firmware.id,
                    version=v_data["version"],
                    file_path=f"/firmware/{device_type.name.lower().replace(' ', '_')}_v{v_data['version']}.bin",
                    checksum=f"sha256:{'a' * 64}",
                    file_size_bytes=1024 * 1024 * random.randint(1, 5),
                    release_notes=f"Version {v_data['version']} - Bug fixes and performance improvements",
                    is_recommended=v_data["is_recommended"],
                    is_mandatory=v_data["is_mandatory"]
                )
                db.add(version)
                firmware_versions.append(version)
                print(f"    ✓ Created version: {v_data['version']}")
            else:
                firmware_versions.append(version)
        
        db.flush()
        
        # Create FOTA jobs for some devices
        if firmware_versions and type_devices:
            recommended_version = next((v for v in firmware_versions if v.is_recommended), firmware_versions[-1])
            target_devices = type_devices[:min(3, len(type_devices))]
            
            # Create a scheduled job
            job = FOTAJob(
                name=f"{device_type.name} Firmware Update - {recommended_version.version}",
                tenant_id=tenant.id,
                firmware_version_id=recommended_version.id,
                status=FOTAJobStatus.SCHEDULED,
                scheduled_at=datetime.now() + timedelta(days=1),
                created_by_user_id=user.id
            )
            db.add(job)
            db.flush()
            
            # Create job device entries
            for device in target_devices:
                job_device = FOTAJobDevice(
                    job_id=job.id,
                    device_id=device.id,
                    status=FirmwareUpdateStatus.PENDING
                )
                db.add(job_device)
                
                # Set device firmware status
                dfs = db.query(DeviceFirmwareStatus).filter(
                    DeviceFirmwareStatus.device_id == device.id
                ).first()
                
                if not dfs:
                    dfs = DeviceFirmwareStatus(
                        device_id=device.id,
                        current_version="1.0.0",
                        target_version=recommended_version.version,
                        status=FirmwareUpdateStatus.PENDING
                    )
                    db.add(dfs)
            
            created_jobs.append(job)
            print(f"  ✓ Created FOTA job: {job.name} (targeting {len(target_devices)} devices)")
    
    db.commit()
    print(f"\n✓ Created {len(created_jobs)} FOTA jobs")
    return created_firmwares, created_jobs

def create_device_health_metrics(db: Session, devices: list):
    """Create device health metrics and history."""
    print("\nCreating device health metrics and history...")
    
    created_metrics = []
    created_history = 0
    
    for device in devices:
        # Create or update health metrics
        metric = db.query(DeviceHealthMetrics).filter(
            DeviceHealthMetrics.device_id == device.id
        ).first()
        
        battery_level = random.uniform(20, 95)
        battery_trend = random.choice(["stable", "decreasing", "increasing"])
        
        if not metric:
            metric = DeviceHealthMetrics(
                device_id=device.id,
                last_battery_level=battery_level,
                battery_trend=battery_trend,
                uptime_24h_percent=random.uniform(85, 99.9),
                uptime_7d_percent=random.uniform(90, 99.5),
                uptime_30d_percent=random.uniform(92, 99),
                connectivity_score=random.uniform(80, 100),
                message_count_24h=random.randint(100, 1000),
                message_count_7d=random.randint(700, 7000),
                avg_message_interval_seconds=random.uniform(60, 300),
                current_status=random.choice(["online", "online", "online", "degraded"]),
                last_seen_at=datetime.now(),
                first_seen_at=datetime.now() - timedelta(days=random.randint(30, 365))
            )
            db.add(metric)
            created_metrics.append(metric)
        
        # Create health history for battery trend (last 10 days, 1 snapshot per day)
        now = datetime.now(timezone.utc)
        base_battery = battery_level
        
        for day_offset in range(10):
            snapshot_time = now - timedelta(days=day_offset)
            # Vary battery level slightly day by day
            if battery_trend == "decreasing":
                day_battery = base_battery - (day_offset * random.uniform(0.5, 2.0))
            elif battery_trend == "increasing":
                day_battery = base_battery + (day_offset * random.uniform(0.5, 2.0))
            else:
                day_battery = base_battery + random.uniform(-1, 1)
            
            day_battery = max(0, min(100, day_battery))  # Clamp between 0-100
            
            # Check if history record already exists
            existing = db.query(DeviceHealthHistory).filter(
                DeviceHealthHistory.device_id == device.id,
                DeviceHealthHistory.snapshot_at >= snapshot_time - timedelta(hours=12),
                DeviceHealthHistory.snapshot_at <= snapshot_time + timedelta(hours=12)
            ).first()
            
            if not existing:
                history = DeviceHealthHistory(
                    device_id=device.id,
                    snapshot_at=snapshot_time,
                    status=random.choice(["online", "online", "online", "degraded"]),
                    battery_level=round(day_battery, 1),
                    message_count_1h=random.randint(10, 50),
                    avg_message_interval_seconds=random.uniform(60, 300),
                    uptime_24h_percent=random.uniform(85, 99.9),
                    connectivity_score=random.uniform(80, 100)
                )
                db.add(history)
                created_history += 1
        
        print(f"  ✓ Added health data for {device.device_id}")
    
    db.commit()
    print(f"✓ Created {len(created_metrics)} device health metrics and {created_history} history records")
    return created_metrics

def create_utility_billing(db: Session, tenant: Tenant, devices: list):
    """Create utility billing data (tariffs, contracts, consumption, invoices)."""
    print("\nCreating utility billing data...")
    
    # Create tariffs
    tariffs = []
    utility_kinds = [
        {"kind": "electricity", "rate": 0.12, "unit": "kWh"},
        {"kind": "gas", "rate": 0.08, "unit": "m3"},
        {"kind": "water", "rate": 0.05, "unit": "m3"}
    ]
    
    for util in utility_kinds:
        tariff = db.query(UtilityTariff).filter(
            UtilityTariff.utility_kind == util["kind"],
            UtilityTariff.name == f"Standard {util['kind'].title()} Tariff"
        ).first()
        
        if not tariff:
            tariff = UtilityTariff(
                name=f"Standard {util['kind'].title()} Tariff",
                utility_kind=util["kind"],
                rate_per_unit=util["rate"],
                currency="USD",
                is_active=True,
                notes=f"Standard rate for {util['kind']} consumption"
            )
            db.add(tariff)
            tariffs.append(tariff)
            print(f"  ✓ Created tariff: {tariff.name}")
        else:
            tariffs.append(tariff)
    
    db.flush()
    
    # Create contracts for LPG meters
    lpg_devices = [d for d in devices if "LPG" in d.device_id]
    created_contracts = []
    gas_tariff = next((t for t in tariffs if t.utility_kind == "gas"), None)
    
    if gas_tariff and lpg_devices:
        for device in lpg_devices:
            contract = db.query(UtilityDeviceContract).filter(
                UtilityDeviceContract.device_id == device.id
            ).first()
            
            if not contract:
                contract = UtilityDeviceContract(
                    tenant_id=tenant.id,
                    device_id=device.id,
                    utility_kind="gas",
                    tariff_id=gas_tariff.id,
                    contract_start=datetime.now() - timedelta(days=90)
                )
                db.add(contract)
                created_contracts.append(contract)
                print(f"  ✓ Created contract for {device.device_id}")
    
    db.flush()
    
    # Create consumption records for last 3 months
    created_consumption = 0
    if gas_tariff and lpg_devices:
        for device in lpg_devices:
            for month_offset in range(3):
                period_start = datetime.now() - timedelta(days=30 * (month_offset + 1))
                period_end = period_start + timedelta(days=30)
                
                consumption = db.query(UtilityConsumption).filter(
                    UtilityConsumption.device_id == device.id,
                    UtilityConsumption.period_start == period_start
                ).first()
                
                if not consumption:
                    start_index = random.uniform(10, 50)
                    end_index = start_index + random.uniform(20, 40)
                    consumption_value = end_index - start_index
                    
                    consumption = UtilityConsumption(
                        tenant_id=tenant.id,
                        device_id=device.id,
                        utility_kind="gas",
                        period_start=period_start,
                        period_end=period_end,
                        start_index=start_index,
                        end_index=end_index,
                        consumption=consumption_value,
                        unit="m3"
                    )
                    db.add(consumption)
                    created_consumption += 1
                    
                    # Create invoice
                    invoice = UtilityInvoice(
                        tenant_id=tenant.id,
                        device_id=device.id,
                        utility_kind="gas",
                        period_start=period_start,
                        period_end=period_end,
                        consumption=consumption_value,
                        unit="m3",
                        amount=round(consumption_value * gas_tariff.rate_per_unit, 2),
                        currency="USD",
                        status=random.choice(["draft", "issued", "paid"]),
                        tariff_snapshot={"rate_per_unit": gas_tariff.rate_per_unit, "name": gas_tariff.name}
                    )
                    db.add(invoice)
    
    db.commit()
    print(f"✓ Created {len(created_contracts)} contracts and {created_consumption} consumption records")
    return tariffs, created_contracts

def main():
    """Main function to create demo profile."""
    print("=" * 70)
    print("COMPREHENSIVE DEMO PROFILE SETUP")
    print("=" * 70)
    print()
    
    db = SessionLocal()
    
    try:
        # Create tenant
        tenant = create_demo_tenant(db)
        
        # Create user
        user = create_demo_user(db, tenant)
        
        # Create devices
        devices = create_devices(db, tenant)
        
        # Create telemetry data
        create_telemetry_data(db, devices)
        
        # Create alert rules
        alert_rules = create_alert_rules(db, tenant, devices)
        
        # Create device rules
        device_rules = create_device_rules(db, devices)
        
        # Create firmware and FOTA jobs
        firmwares, fota_jobs = create_firmware_and_fota(db, tenant, devices, user)
        
        # Create device health metrics
        health_metrics = create_device_health_metrics(db, devices)
        
        # Create utility billing
        tariffs, contracts = create_utility_billing(db, tenant, devices)
        
        # Note: Protocol distribution requires actual message flow through the system
        # The metrics collector tracks this in memory. To populate it, devices need to
        # send messages through the telemetry worker. For demo purposes, you can run
        # the simulation scripts to generate message activity.
        print("\n⚠️  Note: Protocol distribution cards will appear once devices send messages.")
        print("   Run simulation scripts to populate: scripts/smart_bench_sim.py, etc.")
        
        print("\n" + "=" * 70)
        print("DEMO PROFILE CREATED SUCCESSFULLY!")
        print("=" * 70)
        print(f"\nLogin Credentials:")
        print(f"  Email: demo@flowsense.com")
        print(f"  Password: demo123")
        print(f"\nSummary:")
        print(f"  • Tenant: {tenant.name}")
        print(f"  • Devices: {len(devices)}")
        print(f"  • Alert Rules: {len(alert_rules)}")
        print(f"  • Device Rules: {len(device_rules)}")
        print(f"  • FOTA Jobs: {len(fota_jobs)}")
        print(f"  • Health Metrics: {len(health_metrics)}")
        print(f"  • Utility Tariffs: {len(tariffs)}")
        print(f"  • Utility Contracts: {len(contracts)}")
        print(f"\nAll modules are enabled for the demo user.")
        print("The system is now populated with realistic data!")
        print("=" * 70)
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    main()
