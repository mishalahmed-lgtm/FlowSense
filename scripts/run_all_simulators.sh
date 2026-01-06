#!/bin/bash
# Run all simulator scripts in the scripts/ folder
# This script runs simulators from the host machine, connecting to MQTT on localhost:1884

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT" || exit

# Activate virtual environment if it exists
if [ -f "$PROJECT_ROOT/venv/bin/activate" ]; then
    source "$PROJECT_ROOT/venv/bin/activate"
    echo "Virtual environment activated"
elif [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
    source "$PROJECT_ROOT/.venv/bin/activate"
    echo "Virtual environment activated"
fi

# Common environment variables for all simulators (running from host)
export MQTT_HOST=localhost
export MQTT_PORT=1884
export ACCESS_TOKEN=murabba-demo-token

# Stop any existing simulators
echo "Stopping any existing simulators..."
pkill -f 'python.*sim\.py' 2>/dev/null || true
sleep 2

echo ""
echo "============================================================"
echo "Starting all simulator scripts..."
echo "============================================================"
echo ""

# Counter for tracking
COUNT=0

# Function to start a simulator
start_sim() {
    local script_name=$1
    local env_vars=$2
    local log_file=$3
    
    if [ -f "$PROJECT_ROOT/simulators/$script_name" ]; then
        COUNT=$((COUNT + 1))
        eval "$env_vars nohup python \"$PROJECT_ROOT/simulators/$script_name\" > \"$log_file\" 2>&1 &"
        echo "  [$COUNT] ✓ $script_name (PID: $!)"
    else
        echo "  [SKIP] ✗ $script_name (not found)"
    fi
}

# Murabba tenant simulators
echo "--- Murabba Tenant Simulators ---"
start_sim "escooter_esrp1_sim.py" "" "/tmp/escooter_esrp1.log"
start_sim "escooter_esrp2_sim.py" "" "/tmp/escooter_esrp2.log"
start_sim "escooter_esrp3_sim.py" "" "/tmp/escooter_esrp3.log"
start_sim "smart_bin_sim.py" "DEVICE_ID=SB-RP-1" "/tmp/smart_bin_sb_rp1.log"
start_sim "smart_bin_sim.py" "DEVICE_ID=SM1-RP" "/tmp/smart_bin_sm1_rp.log"
start_sim "smart_bin_sbrp2_sim.py" "" "/tmp/smart_bin_sbrp2.log"
start_sim "smart_bin_sbrp3_sim.py" "" "/tmp/smart_bin_sbrp3.log"
start_sim "washroom_swrp1_sim.py" "" "/tmp/washroom_swrp1.log"
start_sim "fitness_sgrp1_sim.py" "" "/tmp/fitness_sgrp1.log"
start_sim "noise_anrp1_sim.py" "" "/tmp/noise_anrp1.log"
start_sim "noise_anrp2_sim.py" "" "/tmp/noise_anrp2.log"
start_sim "noise_nsrp2_sim.py" "" "/tmp/noise_nsrp2.log"
start_sim "recycle_srrp1_sim.py" "" "/tmp/recycle_srrp1.log"
start_sim "digital_kiosk_sim.py" "KIOSK_DEVICE_ID=DK_MP-1" "/tmp/digital_kiosk_dk_mp1.log"
start_sim "digital_kiosk_dkrp2_sim.py" "" "/tmp/digital_kiosk_dkrp2.log"
start_sim "smart_bench_sim.py" "BENCH_ID=BENCH-RP-1" "/tmp/smart_bench_bench_rp1.log"
start_sim "smartbench_sb1rp2_sim.py" "" "/tmp/smartbench_sb1rp2.log"
start_sim "smartbench_sm1rp2_sim.py" "" "/tmp/smartbench_sm1rp2.log"
start_sim "lightpole_plprp1_sim.py" "" "/tmp/lightpole_plprp1.log"
start_sim "master_water_sensor_sim.py" "DEVICE_ID=MW-RP-1 ACCESS_TOKEN=murabba" "/tmp/master_water_sensor.log"
start_sim "rain_sensor_rsrp1_sim.py" "" "/tmp/rain_sensor_rsrp1.log"

# Generic simulators (may need device IDs)
echo ""
echo "--- Generic Simulators ---"
start_sim "escooter_sim.py" "" "/tmp/escooter_generic.log"
start_sim "smart_bin_sim.py" "DEVICE_ID=BIN-MS-001" "/tmp/smart_bin_bin_ms001.log"
start_sim "washroom_sim.py" "" "/tmp/washroom_generic.log"
start_sim "fitness_rower_sim.py" "" "/tmp/fitness_rower_generic.log"
start_sim "noise_sensor_sim.py" "" "/tmp/noise_sensor_generic.log"
start_sim "recycle_kiosk_sim.py" "" "/tmp/recycle_kiosk_generic.log"
start_sim "digital_kiosk_sim.py" "KIOSK_DEVICE_ID=KIOSK-CC-001" "/tmp/digital_kiosk_kiosk_cc001.log"
start_sim "smart_bench_sim.py" "BENCH_ID=BENCH-CP-001" "/tmp/smart_bench_bench_cp001.log"
start_sim "lightpole_sim.py" "" "/tmp/lightpole_generic.log"
start_sim "lpg_meter_sim.py" "DEVICE_ID=LPG-RA-101" "/tmp/lpg_meter_lpg_ra101.log"
start_sim "gps_tracker_sim.py" "DEVICE_ID=GPS-FM-001" "/tmp/gps_tracker_gps_fm001.log"
start_sim "valve_controller_sim.py" "" "/tmp/valve_controller.log"
start_sim "comcore_dlms_sim.py" "" "/tmp/comcore_dlms.log"
start_sim "comcore_ami_sim.py" "" "/tmp/comcore_ami.log"
start_sim "dc41x_manhole_sim.py" "" "/tmp/dc41x_manhole.log"

echo ""
echo "============================================================"
echo "Started $COUNT simulator scripts!"
echo "============================================================"
echo ""
echo "To check if they're running:"
echo "  ps aux | grep -E 'python.*sim\.py' | grep -v grep"
echo ""
echo "To view logs (examples):"
echo "  tail -f /tmp/escooter_esrp1.log"
echo "  tail -f /tmp/smart_bin_sb_rp1.log"
echo "  tail -f /tmp/master_water_sensor.log"
echo ""
echo "To stop all simulators:"
echo "  pkill -f 'python.*sim\.py'"
echo ""

