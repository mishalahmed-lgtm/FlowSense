#!/usr/bin/env python3
"""
Adaptive Pathway Lighting MQTT telemetry simulator for PLP-RP-1.

Publishes JSON telemetry matching the lightpole_12 format.
"""

import json
import os
import random
import time
from datetime import datetime

import paho.mqtt.client as mqtt


# Configuration
DEVICE_ID = os.environ.get("DEVICE_ID", "PLP-RP-1")
MQTT_HOST = os.environ.get("MQTT_HOST", "mqtt-broker")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_TOPIC = os.environ.get("MQTT_TOPIC", f"device/{DEVICE_ID}/telemetry")
MQTT_QOS = int(os.environ.get("MQTT_QOS", "0"))
SEND_INTERVAL_SECONDS = int(os.environ.get("SEND_INTERVAL_SECONDS", "60"))


def build_payload() -> dict:
    """Build a telemetry payload matching lightpole_12 format."""
    now = datetime.utcnow()
    timestamp_ms = int(now.timestamp() * 1000)
    
    # Motion detection - more likely during day/evening hours
    hour = now.hour
    motion_probability = 0.7 if 6 <= hour <= 22 else 0.3
    motion_detected = random.random() < motion_probability
    
    # Crowd density - varies with motion
    if motion_detected:
        crowd_density = random.randint(1, 15)
    else:
        crowd_density = random.randint(0, 3)
    
    # Brightness adjusts based on motion and time of day
    if motion_detected:
        brightness = random.randint(80, 100)
    elif 6 <= hour <= 22:
        brightness = random.randint(40, 70)
    else:
        brightness = random.randint(20, 40)
    
    # Color temperature - warmer at night
    if 18 <= hour <= 6:
        color_temp = random.randint(2700, 3200)  # Warm
    else:
        color_temp = random.randint(4000, 5000)  # Cool
    
    # Energy consumption based on brightness
    energy_consumption = round(brightness * 0.45 + random.uniform(-5, 5), 1)
    
    # Lamp status - ON if brightness > 20
    lamp_status = "ON" if brightness > 20 else "OFF"
    
    # Fault detection - rare
    fault_detected = random.random() < 0.01  # 1% chance
    
    # Override mode - occasional
    override_mode = random.random() < 0.05  # 5% chance
    
    # Power factor - good efficiency
    power_factor = round(random.uniform(0.92, 0.98), 2)
    
    payload = {
        "deviceId": DEVICE_ID,
        "timestamp": timestamp_ms,
        "motion_detected": motion_detected,
        "crowd_density": crowd_density,
        "brightness_percent": brightness,
        "color_temperature_kelvin": color_temp,
        "energy_consumption_w": energy_consumption,
        "lamp_status": lamp_status,
        "fault_detected": fault_detected,
        "override_mode": override_mode,
        "power_factor": power_factor
    }
    
    return payload


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[MQTT] Connected to {MQTT_HOST}:{MQTT_PORT}")
    else:
        print(f"[MQTT] Failed to connect, rc={rc}")


def main():
    print(f"Pathway Lighting simulator starting for device: {DEVICE_ID}")
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
                print(f"  Motion: {payload['motion_detected']}, Brightness: {payload['brightness_percent']}%, Lamp: {payload['lamp_status']}")
            else:
                print(f"[{now}] FAILED to publish, status={status}")

            time.sleep(SEND_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("Pathway Lighting simulator interrupted, shutting down...")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()

