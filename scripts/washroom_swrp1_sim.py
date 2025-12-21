#!/usr/bin/env python3
"""
Smart Washroom System MQTT telemetry simulator for SW-RP-1.

Publishes JSON telemetry matching the washroom_03 format.
"""

import json
import os
import random
import time
from datetime import datetime

import paho.mqtt.client as mqtt


# Configuration
DEVICE_ID = os.environ.get("DEVICE_ID", "SW-RP-1")
MQTT_HOST = os.environ.get("MQTT_HOST", "mqtt-broker")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_TOPIC = os.environ.get("MQTT_TOPIC", f"device/{DEVICE_ID}/telemetry")
MQTT_QOS = int(os.environ.get("MQTT_QOS", "0"))
SEND_INTERVAL_SECONDS = int(os.environ.get("SEND_INTERVAL_SECONDS", "60"))


def build_payload() -> dict:
    """Build a telemetry payload matching washroom_03 format."""
    now = datetime.utcnow()
    timestamp_ms = int(now.timestamp() * 1000)
    
    # Occupancy - more likely during day hours
    hour = now.hour
    occupancy_probability = 0.6 if 8 <= hour <= 20 else 0.2
    occupancy = random.random() < occupancy_probability
    
    # Occupancy duration - accumulates if occupied
    if occupancy:
        occupancy_duration = random.randint(1, 30)
    else:
        occupancy_duration = 0
    
    # Temperature - varies with time of day
    if 12 <= hour <= 16:
        temperature = round(random.uniform(28, 32), 1)  # Warmer during day
    else:
        temperature = round(random.uniform(24, 28), 1)
    
    # Humidity - higher when occupied
    if occupancy:
        humidity = random.randint(70, 85)
    else:
        humidity = random.randint(50, 70)
    
    # VOC (Volatile Organic Compounds) - higher when occupied
    if occupancy:
        voc = round(random.uniform(0.5, 1.5), 2)
    else:
        voc = round(random.uniform(0.2, 0.8), 2)
    
    # Ammonia - increases with usage
    if occupancy:
        ammonia = round(random.uniform(1.0, 2.5), 1)
    else:
        ammonia = round(random.uniform(0.5, 1.5), 1)
    
    # Soap level - decreases over time
    soap_level = max(0, min(100, random.randint(20, 50)))
    
    # Toilet paper level - decreases over time
    toilet_paper_level = max(0, min(100, random.randint(25, 60)))
    
    # Water leak - rare
    water_leak_detected = random.random() < 0.005  # 0.5% chance
    
    # Panic button - very rare
    panic_button_pressed = random.random() < 0.001  # 0.1% chance
    
    payload = {
        "deviceId": DEVICE_ID,
        "timestamp": timestamp_ms,
        "occupancy": occupancy,
        "occupancy_duration_min": occupancy_duration,
        "temperature_c": temperature,
        "humidity_percent": humidity,
        "voc_ppm": voc,
        "ammonia_ppm": ammonia,
        "soap_level_percent": soap_level,
        "toilet_paper_level_percent": toilet_paper_level,
        "water_leak_detected": water_leak_detected,
        "panic_button_pressed": panic_button_pressed
    }
    
    return payload


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[MQTT] Connected to {MQTT_HOST}:{MQTT_PORT}")
    else:
        print(f"[MQTT] Failed to connect, rc={rc}")


def main():
    print(f"Smart Washroom simulator starting for device: {DEVICE_ID}")
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
                print(f"  Occupancy: {payload['occupancy']}, Temp: {payload['temperature_c']}°C, Humidity: {payload['humidity_percent']}%")
            else:
                print(f"[{now}] FAILED to publish, status={status}")

            time.sleep(SEND_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("Smart Washroom simulator interrupted, shutting down...")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()

