#!/usr/bin/env python3
"""
Ambient Noise Sensor MQTT telemetry simulator for NS-RP-2.

Publishes JSON telemetry matching the noise_sensor format.
"""

import json
import os
import random
import time
from datetime import datetime

import paho.mqtt.client as mqtt


# Configuration
DEVICE_ID = os.environ.get("DEVICE_ID", "NS-RP-2")
MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1884"))
MQTT_TOPIC = os.environ.get("MQTT_TOPIC", f"device/{DEVICE_ID}/telemetry")
MQTT_QOS = int(os.environ.get("MQTT_QOS", "0"))

# Access token used for secure telemetry ingestion (must match device metadata)
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN", "murraba")

SEND_INTERVAL_SECONDS = int(os.environ.get("SEND_INTERVAL_SECONDS", "60"))

# Location (Murabba, Riyadh coordinates) - NS-RP-2
LAT = float(os.environ.get("LAT", "24.6750"))
LNG = float(os.environ.get("LNG", "46.7350"))


def build_payload() -> dict:
    """Build a telemetry payload matching noise_sensor format."""
    now = datetime.utcnow()
    timestamp_ms = int(now.timestamp() * 1000)
    
    # Noise level - varies with time of day
    hour = now.hour
    if 8 <= hour <= 20:
        # Daytime - higher noise
        noise_level = round(random.uniform(60, 85), 1)
    else:
        # Nighttime - lower noise
        noise_level = round(random.uniform(40, 65), 1)
    
    # Peak noise - occasional spikes
    noise_peak = round(noise_level + random.uniform(5, 20), 1)
    
    # Frequency - varies
    frequency = random.randint(500, 2000)
    
    # Alert triggered if noise exceeds threshold
    alert_triggered = noise_level > 70
    
    # Noise category - depends on level and time
    if noise_level > 75:
        noise_category = random.choice(["music", "traffic", "construction"])
    elif noise_level > 60:
        noise_category = random.choice(["conversation", "traffic", "music"])
    else:
        noise_category = random.choice(["ambient", "conversation", "wind"])
    
    # Event mode - special events increase noise
    event_mode = random.random() < 0.1  # 10% chance of event
    
    # Location zone
    location_zone = random.choice(["north_lawn", "south_lawn", "east_lawn", "west_lawn", "central_plaza"])

    # Approximate instantaneous power draw (W)
    # Low-power sensor, slightly higher when alerting
    base_power_w = random.uniform(3.0, 5.0)
    alert_extra_power_w = 1.5 if alert_triggered else 0.0
    energy_consumption_w = base_power_w + alert_extra_power_w
    
    payload = {
        "deviceId": DEVICE_ID,
        "timestamp": timestamp_ms,
        "latitude": LAT,
        "longitude": LNG,
        "noise_level_db": noise_level,
        "noise_peak_db": noise_peak,
        "frequency_hz": frequency,
        "alert_triggered": alert_triggered,
        "noise_category": noise_category,
        "event_mode": event_mode,
        "location_zone": location_zone,
        # Instantaneous power draw in watts for Energy Management dashboard
        "energy_consumption_w": round(energy_consumption_w, 2),
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
    print(f"Noise Sensor simulator starting for device: {DEVICE_ID}")
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
                print(f"  Noise: {payload['noise_level_db']} dB, Peak: {payload['noise_peak_db']} dB, Alert: {payload['alert_triggered']}")
            else:
                print(f"[{now}] FAILED to publish, status={status}")

            time.sleep(SEND_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("Noise Sensor simulator interrupted, shutting down...")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()



