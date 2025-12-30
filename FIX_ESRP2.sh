#!/bin/bash
set -e

echo "=========================================="
echo "FIXING ES-RP-2 DEVICE REGISTRATION"
echo "=========================================="

# Step 1: Create/Update ES-RP-2 in database
echo ""
echo "Step 1: Creating/Updating ES-RP-2 device..."
docker exec iot-postgres psql -U iot_user -d iot_platform << 'SQL'
-- Insert or update ES-RP-2
INSERT INTO devices (device_id, name, device_type_id, tenant_id, is_active, is_provisioned, device_metadata)
SELECT 
    'ES-RP-2',
    'E-Scooter 2',
    device_type_id,
    tenant_id,
    true,
    false,
    '{"access_token": "murraba", "mqtt_topic": "device/ES-RP-2/telemetry"}'
FROM devices
WHERE device_id = 'ES-RP-1'
ON CONFLICT (device_id) DO UPDATE
SET 
    device_metadata = '{"access_token": "murraba", "mqtt_topic": "device/ES-RP-2/telemetry"}',
    is_active = true,
    device_type_id = EXCLUDED.device_type_id,
    tenant_id = EXCLUDED.tenant_id;

-- Verify
SELECT device_id, name, is_active, device_metadata FROM devices WHERE device_id = 'ES-RP-2';
SQL

echo ""
echo "Step 2: Checking if simulator is running..."
if pgrep -f "escooter_esrp2" > /dev/null; then
    echo "  ✓ Simulator is running"
    ps aux | grep escooter_esrp2 | grep -v grep
else
    echo "  ✗ Simulator is NOT running"
    echo ""
    echo "Starting simulator..."
    cd /home/mishal/my-iot-project
    source venv/bin/activate 2>/dev/null || true
    nohup python3 scripts/escooter_esrp2_sim.py > /tmp/escooter_esrp2.log 2>&1 &
    sleep 2
    if pgrep -f "escooter_esrp2" > /dev/null; then
        echo "  ✓ Simulator started (PID: $(pgrep -f escooter_esrp2))"
    else
        echo "  ✗ Failed to start simulator"
    fi
fi

echo ""
echo "Step 3: Checking backend logs for ES-RP-2..."
docker logs iot-backend 2>&1 | grep -i "ES-RP-2" | tail -5 || echo "  No recent ES-RP-2 messages in logs"

echo ""
echo "=========================================="
echo "DONE! Check the output above."
echo "=========================================="
echo ""
echo "To monitor simulator: tail -f /tmp/escooter_esrp2.log"
echo "To check backend: docker logs iot-backend -f | grep ES-RP-2"

