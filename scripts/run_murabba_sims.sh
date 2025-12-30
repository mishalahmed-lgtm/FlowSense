#!/bin/bash
# Run all Murabba device simulators from the host
# These connect to the MQTT broker exposed on localhost:1884

echo "Starting all Murabba device simulators..."
echo "Make sure you have activated the virtual environment: source .venv/bin/activate"
echo ""

# Get the project root directory (parent of scripts/)
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT" || exit

# Activate virtual environment if it exists
if [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
    source "$PROJECT_ROOT/.venv/bin/activate"
    echo "Virtual environment activated"
fi

# Common environment variables for all Murabba devices
export MQTT_HOST=localhost
export MQTT_PORT=1884
export ACCESS_TOKEN=murabba-demo-token

# Run each simulator in the background
echo "Starting E-Scooter (ES-RP-1)..."
nohup python "$PROJECT_ROOT/scripts/escooter_esrp1_sim.py" > /tmp/escooter_esrp1.log 2>&1 &
echo "  PID: $!"

echo "Starting Smart Bin (SM1-RP)..."
DEVICE_ID=SM1-RP nohup python "$PROJECT_ROOT/scripts/smart_bin_sim.py" > /tmp/smart_bin.log 2>&1 &
echo "  PID: $!"

echo "Starting Smart Bin (SB-RP-1)..."
DEVICE_ID=SB-RP-1 nohup python "$PROJECT_ROOT/scripts/smart_bin_sim.py" > /tmp/smart_bin_sb.log 2>&1 &
echo "  PID: $!"

echo "Starting Washroom (SW-RP-1)..."
nohup python "$PROJECT_ROOT/scripts/washroom_swrp1_sim.py" > /tmp/washroom_swrp1.log 2>&1 &
echo "  PID: $!"

echo "Starting Fitness Rower (SG-RP-1)..."
nohup python "$PROJECT_ROOT/scripts/fitness_sgrp1_sim.py" > /tmp/fitness_sgrp1.log 2>&1 &
echo "  PID: $!"

echo "Starting Noise Sensor (AN-RP-1)..."
nohup python "$PROJECT_ROOT/scripts/noise_anrp1_sim.py" > /tmp/noise_anrp1.log 2>&1 &
echo "  PID: $!"

echo "Starting Recycle Kiosk (SR-RP-1)..."
nohup python "$PROJECT_ROOT/scripts/recycle_srrp1_sim.py" > /tmp/recycle_srrp1.log 2>&1 &
echo "  PID: $!"

echo "Starting Digital Kiosk (DK_MP-1)..."
KIOSK_DEVICE_ID=DK_MP-1 nohup python "$PROJECT_ROOT/scripts/digital_kiosk_sim.py" > /tmp/digital_kiosk.log 2>&1 &
echo "  PID: $!"

echo "Starting Smart Bench (BENCH-RP-1)..."
BENCH_ID=BENCH-RP-1 nohup python "$PROJECT_ROOT/scripts/smart_bench_sim.py" > /tmp/smart_bench.log 2>&1 &
echo "  PID: $!"

echo "Starting Pathway Lights (PLP-RP-1)..."
DEVICE_ID=PLP-RP-1 nohup python "$PROJECT_ROOT/scripts/lightpole_plprp1_sim.py" > /tmp/lightpole_plprp1.log 2>&1 &
echo "  PID: $!"

echo "Starting Master Water Sensor (MW-RP-1)..."
DEVICE_ID=MW-RP-1 ACCESS_TOKEN=murabba nohup python "$PROJECT_ROOT/scripts/master_water_sensor_sim.py" > /tmp/master_water_sensor.log 2>&1 &
echo "  PID: $!"

echo ""
echo "All simulators started in background!"
echo ""
echo "To check if they're running:"
echo "  ps aux | grep -E 'python.*sim\.py' | grep -v grep"
echo ""
echo "To view logs:"
echo "  tail -f /tmp/escooter_esrp1.log"
echo "  tail -f /tmp/smart_bin.log          # SM1-RP"
echo "  tail -f /tmp/smart_bin_sb.log        # SB-RP-1"
echo "  tail -f /tmp/washroom_swrp1.log"
echo "  tail -f /tmp/fitness_sgrp1.log"
echo "  tail -f /tmp/noise_anrp1.log"
echo "  tail -f /tmp/recycle_srrp1.log"
echo "  tail -f /tmp/digital_kiosk.log       # DK_MP-1"
echo "  tail -f /tmp/smart_bench.log"
echo "  tail -f /tmp/lightpole_plprp1.log"
echo "  tail -f /tmp/master_water_sensor.log"
echo ""
echo "To stop all simulators:"
echo "  pkill -f 'python.*sim\.py'"

