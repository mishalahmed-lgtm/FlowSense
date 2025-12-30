#!/usr/bin/env python3
"""
Rain Sensor MQTT telemetry simulator for RS-RP-1.

Publishes JSON telemetry for a rain sensor device.
"""

import json
import os
import random
import time
from datetime import datetime

import paho.mqtt.client as mqtt


# Configuration
DEVICE_ID = os.environ.get("DEVICE_ID", "RS-RP-1")
MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1884"))
MQTT_TOPIC = os.environ.get("MQTT_TOPIC", f"device/{DEVICE_ID}/telemetry")
MQTT_QOS = int(os.environ.get("MQTT_QOS", "0"))

# Access token used for secure telemetry ingestion (must match device metadata)
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN", "murraba")

SEND_INTERVAL_SECONDS = int(os.environ.get("SEND_INTERVAL_SECONDS", "60"))

# Location (Murabba, Riyadh coordinates) - RS-RP-1
LAT = float(os.environ.get("LAT", "24.6650"))
LNG = float(os.environ.get("LNG", "46.7250"))


def build_payload() -> dict:
    """Build a telemetry payload for rain sensor."""
    now = datetime.utcnow()
    timestamp_ms = int(now.timestamp() * 1000)
    
    # Simulate weather patterns - Riyadh is mostly dry, but occasional rain
    hour = now.hour
    day_of_year = now.timetuple().tm_yday
    
    # Riyadh has very low annual rainfall (~100mm/year), mostly in winter months
    # Simulate occasional rain events (Nov-Feb: higher chance, other months: very low)
    is_rainy_season = 305 <= day_of_year <= 365 or 1 <= day_of_year <= 59  # Nov-Feb
    
    # Base chance of rain: 5% in rainy season, 0.5% otherwise
    rain_chance = 0.05 if is_rainy_season else 0.005
    is_raining = random.random() < rain_chance
    
    if is_raining:
        # Rainfall rate - varies from light to heavy
        rainfall_rate = round(random.uniform(0.5, 15.0), 2)  # mm/h
        
        # Determine intensity based on rate
        if rainfall_rate < 2.5:
            intensity = "light"
        elif rainfall_rate < 7.5:
            intensity = "moderate"
        else:
            intensity = "heavy"
        
        # Accumulated rainfall (increases while raining)
        rainfall_accumulated = round(random.uniform(0.1, 5.0), 2)  # mm
        
        # Humidity increases during rain
        humidity = random.randint(75, 95)
    else:
        # No rain - dry conditions
        rainfall_rate = 0.0
        intensity = "none"
        rainfall_accumulated = 0.0
        
        # Humidity - varies with time of day (lower during day, higher at night)
        if 12 <= hour <= 16:
            humidity = random.randint(25, 40)  # Dry during hot afternoon
        elif 6 <= hour <= 10:
            humidity = random.randint(40, 55)  # Morning
        else:
            humidity = random.randint(50, 65)  # Evening/night
    
    # Temperature - varies with time of day (Riyadh climate)
    if 12 <= hour <= 16:
        temperature = round(random.uniform(32, 42), 1)  # Hot afternoon
    elif 6 <= hour <= 10:
        temperature = round(random.uniform(22, 28), 1)  # Morning
    else:
        temperature = round(random.uniform(18, 25), 1)  # Evening/night
    
    # Temperature drops slightly during rain
    if is_raining:
        temperature = max(15, temperature - random.uniform(2, 5))
    
    # Wind speed - higher during rain events
    if is_raining:
        wind_speed = round(random.uniform(10, 25), 1)  # km/h
    else:
        wind_speed = round(random.uniform(5, 15), 1)  # km/h
    
    # Sensor status
    sensor_status = "active"
    if random.random() < 0.001:  # 0.1% chance of sensor issue
        sensor_status = "maintenance"
    
    # Alert triggered if heavy rain detected
    alert_triggered = intensity == "heavy" and rainfall_rate > 10.0
    
    # Location zone
    location_zone = random.choice(["north_lawn", "south_lawn", "east_lawn", "west_lawn", "central_plaza"])

    # Approximate instantaneous power draw (W)
    # Low-power sensor, slightly higher when alerting
    base_power_w = random.uniform(2.5, 4.5)
    alert_extra_power_w = 1.0 if alert_triggered else 0.0
    energy_consumption_w = base_power_w + alert_extra_power_w
    
    payload = {
        "deviceId": DEVICE_ID,
        "timestamp": timestamp_ms,
        "latitude": LAT,
        "longitude": LNG,
        "rainfall_rate_mmh": rainfall_rate,
        "rainfall_accumulated_mm": rainfall_accumulated,
        "precipitation_intensity": intensity,
        "temperature_c": temperature,
        "humidity_percent": humidity,
        "wind_speed_kmh": wind_speed,
        "sensor_status": sensor_status,
        "alert_triggered": alert_triggered,
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
    print(f"Rain Sensor simulator starting for device: {DEVICE_ID}")
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
                rain_info = f"Rate: {payload['rainfall_rate_mmh']} mm/h" if payload['rainfall_rate_mmh'] > 0 else "No rain"
                print(f"  {rain_info}, Temp: {payload['temperature_c']}°C, Humidity: {payload['humidity_percent']}%, Intensity: {payload['precipitation_intensity']}")
            else:
                print(f"[{now}] FAILED to publish, status={status}")

            time.sleep(SEND_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("Rain Sensor simulator interrupted, shutting down...")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()

