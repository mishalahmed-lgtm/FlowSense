#!/bin/bash
# Run 8 out of 10 Murabba device simulation scripts
# Excludes: SR-RP-1 (Recycling Kiosk) and SW-RP-1 (Smart Washroom)

cd "$(dirname "$0")/.." || exit
source venv/bin/activate

export MQTT_HOST=localhost
export MQTT_PORT=1884
export ACCESS_TOKEN=murabba-demo-token

# Stop any existing simulators
pkill -f 'python.*sim\.py' 2>/dev/null || true
sleep 1

echo "Starting 8 Murabba device simulators..."
echo ""

# 1. E-Scooter (ES-RP-1)
nohup python scripts/escooter_esrp1_sim.py > /tmp/escooter_esrp1.log 2>&1 &
echo "  ✓ ES-RP-1 (E-Scooter) - PID: $!"

# 2. Smart Bin (SB-RP-1)
DEVICE_ID=SB-RP-1 nohup python scripts/smart_bin_sim.py > /tmp/smart_bin_sb.log 2>&1 &
echo "  ✓ SB-RP-1 (Smart Bin) - PID: $!"

# 3. Fitness Rower (SG-RP-1)
nohup python scripts/fitness_sgrp1_sim.py > /tmp/fitness_sgrp1.log 2>&1 &
echo "  ✓ SG-RP-1 (Fitness Rower) - PID: $!"

# 4. Noise Sensor (AN-RP-1)
nohup python scripts/noise_anrp1_sim.py > /tmp/noise_anrp1.log 2>&1 &
echo "  ✓ AN-RP-1 (Noise Sensor) - PID: $!"

# 5. Digital Kiosk (DK_MP-1)
KIOSK_DEVICE_ID=DK_MP-1 nohup python scripts/digital_kiosk_sim.py > /tmp/digital_kiosk.log 2>&1 &
echo "  ✓ DK_MP-1 (Digital Kiosk) - PID: $!"

# 6. Smart Bench (SM1-RP)
BENCH_ID=SM1-RP nohup python scripts/smart_bench_sim.py > /tmp/smart_bench.log 2>&1 &
echo "  ✓ SM1-RP (Smart Bench) - PID: $!"

# 7. Pathway Light (PLP-RP-1)
DEVICE_ID=PLP-RP-1 nohup python scripts/lightpole_plprp1_sim.py > /tmp/lightpole_plprp1.log 2>&1 &
echo "  ✓ PLP-RP-1 (Pathway Light) - PID: $!"

# 8. Master Water Sensor (MW-RP-1)
DEVICE_ID=MW-RP-1 ACCESS_TOKEN=murabba nohup python scripts/master_water_sensor_sim.py > /tmp/master_water_sensor.log 2>&1 &
echo "  ✓ MW-RP-1 (Master Water Sensor) - PID: $!"

echo ""
echo "All 8 simulators started!"
echo ""
echo "To check if they're running:"
echo "  ps aux | grep -E 'python.*sim\.py' | grep -v grep"
echo ""
echo "To view logs:"
echo "  tail -f /tmp/escooter_esrp1.log"
echo "  tail -f /tmp/smart_bin_sb.log"
echo "  tail -f /tmp/fitness_sgrp1.log"
echo "  tail -f /tmp/noise_anrp1.log"
echo "  tail -f /tmp/digital_kiosk.log"
echo "  tail -f /tmp/smart_bench.log"
echo "  tail -f /tmp/lightpole_plprp1.log"
echo "  tail -f /tmp/master_water_sensor.log"
echo ""
echo "To stop all simulators:"
echo "  pkill -f 'python.*sim\.py'"

