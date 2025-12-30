#!/usr/bin/env python3
"""
Digital Kiosk MQTT telemetry simulator for DK-RP-2.

Publishes JSON telemetry for a digital kiosk device.
"""

import json
import os
import random
import time
from datetime import datetime, timedelta

import paho.mqtt.client as mqtt


# Configuration
DEVICE_ID = os.environ.get("DEVICE_ID", "DK-RP-2")
KIOSK_ID = os.environ.get("KIOSK_ID", "kiosk_02")

MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1884"))
MQTT_TOPIC = os.environ.get("MQTT_TOPIC", f"device/{DEVICE_ID}/telemetry")
MQTT_QOS = int(os.environ.get("MQTT_QOS", "0"))

# Access token used for secure telemetry ingestion (must match device metadata)
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN", "murraba")

SEND_INTERVAL_SECONDS = int(os.environ.get("SEND_INTERVAL_SECONDS", "60"))

# Location (Murabba, Riyadh coordinates) - DK-RP-2
LAT = float(os.environ.get("LAT", "24.6800"))
LNG = float(os.environ.get("LNG", "46.7500"))


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
        "deviceId": DEVICE_ID,
        "timestamp": timestamp_ms,
        "latitude": LAT,  # Top-level for map compatibility
        "longitude": LNG,  # Top-level for map compatibility
        "location": {
            "lat": LAT,
            "lng": LNG
        },
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
        },
        # Access token for backend authentication
        "access_token": ACCESS_TOKEN
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
                print(f"  People: {payload['visitorAnalytics']['peopleCount']}, Temp: {payload['environment']['temperature']}°C, Events: {len(payload['events'])}")
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



