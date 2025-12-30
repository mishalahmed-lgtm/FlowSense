#!/bin/bash
# Run RS-RP-1 rain sensor simulator

cd "$(dirname "$0")/.."
source venv/bin/activate

MQTT_HOST=localhost MQTT_PORT=1884 ACCESS_TOKEN=murraba python3 scripts/rain_sensor_rsrp1_sim.py

