#!/bin/bash
# Run SB-RP-2 simulator

cd "$(dirname "$0")/.." || exit

# Activate virtual environment if it exists
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Set environment variables
export MQTT_HOST=localhost
export MQTT_PORT=1884
export ACCESS_TOKEN=murraba
export DEVICE_ID=SB-RP-2
export BIN_ID=sb_rp_2

echo "Starting SB-RP-2 simulator..."
echo "MQTT_HOST: $MQTT_HOST"
echo "MQTT_PORT: $MQTT_PORT"
echo "ACCESS_TOKEN: $ACCESS_TOKEN"
echo "DEVICE_ID: $DEVICE_ID"
echo "BIN_ID: $BIN_ID"
echo ""

# Run the simulator
python3 scripts/smart_bin_sbrp2_sim.py

