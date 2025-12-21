#!/bin/bash
# Quick command to run all simulation scripts for demo devices

echo "🚀 Starting all simulation scripts for demo devices..."
echo ""

# Smart Benches (4 devices)
echo "Starting Smart Bench simulators..."
docker-compose exec -d backend bash -c "BENCH_ID=BENCH-CP-001 python3 /app/scripts/smart_bench_sim.py" &
docker-compose exec -d backend bash -c "BENCH_ID=BENCH-CP-002 python3 /app/scripts/smart_bench_sim.py" &
docker-compose exec -d backend bash -c "BENCH_ID=BENCH-DT-001 python3 /app/scripts/smart_bench_sim.py" &
docker-compose exec -d backend bash -c "BENCH_ID=BENCH-RW-001 python3 /app/scripts/smart_bench_sim.py" &

# Smart Bins (5 devices)
echo "Starting Smart Bin simulators..."
docker-compose exec -d backend bash -c "BIN_DEVICE_ID=BIN-MS-001 python3 /app/scripts/smart_bin_sim.py" &
docker-compose exec -d backend bash -c "BIN_DEVICE_ID=BIN-SM-001 python3 /app/scripts/smart_bin_sim.py" &
docker-compose exec -d backend bash -c "BIN_DEVICE_ID=BIN-CP-SG python3 /app/scripts/smart_bin_sim.py" &
docker-compose exec -d backend bash -c "BIN_DEVICE_ID=BIN-CP-NG python3 /app/scripts/smart_bin_sim.py" &
docker-compose exec -d backend bash -c "BIN_DEVICE_ID=BIN-RA-001 python3 /app/scripts/smart_bin_sim.py" &

# Digital Kiosks (3 devices)
echo "Starting Digital Kiosk simulators..."
docker-compose exec -d backend bash -c "KIOSK_DEVICE_ID=KIOSK-CC-001 python3 /app/scripts/digital_kiosk_sim.py" &
docker-compose exec -d backend bash -c "KIOSK_DEVICE_ID=KIOSK-TS-001 python3 /app/scripts/digital_kiosk_sim.py" &
docker-compose exec -d backend bash -c "KIOSK_DEVICE_ID=KIOSK-AP-001 python3 /app/scripts/digital_kiosk_sim.py" &

# LPG Meters (2 devices) - HTTP protocol
echo "Starting LPG Meter simulators (HTTP)..."
docker-compose exec -d backend bash -c "LPG_DEVICE_ID=LPG-RA-101 ADMIN_EMAIL=demo@flowsense.com ADMIN_PASSWORD=demo123 IOT_API_BASE=http://localhost:5000/api/v1 python3 /app/scripts/lpg_meter_sim.py" &
docker-compose exec -d backend bash -c "LPG_DEVICE_ID=LPG-CB-001 ADMIN_EMAIL=demo@flowsense.com ADMIN_PASSWORD=demo123 IOT_API_BASE=http://localhost:5000/api/v1 python3 /app/scripts/lpg_meter_sim.py" &

# GPS Tracker (1 device) - HTTP protocol
echo "Starting GPS Tracker simulator (HTTP)..."
docker-compose exec -d backend bash -c "GPS_DEVICE_ID=GPS-FM-001 ADMIN_EMAIL=demo@flowsense.com ADMIN_PASSWORD=demo123 IOT_API_BASE=http://localhost:5000/api/v1 python3 /app/scripts/gps_tracker_sim.py" &

echo ""
echo "✅ All 15 simulation scripts started in background!"
echo ""
echo "To check if they're running:"
echo "  docker-compose exec backend ps aux | grep sim"
echo ""
echo "To view logs:"
echo "  docker-compose logs -f backend | grep -i sim"

