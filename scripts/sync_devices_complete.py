#!/usr/bin/env python3
"""
Complete device sync script - fetches installations and telemetry,
builds complete device JSON, and sends to FlowSense.

Usage:
    python scripts/sync_devices_complete.py

Environment variables:
    FLOWSENSE_API_URL - FlowSense API base URL (default: http://localhost:5000)
    FLOWSENSE_API_KEY - External API key for authentication
    API_A_URL - Installations API URL
    API_B_URL - Telemetry API URL (SmartTive)
    API_B_KEY - Telemetry API key
"""
import asyncio
import aiohttp
import random
import string
import os
import sys
from datetime import datetime, timedelta

# ======================================
# CONFIG
# ======================================
API_A = os.getenv("API_A_URL", "https://flooddemo-qr2x.onrender.com/api/installations")
API_B = os.getenv("API_B_URL", "https://op1.smarttive.com/device/{}")
API_B_KEY = os.getenv("API_B_KEY", "M2nJ5vKt8QwR3pLxT0yZ7aDbU1sH6cYe")

FLOWSENSE_API_URL = os.getenv("FLOWSENSE_API_URL", "https://flowsense-772d.onrender.com")
FLOWSENSE_API_KEY = os.getenv("FLOWSENSE_API_KEY", "ext_DOxMY4SinUXk1kgud1LZTBh06QRQvIgPSTJzx4hIO6k")

CONCURRENCY = 200
SEM = asyncio.Semaphore(CONCURRENCY)

TENANT_ID = 2
TENANT_NAME = "Flowsense"

# ======================================
# HELPERS
# ======================================
def now():
    return datetime.utcnow().isoformat() + "Z"


def rand_float(a, b, r=2):
    return round(random.uniform(a, b), r)


def rand_int(a, b):
    return random.randint(a, b)


def rand_string(n=8):
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))


def random_history(value, points=3, spread=1.0):
    base = datetime.utcnow()
    return [
        {
            "timestamp": (base - timedelta(minutes=15 * i)).isoformat() + "Z",
            "value": round(value + random.uniform(-spread, spread), 2)
        }
        for i in reversed(range(points))
    ]


# ======================================
# LOCATION (STRICT PRIORITY)
# ======================================
def extract_location(install):
    # Priority 1: LocationCoordinates
    loc = install.get("LocationCoordinates") or install.get("locationCoordinates") or install.get("locationcoordinates") or {}
    if loc.get("latitude") and loc.get("longitude"):
        return loc.get("latitude"), loc.get("longitude")
    
    # Priority 2: userLatitude/userLongitude
    if install.get("userLatitude") and install.get("userLongitude"):
        return install.get("userLatitude"), install.get("userLongitude")
    
    # Also check usercoordinates
    user_coords = install.get("userCoordinates") or install.get("usercoordinates") or {}
    if isinstance(user_coords, dict):
        if user_coords.get("latitude") and user_coords.get("longitude"):
            return user_coords.get("latitude"), user_coords.get("longitude")
        if user_coords.get("lat") and user_coords.get("lon"):
            return user_coords.get("lat"), user_coords.get("lon")
    
    return None, None


# ======================================
# FLATTEN TELEMETRY
# ======================================
def flatten_dict(d, parent="", out=None):
    if out is None:
        out = {}
    for k, v in d.items():
        key = f"{parent}.{k}" if parent else k
        if isinstance(v, dict):
            flatten_dict(v, key, out)
        else:
            out[key] = v
    return out


