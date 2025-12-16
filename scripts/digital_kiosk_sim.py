#!/usr/bin/env python3
"""
Digital Kiosk MQTT telemetry simulator.

- Publishes JSON telemetry for a digital kiosk device
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
DEVICE_ID = os.environ.get("KIOSK_DEVICE_ID", "DK_MP-1")
KIOSK_ID = os.environ.get("KIOSK_ID", "kiosk_01")

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
    
    # Generate some sample events (vary between 0-3 events)
    num_events = random.randint(0, 3)
    events = []
    event_names = ["Yoga Class", "Music Concert", "Food Festival", "Art Exhibition", "Fitness Workshop"]
    
    for i in range(num_events):
        start_hour = random.randint(9, 18)
        start_time = now.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        if start_time < now:
            start_time += timedelta(days=1)
        end_time = start_time + timedelta(hours=random.randint(1, 3))
        
        events.append({
            "name": random.choice(event_names),
            "startTime": start_time.isoformat() + "Z",
            "endTime": end_time.isoformat() + "Z"
        })
    
    # Weather options
    weather_options = ["Sunny", "Partly Cloudy", "Cloudy", "Clear", "Hazy"]
    
    payload = {
        "deviceId": KIOSK_ID,
        "timestamp": timestamp_ms,
        "environment": {
            "temperature": round(random.uniform(28.0, 38.0), 1),
            "humidity": random.randint(35, 65),
            "airQualityIndex": random.randint(50, 100),
            "weather": random.choice(weather_options),
        },
        "facilityStatus": {
            "restrooms": {
                "available": random.randint(1, 4),
                "total": 5
            },
            "parking": {
                "available": random.randint(5, 18),
                "total": 20
            },
            "benches": {
                "available": random.randint(1, 4),
                "total": 5
            }
        },
        "events": events,
        "visitorAnalytics": {
            "peopleCount": random.randint(10, 50),
            "avgDwellTime": random.randint(60, 180),
            "interactionCount": random.randint(20, 80),
            "popularContent": random.choice([
                "Event Promo Video",
                "Park Map",
                "Weather Info",
                "Event Schedule",
                "Facility Guide"
            ])
        },
        "deviceStatus": {
            "cpuUsage": random.randint(25, 50),
            "ramUsage": random.randint(45, 75),
            "storageUsage": random.randint(40, 70),
            "network": {
                "status": random.choice(["ok", "ok", "ok", "degraded"]),  # Mostly ok
                "connection": random.choice(["Ethernet", "WiFi", "5G"])
            }
        }
    }
    
    return payload


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[MQTT] Connected to {MQTT_HOST}:{MQTT_PORT}")
    else:
        print(f"[MQTT] Failed to connect, rc={rc}")


def main():
    print(f"Digital Kiosk simulator starting for device: {DEVICE_ID}")
    print(f"Kiosk ID: {KIOSK_ID}")
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
                print(f"  Payload preview: deviceId={payload['deviceId']}, temp={payload['environment']['temperature']}°C, people={payload['visitorAnalytics']['peopleCount']}")
            else:
                print(f"[{now}] FAILED to publish, status={status}")

            time.sleep(SEND_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("Digital Kiosk simulator interrupted, shutting down...")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()

