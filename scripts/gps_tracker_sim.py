#!/usr/bin/env python3
"""
GPS Tracker simulator for device GPS-TRUCK-001.

- Logs in to the admin API using the configured admin email/password.
- Looks up the provisioning key for GPS-TRUCK-001.
- Sends HTTP telemetry every 30 seconds with GPS coordinates and speed.
- Simulates a truck moving around a city area.
"""

import os
import random
import time

import requests


API_BASE = os.environ.get("IOT_API_BASE", "http://localhost:5000/api/v1")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
DEVICE_ID = os.environ.get("GPS_DEVICE_ID", "GPS-TRUCK-001")
INTERVAL = int(os.environ.get("GPS_INTERVAL", "30"))  # seconds

# Starting location (example: somewhere in a city)
START_LAT = 40.7128  # New York City latitude
START_LON = -74.0060  # New York City longitude


def get_admin_token() -> str:
    """Authenticate as admin and return JWT access token."""
    resp = requests.post(
        f"{API_BASE}/admin/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=5,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["access_token"]


def get_device_key(token: str, device_id: str) -> str:
    """Fetch provisioning key for the given device_id via admin API."""
    resp = requests.get(
        f"{API_BASE}/admin/devices",
        headers={"Authorization": f"Bearer {token}"},
        timeout=5,
    )
    resp.raise_for_status()
    devices = resp.json()
    for dev in devices:
        if dev.get("device_id") == device_id:
            provisioning = dev.get("provisioning_key") or {}
            key = provisioning.get("key")
            if not key:
                raise RuntimeError(f"Device {device_id} has no provisioning key.")
            return key
    raise RuntimeError(f"Device {device_id} not found.")


def send_telemetry(device_id: str, key: str, payload: dict):
    """Send telemetry via HTTP endpoint."""
    resp = requests.post(
        f"{API_BASE}/telemetry/http",
        json=payload,
        headers={"X-Device-Key": key},
        timeout=5,
    )
    resp.raise_for_status()
    return resp.status_code == 202


def main():
    print(f"🚛 GPS Tracker Simulator for {DEVICE_ID}")
    print(f"   API Base: {API_BASE}")
    
    # Get admin token and device key
    print("   Authenticating as admin...")
    token = get_admin_token()
    print("   ✓ Admin authenticated")
    
    print(f"   Fetching provisioning key for {DEVICE_ID}...")
    device_key = get_device_key(token, DEVICE_ID)
    print(f"   ✓ Provisioning key obtained")
    
    # Initialize GPS position
    lat = START_LAT
    lon = START_LON
    speed = random.uniform(0.0, 60.0)  # km/h
    
    print(f"\n📍 Starting location: {lat:.6f}, {lon:.6f}")
    print(f"📡 Starting telemetry transmission (every {INTERVAL} seconds)...")
    
    message_count = 0
    try:
        while True:
            # Simulate movement (random walk with some direction)
            # Move in a roughly north-east direction with some randomness
            lat_delta = random.uniform(-0.001, 0.002)  # ~100-200m per update
            lon_delta = random.uniform(-0.001, 0.002)
            
            lat += lat_delta
            lon += lon_delta
            
            # Update speed (simulate traffic)
            speed = max(0.0, min(80.0, speed + random.uniform(-5.0, 10.0)))
            
            # Create payload (must be wrapped in 'data' field)
            payload = {
                "data": {
                    "latitude": round(lat, 6),
                    "longitude": round(lon, 6),
                    "speed": round(speed, 2),
                }
            }
            
            # Send telemetry
            try:
                send_telemetry(DEVICE_ID, device_key, payload)
                message_count += 1
                print(
                    f"   [{message_count}] Sent: lat={lat:.6f}, lon={lon:.6f}, speed={speed:.1f} km/h"
                )
            except Exception as e:
                print(f"   ✗ Failed to send telemetry: {e}")
            
            time.sleep(INTERVAL)
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping simulator...")
        print("   ✓ Simulator stopped")


if __name__ == "__main__":
    main()

