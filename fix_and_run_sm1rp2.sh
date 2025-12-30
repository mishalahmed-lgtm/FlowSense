#!/bin/bash
# Fix SM1-RP-2 registration and run the simulator

echo "=========================================="
echo "FIXING SM1-RP-2 DEVICE REGISTRATION"
echo "=========================================="

# Fix SM1-RP-2 in database
docker exec iot-postgres psql -U iot_user -d iot_platform -c "
WITH ref_device AS (
    SELECT d.tenant_id, d.device_type_id
    FROM devices d
    JOIN tenants t ON d.tenant_id = t.id
    WHERE d.device_id IN ('AN-RP-1', 'ES-RP-1', 'SW-RP-1', 'SM1-RP-1')
    AND t.code = '1234'
    LIMIT 1
)
INSERT INTO devices (device_id, name, device_type_id, tenant_id, is_active, is_provisioned, device_metadata)
SELECT 
    'SM1-RP-2',
    'Smart Bench 2',
    ref_device.device_type_id,
    ref_device.tenant_id,
    true,
    false,
    '{\"access_token\": \"murraba\", \"mqtt_topic\": \"device/SM1-RP-2/telemetry\"}'
FROM ref_device
ON CONFLICT (device_id) 
DO UPDATE SET
    is_active = true,
    device_metadata = '{\"access_token\": \"murraba\", \"mqtt_topic\": \"device/SM1-RP-2/telemetry\"}',
    tenant_id = (SELECT tenant_id FROM ref_device),
    device_type_id = (SELECT device_type_id FROM ref_device);
"

echo ""
echo "Verifying SM1-RP-2 configuration..."
docker exec iot-postgres psql -U iot_user -d iot_platform -c "SELECT d.device_id, d.name, d.is_active, d.device_metadata FROM devices d WHERE d.device_id = 'SM1-RP-2';"

echo ""
echo "=========================================="
echo "STARTING SM1-RP-2 SIMULATOR"
echo "=========================================="

cd "$(dirname "$0")"
source venv/bin/activate

MQTT_HOST=localhost MQTT_PORT=1884 ACCESS_TOKEN=murraba python3 scripts/smartbench_sm1rp2_sim.py

