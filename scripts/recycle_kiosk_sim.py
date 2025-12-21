#!/usr/bin/env python3
"""
Smart Recycling Kiosk MQTT telemetry simulator.

Publishes JSON telemetry for a recycling kiosk device.
Sends a message every minute to the configured MQTT topic.
"""

import json
import os
import random
import time
from datetime import datetime

import paho.mqtt.client as mqtt


# Configuration
DEVICE_ID = os.environ.get("DEVICE_ID", "recycle_kiosk_01")
MQTT_HOST = os.environ.get("MQTT_HOST", "mqtt-broker")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_TOPIC = os.environ.get("MQTT_TOPIC", f"device/{DEVICE_ID}/telemetry")
MQTT_QOS = int(os.environ.get("MQTT_QOS", "0"))
SEND_INTERVAL_SECONDS = int(os.environ.get("SEND_INTERVAL_SECONDS", "60"))


def build_payload() -> dict:
    """Build a telemetry payload with realistic variation."""
    now = datetime.utcnow()
    timestamp_ms = int(now.timestamp() * 1000)
    
    # Fill level - gradually increases, can decrease after collection
    fill_level = max(20, min(95, random.randint(60, 90)))
    
    # Bin weight - correlates with fill level
    bin_weight = round(fill_level * 0.6 + random.uniform(-5, 5), 1)
    
    # Compactor status - active if fill level is high
    if fill_level > 70:
        compactor_status = random.choice(["ACTIVE", "ACTIVE", "STANDBY"])  # Mostly active when full
    else:
        compactor_status = random.choice(["STANDBY", "STANDBY", "ACTIVE"])
    
    # Material counts - vary with usage
    plastic_count = random.randint(10, 25)
    metal_count = random.randint(3, 10)
    paper_count = random.randint(5, 15)
    
    # Contamination detection - rare
    contamination_detected = random.random() < 0.05  # 5% chance
    
    # Collection required if fill level is high
    collection_required = fill_level > 75
    
    # Reward credits - issued when items are deposited
    if fill_level > 50:
        reward_credits = random.randint(3, 8)
    else:
        reward_credits = random.randint(0, 3)
    
    payload = {
        "deviceId": DEVICE_ID,
        "timestamp": timestamp_ms,
        "fill_level_percent": fill_level,
        "bin_weight_kg": bin_weight,
        "compactor_status": compactor_status,
        "plastic_count": plastic_count,
        "metal_count": metal_count,
        "paper_count": paper_count,
        "contamination_detected": contamination_detected,
        "collection_required": collection_required,
        "reward_credits_issued": reward_credits
    }
    
    return payload


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[MQTT] Connected to {MQTT_HOST}:{MQTT_PORT}")
    else:
        print(f"[MQTT] Failed to connect, rc={rc}")


def main():
    print(f"Recycling Kiosk simulator starting for device: {DEVICE_ID}")
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
                print(f"  Fill Level: {payload['fill_level_percent']}%, Weight: {payload['bin_weight_kg']} kg, Collection: {'Required' if payload['collection_required'] else 'Not Required'}")
            else:
                print(f"[{now}] FAILED to publish, status={status}")

            time.sleep(SEND_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("Recycling Kiosk simulator interrupted, shutting down...")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()

