#!/bin/bash
# Run all simulation scripts for demo devices in the background

echo "Starting all simulation scripts for demo devices..."

# Smart Benches (4 devices)
docker-compose exec -d backend python3 /app/scripts/smart_bench_sim.py BENCH_ID=BENCH-CP-001
docker-compose exec -d backend python3 /app/scripts/smart_bench_sim.py BENCH_ID=BENCH-CP-002
docker-compose exec -d backend python3 /app/scripts/smart_bench_sim.py BENCH_ID=BENCH-DT-001
docker-compose exec -d backend python3 /app/scripts/smart_bench_sim.py BENCH_ID=BENCH-RW-001

# Smart Bins (5 devices)
docker-compose exec -d backend python3 /app/scripts/smart_bin_sim.py DEVICE_ID=BIN-MS-001
docker-compose exec -d backend python3 /app/scripts/smart_bin_sim.py DEVICE_ID=BIN-SM-001
docker-compose exec -d backend python3 /app/scripts/smart_bin_sim.py DEVICE_ID=BIN-CP-SG
docker-compose exec -d backend python3 /app/scripts/smart_bin_sim.py DEVICE_ID=BIN-CP-NG
docker-compose exec -d backend python3 /app/scripts/smart_bin_sim.py DEVICE_ID=BIN-RA-001

# Digital Kiosks (3 devices)
docker-compose exec -d backend python3 /app/scripts/digital_kiosk_sim.py KIOSK_DEVICE_ID=KIOSK-CC-001
docker-compose exec -d backend python3 /app/scripts/digital_kiosk_sim.py KIOSK_DEVICE_ID=KIOSK-TS-001
docker-compose exec -d backend python3 /app/scripts/digital_kiosk_sim.py KIOSK_DEVICE_ID=KIOSK-AP-001

# LPG Meters (2 devices)
docker-compose exec -d backend python3 /app/scripts/lpg_meter_sim.py DEVICE_ID=LPG-RA-101
docker-compose exec -d backend python3 /app/scripts/lpg_meter_sim.py DEVICE_ID=LPG-CB-001

# GPS Tracker (1 device)
docker-compose exec -d backend python3 /app/scripts/gps_tracker_sim.py DEVICE_ID=GPS-FM-001

echo "All simulation scripts started in background!"
echo "Check logs with: docker-compose logs -f backend"

