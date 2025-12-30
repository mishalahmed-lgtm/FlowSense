#!/usr/bin/env python3
"""
Smart Bench MQTT telemetry simulator for SM1-RP-2.

Publishes JSON telemetry for a smart bench device.
"""

import json
import os
import random
import time
from datetime import datetime

import paho.mqtt.client as mqtt


# Configuration
DEVICE_ID = os.environ.get("DEVICE_ID", "SM1-RP-2")
MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1884"))
MQTT_TOPIC = os.environ.get("MQTT_TOPIC", f"device/{DEVICE_ID}/telemetry")
MQTT_QOS = int(os.environ.get("MQTT_QOS", "0"))

# Access token used for secure telemetry ingestion (must match device metadata)
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN", "murraba")

SEND_INTERVAL_SECONDS = int(os.environ.get("SEND_INTERVAL_SECONDS", "60"))

# Location (Murabba, Riyadh coordinates) - SM1-RP-2
LAT = float(os.environ.get("LAT", "24.6700"))
LNG = float(os.environ.get("LNG", "46.7300"))


def build_payload() -> dict:
    """Build a telemetry payload for smart bench."""
    payload = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "benchId": DEVICE_ID,
        "deviceId": DEVICE_ID,
        "latitude": LAT,  # Top-level for map compatibility
        "longitude": LNG,  # Top-level for map compatibility
        "location": {
            "lat": LAT,
            "lng": LNG,
            "latitude": LAT,  # Keep for backward compatibility
            "longitude": LNG,  # Keep for backward compatibility
        },
        "battery": {
            "voltage": round(random.uniform(12.4, 12.8), 2),
            "soc": random.randint(75, 90),
            "solarPowerW": random.randint(100, 160),
            "loadPowerW": random.randint(40, 70),
        },
        "occupancy": {
            "seat1": random.choice([True, False]),
            "seat2": random.choice([True, False]),
            "seat3": random.choice([True, False]),
            "total": 0,  # will be updated below
        },
        "charging": {
            "usbActivePorts": random.randint(0, 4),
            "wirelessActive": random.choice([True, False]),
            "powerW": random.randint(0, 60),
            "sessionsToday": random.randint(0, 40),
        },
        "environment": {
            "pm25": random.randint(20, 80),
            "pm10": random.randint(30, 100),
            "co2": random.randint(600, 1200),
            "temperature": round(random.uniform(30.0, 42.0), 1),
            "humidity": random.randint(30, 70),
        },
        "system": {
            "uptimeHours": random.randint(200, 300),
            "cpuTemp": round(random.uniform(45.0, 65.0), 1),
            "network": random.choice(["LTE", "5G", "WiFi"]),
            "rssi": random.randint(-80, -60),
        },
        # Instantaneous power draw in watts for Energy Management dashboard
        "energy_consumption_w": round(random.uniform(50.0, 120.0), 1),
        # Access token for backend authentication
        "access_token": ACCESS_TOKEN
    }

    occ = payload["occupancy"]
    occ["total"] = sum(1 for seat in ("seat1", "seat2", "seat3") if occ[seat])
    return payload


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[MQTT] Connected to {MQTT_HOST}:{MQTT_PORT}")
    else:
        print(f"[MQTT] Failed to connect, rc={rc}")


def main():
    print(f"Smart Bench simulator starting for device: {DEVICE_ID}")
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
                print(f"  Occupancy: {payload['occupancy']['total']}/3, Temp: {payload['environment']['temperature']}°C, Battery: {payload['battery']['soc']}%")
            else:
                print(f"[{now}] FAILED to publish, status={status}")

            time.sleep(SEND_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("Smart Bench simulator interrupted, shutting down...")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()

