#!/usr/bin/env python3
"""
Smart Bin MQTT telemetry simulator for SB-RP-3.

Publishes JSON telemetry for a smart bin device.
"""

import json
import os
import random
import time
from datetime import datetime, timedelta

import paho.mqtt.client as mqtt


# Configuration
DEVICE_ID = os.environ.get("DEVICE_ID", "SB-RP-3")
BIN_ID = os.environ.get("BIN_ID", "sb_rp_3")

MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1884"))

# MQTT topic should match the Topic Pattern configured for the device
MQTT_TOPIC = os.environ.get("MQTT_TOPIC", f"device/{DEVICE_ID}/telemetry")
MQTT_QOS = int(os.environ.get("MQTT_QOS", "0"))

# Access token used for secure telemetry ingestion (must match device metadata)
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN", "murraba")

# Default send interval: 5 minutes (can override via SEND_INTERVAL_SECONDS env)
SEND_INTERVAL_SECONDS = int(os.environ.get("SEND_INTERVAL_SECONDS", "60"))

# Location (Murabba, Riyadh coordinates) - SB-RP-3
LAT = float(os.environ.get("LAT", "24.6600"))
LNG = float(os.environ.get("LNG", "46.7200"))


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

    # Approximate instantaneous power draw (W)
    # - Base idle power
    # - Extra power when solar charging
    # - Extra power when compacting
    base_power_w = 15.0
    charging_power_w = 10.0 if solar_charging else 0.0
    compaction_power_w = 120.0 if fire_alert or movement_alert else 0.0
    energy_consumption_w = base_power_w + charging_power_w + compaction_power_w

    payload = {
        "deviceId": DEVICE_ID,
        "binId": BIN_ID,
        "timestamp": timestamp_ms,
        "latitude": LAT,  # Top-level for map compatibility
        "longitude": LNG,  # Top-level for map compatibility
        "location": {
            "lat": LAT,
            "lng": LNG,
        },
        "fillLevels": {
            "generalWaste": general_waste,
            "recyclables": recyclables,
            "organic": organic,
        },
        "alerts": {
            "fire": fire_alert,
            "movement": movement_alert,
        },
        "battery": {
            "level": battery,
            "solarVoltage": solar_voltage,
            "solarCharging": solar_charging,
        },
        "compaction": {
            "lastCycleTime": last_cycle_time.isoformat() + "Z",
            "compactionRatio": compaction_ratio,
        },
        "odorControl": {
            "status": odor_status,
            "filterLife": filter_life,
        },
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
    print(f"Smart Bin simulator starting for device: {DEVICE_ID}")
    print(f"Bin ID: {BIN_ID}")
    print(f"Broker: {MQTT_HOST}:{MQTT_PORT}")
    print(f"Topic:  {MQTT_TOPIC}")
    print(f"QoS:    {MQTT_QOS}")
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
                fill_info = f"Waste: {payload['fillLevels']['generalWaste']}%, Recyclables: {payload['fillLevels']['recyclables']}%"
                print(f"  {fill_info}, Battery: {payload['battery']['level']}%")
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



