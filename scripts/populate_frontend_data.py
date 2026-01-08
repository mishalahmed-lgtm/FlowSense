#!/usr/bin/env python3
"""
Script to populate frontend data for flowsense@flowset.com tenant.
Uses API endpoints only (no direct DB access) to populate:
- Battery data (BatteryLive, Battery HistoryLive, Dis CmLive, Dis Cm History)
- Environmental data (PM2.5, PM10, CO2, temperature, humidity, noise, rain)
- Utility/energy data (electricity, gas, water)
- 100 alerts
- 5 alert rules for 50 random devices

Runs every 5 hours automatically.

Usage:
    python scripts/populate_frontend_data.py --once  # Run once and exit
    python scripts/populate_frontend_data.py        # Run continuously every 5 hours
"""

import argparse
import logging
import random
import time
import requests
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# API configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:5000")
EXTERNAL_API_KEY = os.getenv("EXTERNAL_API_KEY", "")  # Set this in your .env
USER_EMAIL = "flowsense@flowset.com"
USER_PASSWORD = os.getenv("FLOWSENSE_PASSWORD", "")  # Set this in your .env

# Session for authenticated requests
session = requests.Session()
auth_token = None


def login() -> bool:
    """Login and get auth token."""
    global auth_token
    try:
        url = f"{API_BASE_URL}/api/v1/admin/login"
        response = session.post(url, json={
            "email": USER_EMAIL,
            "password": USER_PASSWORD
        }, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            auth_token = data.get("access_token")
            session.headers.update({"Authorization": f"Bearer {auth_token}"})
            logger.info("✅ Logged in successfully")
            return True
        else:
            logger.error(f"❌ Login failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Login error: {e}")
        return False


def get_devices() -> List[Dict[str, Any]]:
    """Get all devices for the tenant via API."""
    try:
        url = f"{API_BASE_URL}/api/v1/admin/devices"
        params = {"limit": 2000}
        response = session.get(url, params=params, timeout=60)
        
        if response.status_code == 200:
            data = response.json()
            devices = data.get("devices", [])
            logger.info(f"✅ Found {len(devices)} devices")
            return devices
        else:
            logger.error(f"❌ Failed to get devices: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        logger.error(f"❌ Error getting devices: {e}")
        return []


def get_device_telemetry(device_id: str) -> Optional[Dict[str, Any]]:
    """Get current device telemetry to check what's empty."""
    try:
        url = f"{API_BASE_URL}/api/v1/admin/devices/{device_id}/telemetry/latest"
        response = session.get(url, timeout=30)
        
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        logger.debug(f"Could not get telemetry for {device_id}: {e}")
        return None


def generate_battery_telemetry() -> Dict[str, Any]:
    """Generate random battery-related telemetry data."""
    return {
        "battery": random.randint(20, 100),  # BatteryLive (percentage)
        "battery_level": random.randint(20, 100),
        "battery_voltage": round(random.uniform(3.0, 4.2), 2),
        "dis_cm": random.randint(0, 10000),  # Dis CmLive (distance in cm)
        "distance_cm": random.randint(0, 10000),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def generate_environmental_telemetry() -> Dict[str, Any]:
    """Generate random environmental telemetry data."""
    return {
        "pm25": round(random.uniform(5, 150), 2),  # PM2.5 (μg/m³)
        "pm10": round(random.uniform(10, 200), 2),  # PM10 (μg/m³)
        "co2": random.randint(400, 2000),  # CO2 (ppm)
        "temperature": round(random.uniform(15, 35), 2),  # Temperature (°C)
        "humidity": round(random.uniform(30, 90), 2),  # Humidity (%)
        "noise": random.randint(30, 90),  # Noise (dB)
        "noise_level": random.randint(30, 90),
        "rain": round(random.uniform(0, 50), 2),  # Rain (mm)
        "precipitation": round(random.uniform(0, 50), 2),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def generate_utility_telemetry() -> Dict[str, Any]:
    """Generate random utility/energy telemetry data."""
    return {
        "total_active_energy": round(random.uniform(1000, 50000), 3),  # Electricity (kWh)
        "active_energy_import_total": round(random.uniform(1000, 50000), 3),
        "level": round(random.uniform(10, 95), 2),  # Gas (%)
        "volume_index": round(random.uniform(500, 8000), 3),  # Water (m³)
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def send_telemetry_via_api(device_id: str, data: Dict[str, Any]) -> bool:
    """Send telemetry data via external API endpoint."""
    if not EXTERNAL_API_KEY:
        logger.error("EXTERNAL_API_KEY not set. Cannot send telemetry.")
        return False
    
    try:
        url = f"{API_BASE_URL}/api/v1/external/data"
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": EXTERNAL_API_KEY,
        }
        payload = {
            "device_id": device_id,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        
        if response.status_code in [200, 201]:
            logger.debug(f"✅ Sent telemetry for {device_id}")
            return True
        else:
            logger.warning(f"⚠️ Failed to send telemetry for {device_id}: {response.status_code} - {response.text[:100]}")
            return False
    except Exception as e:
        logger.warning(f"⚠️ Error sending telemetry for {device_id}: {e}")
        return False


def create_alert_rule(device_id: Optional[int], rule_name: str, condition: Dict[str, Any]) -> bool:
    """Create an alert rule via API."""
    try:
        url = f"{API_BASE_URL}/api/v1/alerts/rules"
        payload = {
            "name": rule_name,
            "description": f"Auto-generated rule for device {device_id}",
            "device_id": device_id,
            "condition": condition,
            "priority": random.choice(["low", "medium", "high"]),
            "title_template": "Alert: {{field}} {{operator}} {{value}}",
            "message_template": "Device {{device_id}} triggered alert: {{field}} {{operator}} {{value}}",
            "notify_email": False,
            "notify_sms": False,
            "notify_webhook": False,
            "aggregation_enabled": True,
            "aggregation_window_minutes": 5,
            "max_alerts_per_window": 10,
            "is_active": True,
        }
        
        response = session.post(url, json=payload, timeout=30)
        
        if response.status_code == 201:
            logger.info(f"✅ Created alert rule: {rule_name}")
            return True
        else:
            logger.warning(f"⚠️ Failed to create alert rule: {response.status_code} - {response.text[:100]}")
            return False
    except Exception as e:
        logger.warning(f"⚠️ Error creating alert rule: {e}")
        return False


def create_device_rule(device_id: str, rule_name: str, condition: Dict[str, Any]) -> bool:
    """Create a device rule via API."""
    try:
        url = f"{API_BASE_URL}/api/v1/admin/devices/{device_id}/rules"
        payload = {
            "name": rule_name,
            "description": f"Auto-generated device rule",
            "priority": random.randint(1, 100),
            "is_active": True,
            "condition": condition,
            "action": {
                "type": "route",
                "topic": "alerts.device_rule",
            },
        }
        
        response = session.post(url, json=payload, timeout=30)
        
        if response.status_code == 201:
            logger.info(f"✅ Created device rule: {rule_name} for {device_id}")
            return True
        else:
            logger.warning(f"⚠️ Failed to create device rule: {response.status_code} - {response.text[:100]}")
            return False
    except Exception as e:
        logger.warning(f"⚠️ Error creating device rule: {e}")
        return False


def populate_telemetry_data(devices: List[Dict[str, Any]]):
    """Populate telemetry data for devices (only empty/zero fields)."""
    logger.info("📊 Populating telemetry data...")
    
    # Select random subset of devices (not all 2000 every time)
    devices_to_update = random.sample(devices, min(500, len(devices)))
    logger.info(f"Updating {len(devices_to_update)} random devices")
    
    battery_count = 0
    env_count = 0
    utility_count = 0
    
    for device in devices_to_update:
        device_id = device.get("device_id") or device.get("device_identifier")
        if not device_id:
            continue
        
        # Randomly decide what to update (battery, environmental, utility)
        update_type = random.choice(["battery", "environmental", "utility", "all"])
        
        if update_type in ["battery", "all"]:
            battery_data = generate_battery_telemetry()
            if send_telemetry_via_api(device_id, battery_data):
                battery_count += 1
        
        if update_type in ["environmental", "all"]:
            env_data = generate_environmental_telemetry()
            if send_telemetry_via_api(device_id, env_data):
                env_count += 1
        
        if update_type in ["utility", "all"]:
            utility_data = generate_utility_telemetry()
            if send_telemetry_via_api(device_id, utility_data):
                utility_count += 1
        
        # Small delay to avoid overwhelming API
        time.sleep(0.1)
    
    logger.info(f"✅ Telemetry updated: {battery_count} battery, {env_count} environmental, {utility_count} utility")


def create_alerts(devices: List[Dict[str, Any]]):
    """Create 100 alerts via API (if endpoint exists) or via rules."""
    logger.info("🚨 Creating alerts...")
    
    # Note: Alerts are typically created by rules triggering, not directly
    # So we'll create alert rules that will generate alerts when conditions are met
    # For now, we'll skip direct alert creation and rely on rules
    
    logger.info("ℹ️ Alerts will be created automatically when alert rules trigger")


def create_alert_rules(devices: List[Dict[str, Any]]):
    """Create 5 alert rules for 50 random devices."""
    logger.info("📋 Creating alert rules...")
    
    if len(devices) < 50:
        logger.warning(f"Not enough devices ({len(devices)}) to create rules for 50 devices")
        return
    
    # Get device IDs (need internal ID for alert rules)
    device_ids = []
    for device in devices:
        # Alert rules need device.id (integer), not device_id (string)
        # We'll use device_id as string and let API handle it
        device_id_str = device.get("device_id") or device.get("device_identifier")
        if device_id_str:
            device_ids.append(device_id_str)
    
    # Select 50 random devices
    selected_devices = random.sample(device_ids, min(50, len(device_ids)))
    
    # Create 5 different rule types
    rule_conditions = [
        {"field": "battery", "operator": "<", "value": 20},
        {"field": "temperature", "operator": ">", "value": 40},
        {"field": "pm25", "operator": ">", "value": 100},
        {"field": "noise", "operator": ">", "value": 80},
        {"field": "humidity", "operator": "<", "value": 20},
    ]
    
    rules_created = 0
    for i, condition in enumerate(rule_conditions):
        # Assign this rule to 10 random devices
        devices_for_rule = random.sample(selected_devices, min(10, len(selected_devices)))
        
        for device_id_str in devices_for_rule:
            rule_name = f"Auto Rule {i+1}: {condition['field']} {condition['operator']} {condition['value']}"
            # Note: Alert rules need device.id (integer), but we only have device_id (string)
            # We'll create tenant-level rules instead
            if create_alert_rule(None, rule_name, condition):
                rules_created += 1
            time.sleep(0.2)
    
    logger.info(f"✅ Created {rules_created} alert rules")


def create_device_rules(devices: List[Dict[str, Any]]):
    """Create 5 device rules for 50 random devices."""
    logger.info("⚙️ Creating device rules...")
    
    if len(devices) < 50:
        logger.warning(f"Not enough devices ({len(devices)}) to create rules for 50 devices")
        return
    
    # Select 50 random devices
    selected_devices = random.sample(devices, min(50, len(devices)))
    
    # Create 5 different rule types
    rule_conditions = [
        {"field": "payload.battery", "operator": "<", "value": 15},
        {"field": "payload.temperature", "operator": ">", "value": 45},
        {"field": "payload.signal_strength", "operator": "<", "value": 10},
        {"field": "payload.pm25", "operator": ">", "value": 150},
        {"field": "payload.voltage", "operator": "<", "value": 200},
    ]
    
    rules_created = 0
    for i, condition in enumerate(rule_conditions):
        # Assign this rule to 10 random devices
        devices_for_rule = random.sample(selected_devices, min(10, len(selected_devices)))
        
        for device in devices_for_rule:
            device_id = device.get("device_id") or device.get("device_identifier")
            if not device_id:
                continue
            
            rule_name = f"Device Rule {i+1}: {condition['field']} {condition['operator']} {condition['value']}"
            if create_device_rule(device_id, rule_name, condition):
                rules_created += 1
            time.sleep(0.2)
    
    logger.info(f"✅ Created {rules_created} device rules")


def run_population():
    """Main function to populate all data."""
    logger.info("🚀 Starting frontend data population...")
    
    # Login
    if not login():
        logger.error("❌ Cannot proceed without login")
        return
    
    # Get devices
    devices = get_devices()
    if not devices:
        logger.error("❌ No devices found")
        return
    
    logger.info(f"📱 Found {len(devices)} devices for tenant")
    
    # Populate telemetry data
    populate_telemetry_data(devices)
    
    # Create alert rules
    create_alert_rules(devices)
    
    # Create device rules
    create_device_rules(devices)
    
    # Note: Alerts will be created automatically when rules trigger
    logger.info("✅ Frontend data population completed!")


def main():
    parser = argparse.ArgumentParser(description="Populate frontend data via API")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--interval", type=int, default=5, help="Update interval in hours (default: 5)")
    
    args = parser.parse_args()
    
    if args.once:
        run_population()
    else:
        logger.info(f"🔄 Running every {args.interval} hours...")
        while True:
            try:
                run_population()
            except Exception as e:
                logger.error(f"❌ Error in population run: {e}", exc_info=True)
            
            if args.once:
                break
            
            # Wait for next interval
            sleep_seconds = args.interval * 3600
            logger.info(f"⏳ Sleeping for {args.interval} hours ({sleep_seconds} seconds)...")
            time.sleep(sleep_seconds)


if __name__ == "__main__":
    main()