# ======================================
# FETCH TELEMETRY (API B)
# ======================================
async def fetch_telemetry(session, device_id):
    async with SEM:
        try:
            async with session.get(
                API_B.format(device_id.upper()),
                headers={"X-API-KEY": API_B_KEY},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as r:
                if r.status != 200:
                    return {}
                data = await r.json()
                return flatten_dict(data)
        except Exception as e:
            print(f"  ⚠ Failed to fetch telemetry for {device_id}: {e}")
            return {}


# ======================================
# BUILD DEVICE OBJECT
# ======================================
def build_device(install, telemetry):
    device_id = str(
        install.get("deviceId")
        or install.get("device_id")
        or rand_string(16)
    )

    name = (
        install.get("deviceName")
        or install.get("name")
        or f"HTTP Device {device_id}"
    )

    lat, lng = extract_location(install)

    level = telemetry.get("level", rand_float(20, 90))
    temperature = telemetry.get("temperature", rand_float(15, 40))
    battery = telemetry.get("battery", rand_int(40, 100))
    pressure = telemetry.get("pressure", rand_float(1.5, 2.5))
    dis_cm = telemetry.get("dis_cm", rand_float(10, 80))

    return {
        # ======================================
        # CORE
        # ======================================
        "device_id": device_id,
        "name": name,
        "device_type": {
            "id": 1,
            "name": "HTTP Device",
            "protocol": "HTTP",
            "description": "HTTP telemetry device"
        },
        "tenant_id": TENANT_ID,
        "tenant_name": TENANT_NAME,
        "is_active": True,
        "is_provisioned": True,

        # ======================================
        # LOCATION
        # ======================================
        "location": {
            "latitude": lat,
            "longitude": lng,
            "address": None,
            "accuracy": rand_float(5, 25) if lat else None,
            "source": "gps" if lat else None,
            "updated_at": now()
        },

        # ======================================
        # TELEMETRY
        # ======================================
        "telemetry": {
            "timestamp": now(),
            "updated_at": now(),
            "data": telemetry or {
                "level": level,
                "temperature": temperature,
                "pressure": pressure,
                "battery": battery,
                "dis_cm": dis_cm
            }
        },

        # ======================================
        # HISTORY
        # ======================================
        "history": {
            "level": random_history(level),
            "temperature": random_history(temperature),
            "battery": random_history(battery),
            "pressure": random_history(pressure),
            "dis_cm": random_history(dis_cm)
        },

        # ======================================
        # FIELDS
        # ======================================
        "fields": [
            {"key": "level", "display_name": "Level", "field_type": "number", "unit": "%", "sample_value": level},
            {"key": "temperature", "display_name": "Temperature", "field_type": "number", "unit": "°C", "sample_value": temperature},
            {"key": "battery", "display_name": "Battery", "field_type": "number", "unit": "%", "sample_value": battery},
            {"key": "pressure", "display_name": "Pressure", "field_type": "number", "unit": "bar", "sample_value": pressure},
            {"key": "dis_cm", "display_name": "Dis Cm", "field_type": "number", "unit": "cm", "sample_value": dis_cm}
        ],

        # ======================================
        # DASHBOARD (BASIC)
        # ======================================
        "dashboard": {
            "widgets": [
                {"id": "level-gauge", "type": "gauge", "field": "level", "title": "Level", "unit": "%", "min": 0, "max": 100},
                {"id": "temp-thermo", "type": "thermometer", "field": "temperature", "title": "Temperature", "unit": "°C", "min": -20, "max": 50},
                {"id": "battery", "type": "battery", "field": "battery", "title": "Battery", "min": 0, "max": 100}
            ],
            "layout": "grid"
        },

        # ======================================
        # HEALTH
        # ======================================
        "health": {
            "status": "online",
            "last_seen_at": now(),
            "battery": {
                "level": battery,
                "trend": "stable"
            }
        },

        # ======================================
        # METADATA
        # ======================================
        "metadata": {
            "installation_id": install.get("installationId") or install.get("id"),
            "source": "external_installations_api"
        },

        "created_at": now(),
        "updated_at": now()
    }


# ======================================
# SEND TO FLOWSENSE
# ======================================
async def send_to_flowsense(session, device_data):
    """Send complete device data to FlowSense API."""
    if not FLOWSENSE_API_KEY:
        print("⚠ FLOWSENSE_API_KEY not set, skipping send to FlowSense")
        return False
    
    url = f"{FLOWSENSE_API_URL}/api/v1/external/devices/complete"
    headers = {
        "X-API-Key": FLOWSENSE_API_KEY,
        "Content-Type": "application/json"
    }
    
    try:
        async with session.post(url, json=device_data, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as r:
            if r.status in [200, 201]:
                return True
            else:
                text = await r.text()
                print(f"  ✗ Failed to send {device_data['device_id']}: HTTP {r.status} - {text[:200]}")
                return False
    except Exception as e:
        print(f"  ✗ Error sending {device_data['device_id']}: {e}")
        return False


# ======================================
# MAIN PIPELINE
# ======================================
async def main():
    if not FLOWSENSE_API_KEY:
        print("⚠ Warning: FLOWSENSE_API_KEY not set. Devices will be built but not sent to FlowSense.")
        print("   Set FLOWSENSE_API_KEY environment variable to enable sending.")
    
    async with aiohttp.ClientSession() as session:
        print(f"📥 Fetching installations from {API_A}...")
        async with session.get(API_A) as r:
            if r.status != 200:
                print(f"✗ Failed to fetch installations: HTTP {r.status}")
                return
            installations = await r.json()
        
        print(f"✅ Found {len(installations)} installations")
        
        # Process devices
        tasks = []
        for install in installations:
            device_id = install.get("deviceId") or install.get("device_id")
            if not device_id:
                continue

            async def process(install=install, device_id=device_id):
                telemetry = await fetch_telemetry(session, device_id)
                device_data = build_device(install, telemetry)
                
                # Send to FlowSense if API key is set
                if FLOWSENSE_API_KEY:
                    success = await send_to_flowsense(session, device_data)
                    return device_data, success
                else:
                    return device_data, None

            tasks.append(process())

        print(f"🔄 Processing {len(tasks)} devices (concurrency: {CONCURRENCY})...")
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count results
        devices = []
        success_count = 0
        fail_count = 0
        skip_count = 0
        
        for result in results:
            if isinstance(result, Exception):
                print(f"  ✗ Error: {result}")
                fail_count += 1
                continue
            
            device_data, success = result
            devices.append(device_data)
            
            if success is True:
                success_count += 1
            elif success is False:
                fail_count += 1
            else:
                skip_count += 1
        
        print(f"\n{'='*60}")
        print(f"✅ Processed {len(devices)} devices")
        if FLOWSENSE_API_KEY:
            print(f"   ✓ Successfully sent: {success_count}")
            print(f"   ✗ Failed to send: {fail_count}")
        else:
            print(f"   ⚠ Skipped sending (no API key): {skip_count}")
        print(f"{'='*60}")
        
        return devices


# ======================================
# RUN
# ======================================
if __name__ == "__main__":
    try:
        devices = asyncio.run(main())
        if devices and not FLOWSENSE_API_KEY:
            print(f"\n💡 Tip: Set FLOWSENSE_API_KEY to send {len(devices)} devices to FlowSense")
    except KeyboardInterrupt:
        print("\n⚠ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

