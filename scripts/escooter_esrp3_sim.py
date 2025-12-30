#!/usr/bin/env python3
"""
E-Scooter MQTT telemetry simulator for ES-RP-3.

Publishes JSON telemetry matching the emscooter format.
"""

import json
import os
import random
import time
from datetime import datetime

import paho.mqtt.client as mqtt


# Configuration
DEVICE_ID = os.environ.get("DEVICE_ID", "ES-RP-3")
MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1884"))
MQTT_TOPIC = os.environ.get("MQTT_TOPIC", f"device/{DEVICE_ID}/telemetry")
MQTT_QOS = int(os.environ.get("MQTT_QOS", "0"))

# Access token used for secure telemetry ingestion (must match device metadata)
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN", "murraba")

SEND_INTERVAL_SECONDS = int(os.environ.get("SEND_INTERVAL_SECONDS", "60"))

# Location (Murabba, Riyadh coordinates) - ES-RP-3
BASE_LAT = float(os.environ.get("LAT", "24.6500"))
BASE_LNG = float(os.environ.get("LNG", "46.7100"))


def build_payload() -> dict:
    """Build a telemetry payload matching emscooter format."""
    now = datetime.utcnow()
    timestamp_ms = int(now.timestamp() * 1000)
    
    # Location with slight variation (simulating movement)
    lat_offset = random.uniform(-0.001, 0.001)
    lng_offset = random.uniform(-0.001, 0.001)
    current_lat = BASE_LAT + lat_offset
    current_lng = BASE_LNG + lng_offset
    
    # Speed varies between 0-25 kmph
    speed = round(random.uniform(0, 25), 1)
    
    # Battery gradually decreases but can increase if charging
    battery = max(20, min(100, random.uniform(50, 80)))
    
    # Battery health slowly degrades over time
    battery_health = max(80, min(100, random.uniform(85, 95)))
    
    # Lock status - mostly unlocked when in use
    is_locked = random.random() < 0.3  # 30% chance locked
    
    # Trip active if speed > 0
    trip_active = speed > 0.5
    
    # Trip distance accumulates if trip is active
    trip_distance = round(random.uniform(0, 5), 2) if trip_active else 0.0
    
    # Motor temperature increases with speed
    motor_temp = round(25 + (speed * 0.5) + random.uniform(-2, 2), 1)
    
    payload = {
        "deviceId": DEVICE_ID,
        "timestamp": timestamp_ms,
        "latitude": current_lat,  # Top-level for map compatibility
        "longitude": current_lng,  # Top-level for map compatibility
        "location": {
            "lat": current_lat,
            "lng": current_lng,
        },
        "speed_kmh": speed,
        "battery_percent": round(battery, 1),
        "battery_health_percent": round(battery_health, 1),
        "is_locked": is_locked,
        "trip_active": trip_active,
        "trip_distance_km": trip_distance,
        "motor_temperature_c": motor_temp,
        # Access token for backend authentication
        "access_token": ACCESS_TOKEN,
    }
    
    return payload


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[MQTT] Connected to {MQTT_HOST}:{MQTT_PORT}")
    else:
        print(f"[MQTT] Failed to connect, rc={rc}")


def main():
    print(f"E-Scooter simulator starting for device: {DEVICE_ID}")
    print(f"Broker: {MQTT_HOST}:{MQTT_PORT}")
    print(f"Topic:  {MQTT_TOPIC}")
    print(f"Interval: {SEND_INTERVAL_SECONDS} seconds\n")

    client = mqtt.Client()
    client.on_connect = on_connect

    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_start()

    try:
        while True:
            payload = build_payload()
            payload_str = json.dumps(payload)

            result = client.publish(MQTT_TOPIC, payload_str, qos=MQTT_QOS)
            status = result[0]

            now = datetime.utcnow().isoformat() + "Z"
            if status == mqtt.MQTT_ERR_SUCCESS:
                print(f"[{now}] Published to {MQTT_TOPIC}")
                print(f"  Speed: {payload['speed_kmh']} km/h, Battery: {payload['battery_percent']}%, Locked: {payload['is_locked']}")
            else:
                print(f"[{now}] FAILED to publish, status={status}")

            time.sleep(SEND_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("E-Scooter simulator interrupted, shutting down...")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()



