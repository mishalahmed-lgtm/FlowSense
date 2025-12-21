#!/usr/bin/env python3
"""
Smart Bench MQTT telemetry simulator.

- Publishes JSON telemetry for a single bench (e.g. BENCH-07)
- Sends a message every minute to the configured MQTT topic
- Intended to run inside the Docker backend container, talking to the
  Mosquitto broker service on the internal Docker network.
"""

import json
import os
import random
import time
from datetime import datetime

import paho.mqtt.client as mqtt


# ---------------------------------------------------------------------------
# Configuration (can be overridden via environment variables)
# ---------------------------------------------------------------------------
BENCH_ID = os.environ.get("BENCH_ID", "BENCH-07")

# Optional fixed location for this bench (can be overridden via env)
# Example: 24.7136, 46.6753 (Riyadh)
BENCH_LAT = float(os.environ.get("BENCH_LAT", "24.7136"))
BENCH_LON = float(os.environ.get("BENCH_LON", "46.6753"))

# Inside Docker network, the broker service is "mqtt-broker:1883"
# If you ever run this directly on your host, you can override via env:
#   MQTT_HOST=localhost MQTT_PORT=1884
MQTT_HOST = os.environ.get("MQTT_HOST", "mqtt-broker")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))

# MQTT topic should match the Topic Pattern configured for the device
MQTT_TOPIC = os.environ.get("MQTT_TOPIC", f"devices/{BENCH_ID}/telemetry")
MQTT_QOS = int(os.environ.get("MQTT_QOS", "0"))

# Default send interval: 5 minutes (can override via SEND_INTERVAL_SECONDS env)
SEND_INTERVAL_SECONDS = int(os.environ.get("SEND_INTERVAL_SECONDS", "300"))


def build_payload() -> dict:
    """Build a telemetry payload similar to the example, with light variation."""
    payload = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "benchId": BENCH_ID,
        "location": {
            "latitude": BENCH_LAT,
            "longitude": BENCH_LON,
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
    print(f"Smart Bench simulator starting for bench: {BENCH_ID}")
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
                print(f"[{now}] Published to {MQTT_TOPIC}: {payload_str}")
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


