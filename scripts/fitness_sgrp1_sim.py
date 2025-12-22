#!/usr/bin/env python3
"""
Smart Fitness Equipment (Rower) MQTT telemetry simulator for SG-RP-1.

Publishes JSON telemetry matching the fitness_rower_02 format.
"""

import json
import os
import random
import time
from datetime import datetime

import paho.mqtt.client as mqtt


# Configuration
DEVICE_ID = os.environ.get("DEVICE_ID", "SG-RP-1")
MQTT_HOST = os.environ.get("MQTT_HOST", "mqtt-broker")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_TOPIC = os.environ.get("MQTT_TOPIC", f"device/{DEVICE_ID}/telemetry")
MQTT_QOS = int(os.environ.get("MQTT_QOS", "0"))

# Access token used for secure telemetry ingestion (must match device metadata)
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN", "murabba-demo-token")

SEND_INTERVAL_SECONDS = int(os.environ.get("SEND_INTERVAL_SECONDS", "60"))

# Location (Murabba, Riyadh coordinates) - SG-RP-1
LAT = float(os.environ.get("LAT", "24.6700"))
LNG = float(os.environ.get("LNG", "46.7300"))


def build_payload() -> dict:
    """Build a telemetry payload matching fitness_rower_02 format."""
    now = datetime.utcnow()
    timestamp_ms = int(now.timestamp() * 1000)
    
    # In use - more likely during morning/evening hours
    hour = now.hour
    in_use_probability = 0.4 if (6 <= hour <= 9 or 17 <= hour <= 21) else 0.1
    in_use = random.random() < in_use_probability
    
    # User session ID - only if in use
    if in_use:
        user_session_id = f"session_{random.randint(80000, 90000)}"
    else:
        user_session_id = None
    
    # Reps count - accumulates if in use
    if in_use:
        reps_count = random.randint(50, 200)
    else:
        reps_count = 0
    
    # Calories burned - based on usage
    if in_use:
        calories_burned = random.randint(30, 100)
    else:
        calories_burned = 0
    
    # Usage duration - accumulates if in use
    if in_use:
        usage_duration = random.randint(5, 30)
    else:
        usage_duration = 0
    
    # Equipment load level - varies with usage
    if in_use:
        equipment_load_level = random.randint(4, 10)
    else:
        equipment_load_level = 0
    
    # Maintenance score - slowly decreases over time
    maintenance_score = max(70, min(100, random.randint(80, 95)))
    
    # Fault detection - rare
    fault_detected = random.random() < 0.01  # 1% chance

    # Approximate instantaneous power draw (W)
    # Higher when in use (motor + console), very low when idle
    if in_use:
        energy_consumption_w = random.uniform(300.0, 600.0)
    else:
        energy_consumption_w = random.uniform(30.0, 80.0)
    
    payload = {
        "deviceId": DEVICE_ID,
        "timestamp": timestamp_ms,
        "latitude": LAT,
        "longitude": LNG,
        "in_use": in_use,
        "user_session_id": user_session_id,
        "reps_count": reps_count,
        "calories_burned_kcal": calories_burned,
        "usage_duration_min": usage_duration,
        "equipment_load_level": equipment_load_level,
        "maintenance_score": maintenance_score,
        "fault_detected": fault_detected,
        # Instantaneous power draw in watts for Energy Management dashboard
        "energy_consumption_w": round(energy_consumption_w, 1),
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
    print(f"Fitness Rower simulator starting for device: {DEVICE_ID}")
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
                print(f"  In Use: {payload['in_use']}, Reps: {payload['reps_count']}, Calories: {payload['calories_burned_kcal']} kcal")
            else:
                print(f"[{now}] FAILED to publish, status={status}")

            time.sleep(SEND_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("Fitness Rower simulator interrupted, shutting down...")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()

