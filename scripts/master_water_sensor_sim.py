#!/usr/bin/env python3
"""
Master Water Sensor MQTT telemetry simulator.

Publishes JSON telemetry for a master water sensor device.
Sends a message every minute to the configured MQTT topic.
"""

import json
import os
import random
import time
from datetime import datetime

import paho.mqtt.client as mqtt


# Configuration
DEVICE_ID = os.environ.get("DEVICE_ID", "MW-RP-1")
MQTT_HOST = os.environ.get("MQTT_HOST", "mqtt-broker")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_TOPIC = os.environ.get("MQTT_TOPIC", f"device/{DEVICE_ID}/telemetry")
MQTT_QOS = int(os.environ.get("MQTT_QOS", "0"))
SEND_INTERVAL_SECONDS = int(os.environ.get("SEND_INTERVAL_SECONDS", "60"))

# Access token used for secure telemetry ingestion (must match device metadata)
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN", "murabba")

# Location (Murabba, Riyadh coordinates) - MW-RP-1
LAT = float(os.environ.get("LAT", "24.6800"))
LNG = float(os.environ.get("LNG", "46.7150"))

# Cumulative water consumption (in m³) - starts at a base value and increases
# Start at 0 to show total consumption from the beginning
base_consumption_m3 = float(os.environ.get("BASE_CONSUMPTION_M3", "0.0"))  # Start at 0 m³
consumption_counter = base_consumption_m3


def build_payload() -> dict:
    """Build a telemetry payload with realistic variation."""
    global consumption_counter
    
    now = datetime.utcnow()
    timestamp_ms = int(now.timestamp() * 1000)
    
    # Water flow rate - varies with time of day (more usage during day)
    hour = now.hour
    if 8 <= hour <= 20:
        # Daytime - higher flow
        flow_rate_lpm = round(random.uniform(10.0, 50.0), 2)  # liters per minute
    else:
        # Nighttime - lower flow
        flow_rate_lpm = round(random.uniform(2.0, 15.0), 2)
    
    # Water pressure - typically 2-5 bar
    pressure_bar = round(random.uniform(2.0, 5.0), 2)
    
    # Water temperature - ambient + slight variation
    water_temp_c = round(random.uniform(22.0, 28.0), 1)
    
    # Total water consumption (cumulative, increases over time)
    # Increment based on flow rate (simulate consumption over the interval)
    # Flow rate is in LPM, interval is in seconds, convert to m³
    interval_minutes = SEND_INTERVAL_SECONDS / 60.0
    consumption_increment_liters = flow_rate_lpm * interval_minutes
    consumption_increment_m3 = consumption_increment_liters / 1000.0
    consumption_counter += consumption_increment_m3
    
    # Round to 3 decimal places for m³
    consumption_m3 = round(consumption_counter, 3)
    consumption_liters = round(consumption_m3 * 1000.0, 2)  # For display/compatibility
    
    # Water quality metrics
    ph_level = round(random.uniform(6.5, 8.5), 2)
    turbidity_ntu = round(random.uniform(0.1, 2.0), 2)  # Nephelometric Turbidity Units
    chlorine_ppm = round(random.uniform(0.2, 2.0), 2)  # Parts per million
    
    # Leak detection - rare but possible
    leak_detected = random.random() < 0.02  # 2% chance
    
    # Valve status
    valve_status = random.choice(["open", "open", "open", "closed"])  # Mostly open
    
    # System status
    system_status = "normal" if not leak_detected else "alert"
    
    # Battery level (if battery-powered)
    battery_percent = random.randint(85, 100)
    
    # Signal strength
    signal_strength_dbm = random.randint(-85, -65)
    
    payload = {
        "deviceId": DEVICE_ID,
        "timestamp": timestamp_ms,
        "location": {
            "lat": LAT,
            "lng": LNG
        },
        "latitude": LAT,  # Keep for backward compatibility
        "longitude": LNG,  # Keep for backward compatibility
        "flow_rate_lpm": flow_rate_lpm,
        "pressure_bar": pressure_bar,
        "water_temperature_c": water_temp_c,
        "total_consumption_liters": consumption_liters,  # Keep for backward compatibility
        "volume_index": consumption_m3,  # Required by backend for water consumption tracking (in m³)
        "water_quality": {
            "ph": ph_level,
            "turbidity_ntu": turbidity_ntu,
            "chlorine_ppm": chlorine_ppm
        },
        "leak_detected": leak_detected,
        "valve_status": valve_status,
        "system_status": system_status,
        "battery_percent": battery_percent,
        "signal_strength_dbm": signal_strength_dbm,
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
    print(f"Master Water Sensor simulator starting for device: {DEVICE_ID}")
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
                print(f"  Flow: {payload['flow_rate_lpm']} LPM, Pressure: {payload['pressure_bar']} bar, Status: {payload['system_status']}")
            else:
                print(f"[{now}] FAILED to publish, status={status}")

            time.sleep(SEND_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("Master Water Sensor simulator interrupted, shutting down...")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()

