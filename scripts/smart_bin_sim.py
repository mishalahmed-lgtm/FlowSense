#!/usr/bin/env python3
"""
Smart Bin MQTT telemetry simulator.

- Publishes JSON telemetry for a smart bin device
- Sends a message every 5 minutes to the configured MQTT topic
- Intended to run inside the Docker backend container, talking to the
  Mosquitto broker service on the internal Docker network.
"""

import json
import os
import random
import time
from datetime import datetime, timedelta

import paho.mqtt.client as mqtt


# ---------------------------------------------------------------------------
# Configuration (can be overridden via environment variables)
# ---------------------------------------------------------------------------
DEVICE_ID = os.environ.get("BIN_DEVICE_ID", "B-RP-1")
BIN_ID = os.environ.get("BIN_ID", "bin_01")

# Inside Docker network, the broker service is "mqtt-broker:1883"
# If you ever run this directly on your host, you can override via env:
#   MQTT_HOST=localhost MQTT_PORT=1884
MQTT_HOST = os.environ.get("MQTT_HOST", "mqtt-broker")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))

# MQTT topic should match the Topic Pattern configured for the device
MQTT_TOPIC = os.environ.get("MQTT_TOPIC", f"devices/{DEVICE_ID}/telemetry")
MQTT_QOS = int(os.environ.get("MQTT_QOS", "0"))

# Default send interval: 5 minutes (can override via SEND_INTERVAL_SECONDS env)
SEND_INTERVAL_SECONDS = int(os.environ.get("SEND_INTERVAL_SECONDS", "300"))


def build_payload() -> dict:
    """Build a telemetry payload similar to the example, with realistic variation."""
    now = datetime.utcnow()
    timestamp_ms = int(now.timestamp() * 1000)
    
    # Fill levels gradually increase over time, with some randomness
    general_waste = random.randint(50, 90)
    recyclables = random.randint(30, 60)
    organic = random.randint(20, 50)
    
    # Fire alert is rare (1% chance)
    fire_alert = random.random() < 0.01
    
    # Movement alert (bin being moved/tilted) - 5% chance
    movement_alert = random.random() < 0.05
    
    # Battery gradually decreases but stays reasonable
    battery = random.randint(75, 95)
    
    # Solar panel status - depends on time of day (simplified)
    hour = now.hour
    is_daytime = 6 <= hour <= 18
    solar_voltage = round(random.uniform(12.0, 13.5) if is_daytime else random.uniform(11.5, 12.2), 1)
    solar_charging = is_daytime and random.random() > 0.2  # 80% chance of charging during day
    
    # Last compaction cycle - within last 24 hours
    last_cycle_hours_ago = random.randint(0, 24)
    last_cycle_time = now - timedelta(hours=last_cycle_hours_ago)
    compaction_ratio = random.randint(3, 7)  # Compression ratio
    
    # Odor control status
    odor_status = random.choice(["active", "active", "active", "standby"])  # Mostly active
    filter_life = random.randint(60, 90)  # Filter life percentage
    
    payload = {
        "deviceId": BIN_ID,
        "timestamp": timestamp_ms,
        "fillLevel": {
            "generalWaste": general_waste,
            "recyclables": recyclables,
            "organic": organic
        },
        "temperature": round(random.uniform(25.0, 35.0), 1),
        "fireAlert": fire_alert,
        "movementAlert": movement_alert,
        "battery": battery,
        "solarPanel": {
            "voltage": solar_voltage,
            "charging": solar_charging
        },
        "compactionStatus": {
            "lastCycleTime": last_cycle_time.isoformat() + "Z",
            "ratio": compaction_ratio
        },
        "odorControl": {
            "status": odor_status,
            "filterLifePercent": filter_life
        }
    }
    
    return payload


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[MQTT] Connected to {MQTT_HOST}:{MQTT_PORT}")
    else:
        print(f"[MQTT] Failed to connect, rc={rc}")


def main():
    print(f"Smart Bin simulator starting for device: {DEVICE_ID}")
    print(f"Bin ID: {BIN_ID}")
    print(f"Broker: {MQTT_HOST}:{MQTT_PORT}")
    print(f"Topic:  {MQTT_TOPIC}")
    print(f"QoS:    {MQTT_QOS}")
    print(f"Interval: {SEND_INTERVAL_SECONDS} seconds\n")

    client = mqtt.Client()
    client.on_connect = on_connect

    # Connect and start network loop
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
                print(f"  Payload preview: deviceId={payload['deviceId']}, generalWaste={payload['fillLevel']['generalWaste']}%, battery={payload['battery']}%")
            else:
                print(f"[{now}] FAILED to publish, status={status}")

            time.sleep(SEND_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("Smart Bin simulator interrupted, shutting down...")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()

