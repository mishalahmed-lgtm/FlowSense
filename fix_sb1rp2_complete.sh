#!/bin/bash
# Complete fix for SB1-RP-2: Activate device and verify configuration

echo "=========================================="
echo "FIXING SB1-RP-2 COMPLETE"
echo "=========================================="

# Step 1: Activate and configure SB1-RP-2
echo ""
echo "[1] Activating SB1-RP-2 device..."
docker exec iot-postgres psql -U iot_user -d iot_platform -c "
WITH ref_device AS (
    SELECT d.tenant_id, d.device_type_id
    FROM devices d
    JOIN tenants t ON d.tenant_id = t.id
    WHERE d.device_id IN ('AN-RP-1', 'ES-RP-1', 'SW-RP-1', 'SM1-RP-1', 'NS-RP-1', 'SM1-RP-2')
    AND t.code = '1234'
    LIMIT 1
)
INSERT INTO devices (device_id, name, device_type_id, tenant_id, is_active, is_provisioned, device_metadata)
SELECT 
    'SB1-RP-2',
    'Smart Bench 2',
    ref_device.device_type_id,
    ref_device.tenant_id,
    true,
    false,
    '{\"access_token\": \"murraba\", \"mqtt_topic\": \"device/SB1-RP-2/telemetry\"}'
FROM ref_device
ON CONFLICT (device_id) 
DO UPDATE SET
    is_active = true,
    device_metadata = '{\"access_token\": \"murraba\", \"mqtt_topic\": \"device/SB1-RP-2/telemetry\"}',
    tenant_id = (SELECT tenant_id FROM ref_device),
    device_type_id = (SELECT device_type_id FROM ref_device);
"

# Step 2: Verify device configuration
echo ""
echo "[2] Verifying SB1-RP-2 configuration..."
docker exec iot-postgres psql -U iot_user -d iot_platform -c "
SELECT 
    d.device_id, 
    d.name, 
    d.is_active, 
    d.device_metadata,
    dt.name as device_type_name,
    t.name as tenant_name
FROM devices d
LEFT JOIN device_types dt ON d.device_type_id = dt.id
LEFT JOIN tenants t ON d.tenant_id = t.id
WHERE d.device_id = 'SB1-RP-2';
"

# Step 3: Check if simulator is running
echo ""
echo "[3] Checking simulator status..."
if pgrep -f "smartbench_sb1rp2" > /dev/null; then
    echo "   ✓ Simulator is running"
    pgrep -f "smartbench_sb1rp2"
else
    echo "   ⚠ Simulator is NOT running"
fi

echo ""
echo "=========================================="
echo "✅ SB1-RP-2 FIXED!"
echo "=========================================="
echo ""
echo "To start the simulator:"
echo "cd /home/mishal/my-iot-project"
echo "source venv/bin/activate"
echo "MQTT_HOST=localhost MQTT_PORT=1884 ACCESS_TOKEN=murraba python3 scripts/smartbench_sb1rp2_sim.py &"
echo ""
echo "The device will appear on the map once it starts sending telemetry with location data."



