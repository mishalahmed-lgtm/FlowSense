#!/usr/bin/env python3
"""
E-Scooter MQTT telemetry simulator for ES-RP-1 and ES-RP-2.

Publishes JSON telemetry matching the emscooter_01 format.
Supports multiple devices running concurrently.
"""

import json
import os
import random
import time
import threading
from datetime import datetime

import paho.mqtt.client as mqtt


# Configuration
MQTT_HOST = os.environ.get("MQTT_HOST", "mqtt-broker")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_QOS = int(os.environ.get("MQTT_QOS", "0"))
SEND_INTERVAL_SECONDS = int(os.environ.get("SEND_INTERVAL_SECONDS", "60"))

# Device configurations
DEVICES = [
    {
        "device_id": "ES-RP-1",
        "access_token": os.environ.get("ES_RP_1_TOKEN", "murabba-demo-token"),
        "lat": float(os.environ.get("ES_RP_1_LAT", "24.6400")),
        "lng": float(os.environ.get("ES_RP_1_LNG", "46.7000")),
    },
    {
        "device_id": "ES-RP-2",
        "access_token": os.environ.get("ES_RP_2_TOKEN", "murraba"),
        "lat": float(os.environ.get("ES_RP_2_LAT", "24.6450")),
        "lng": float(os.environ.get("ES_RP_2_LNG", "46.7050")),
    },
]

# Support single device mode via DEVICE_ID env var (for backward compatibility)
SINGLE_DEVICE_ID = os.environ.get("DEVICE_ID")
if SINGLE_DEVICE_ID:
    # Filter to only the specified device
    DEVICES = [d for d in DEVICES if d["device_id"] == SINGLE_DEVICE_ID]
    if not DEVICES:
        # If device not in list, create a single device config
        DEVICES = [{
            "device_id": SINGLE_DEVICE_ID,
            "access_token": os.environ.get("ACCESS_TOKEN", "murabba-demo-token"),
            "lat": float(os.environ.get("LAT", "24.6400")),
            "lng": float(os.environ.get("LNG", "46.7000")),
        }]


def build_payload(device_id: str, access_token: str, base_lat: float, base_lng: float) -> dict:
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
    
    # Rough estimate of instantaneous power draw (W) based on speed and trip state.
    # This is a simplified demo model for the Energy Management dashboard.
    if trip_active:
        # More power when moving faster
        energy_consumption_w = max(150.0, min(600.0, speed * 20.0))
    else:
        # Idle / parked power draw
        energy_consumption_w = 20.0 if not is_locked else 5.0

    payload = {
        "deviceId": device_id,
        "timestamp": timestamp_ms,
        "location": {
            "lat": round(base_lat + lat_offset, 4),
            "lng": round(base_lng + lng_offset, 4)
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
        "signal_strength_dbm": signal_strength,
        # Instantaneous power draw in watts for Energy Management dashboard
        "energy_consumption_w": round(energy_consumption_w, 1),
        # Access token for backend authentication
        "access_token": access_token,
    }
    
    return payload


def on_connect(client, userdata, flags, rc):
    device_id = userdata.get("device_id", "Unknown")
    if rc == 0:
        print(f"[{device_id}] Connected to {MQTT_HOST}:{MQTT_PORT}")
    else:
        print(f"[{device_id}] Failed to connect, rc={rc}")


def simulate_device(device_config: dict):
    """Simulate a single e-scooter device."""
    device_id = device_config["device_id"]
    access_token = device_config["access_token"]
    base_lat = device_config["lat"]
    base_lng = device_config["lng"]
    mqtt_topic = f"device/{device_id}/telemetry"
    
    print(f"[{device_id}] E-Scooter simulator starting")
    print(f"[{device_id}] Broker: {MQTT_HOST}:{MQTT_PORT}")
    print(f"[{device_id}] Topic:  {mqtt_topic}")
    print(f"[{device_id}] Interval: {SEND_INTERVAL_SECONDS} seconds\n")

    client = mqtt.Client()
    client.user_data_set({"device_id": device_id})
    client.on_connect = on_connect

    try:
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_start()

        while True:
            payload = build_payload(device_id, access_token, base_lat, base_lng)
            payload_str = json.dumps(payload)

            result = client.publish(mqtt_topic, payload_str, qos=MQTT_QOS)
            status = result[0]

            now = datetime.utcnow().isoformat() + "Z"
            if status == mqtt.MQTT_ERR_SUCCESS:
                print(f"[{now}] [{device_id}] Published to {mqtt_topic}")
                print(f"  Speed: {payload['speed_kmph']} kmph, Battery: {payload['battery_percent']}%, Trip: {'Active' if payload['trip_active'] else 'Inactive'}")
            else:
                print(f"[{now}] [{device_id}] FAILED to publish, status={status}")

            time.sleep(SEND_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print(f"[{device_id}] E-Scooter simulator interrupted, shutting down...")
    finally:
        client.loop_stop()
        client.disconnect()


def main():
    print("=" * 60)
    print("E-Scooter Simulator - Multiple Devices")
    print("=" * 60)
    print(f"Broker: {MQTT_HOST}:{MQTT_PORT}")
    print(f"Devices to simulate: {len(DEVICES)}")
    for device in DEVICES:
        print(f"  - {device['device_id']} (token: {device['access_token']})")
    print(f"Interval: {SEND_INTERVAL_SECONDS} seconds")
    print("=" * 60)
    print()

    threads = []
    for device_config in DEVICES:
        thread = threading.Thread(
            target=simulate_device,
            args=(device_config,),
            daemon=True
        )
        thread.start()
        threads.append(thread)

    try:
        # Keep main thread alive
        for thread in threads:
            thread.join()
    except KeyboardInterrupt:
        print("\nE-Scooter simulators interrupted, shutting down...")
        print("Waiting for threads to finish...")


if __name__ == "__main__":
    main()

