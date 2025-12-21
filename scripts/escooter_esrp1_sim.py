#!/usr/bin/env python3
"""
E-Scooter MQTT telemetry simulator for ES-RP-1.

Publishes JSON telemetry matching the emscooter_01 format.
"""

import json
import os
import random
import time
from datetime import datetime

import paho.mqtt.client as mqtt


# Configuration
DEVICE_ID = os.environ.get("DEVICE_ID", "ES-RP-1")
MQTT_HOST = os.environ.get("MQTT_HOST", "mqtt-broker")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_TOPIC = os.environ.get("MQTT_TOPIC", f"device/{DEVICE_ID}/telemetry")
MQTT_QOS = int(os.environ.get("MQTT_QOS", "0"))
SEND_INTERVAL_SECONDS = int(os.environ.get("SEND_INTERVAL_SECONDS", "60"))

# Location (Riyadh coordinates)
LAT = float(os.environ.get("LAT", "24.8607"))
LNG = float(os.environ.get("LNG", "67.0011"))


def build_payload() -> dict:
    """Build a telemetry payload matching emscooter_01 format."""
    now = datetime.utcnow()
    timestamp_ms = int(now.timestamp() * 1000)
    
    # Location with slight variation (simulating movement)
    lat_offset = random.uniform(-0.001, 0.001)
    lng_offset = random.uniform(-0.001, 0.001)
    
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
    trip_distance = round(random.uniform(0, 5), 1) if trip_active else 0
    
    # Motor temperature increases with speed
    motor_temp = round(35 + (speed * 0.5) + random.uniform(-2, 2), 1)
    
    # Tamper detection - rare
    tamper_detected = random.random() < 0.02  # 2% chance
    
    # Geofence status
    geofence_status = random.choice(["inside", "inside", "inside", "outside"])  # Mostly inside
    
    # Signal strength
    signal_strength = random.randint(-90, -60)
    
    payload = {
        "deviceId": DEVICE_ID,
        "timestamp": timestamp_ms,
        "location": {
            "lat": round(LAT + lat_offset, 4),
            "lng": round(LNG + lng_offset, 4)
        },
        "speed_kmph": speed,
        "battery_percent": round(battery),
        "battery_health": round(battery_health),
        "is_locked": is_locked,
        "trip_active": trip_active,
        "trip_distance_km": trip_distance,
        "motor_temperature_c": motor_temp,
        "tamper_detected": tamper_detected,
        "geofence_status": geofence_status,
        "signal_strength_dbm": signal_strength
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
                print(f"  Speed: {payload['speed_kmph']} kmph, Battery: {payload['battery_percent']}%, Trip: {'Active' if payload['trip_active'] else 'Inactive'}")
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

