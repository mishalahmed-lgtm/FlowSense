#!/bin/bash
# Fix SB1-RP-2, ES-RP-3, and SB-RP-3: Activate them and ensure they have location data

echo "=========================================="
echo "FIXING DEVICES FOR MAP (SB1-RP-2, ES-RP-3, SB-RP-3)"
echo "=========================================="

# Fix SB1-RP-2
echo ""
echo "Fixing SB1-RP-2 (Smart Bench 2)..."
docker exec iot-postgres psql -U iot_user -d iot_platform -c "
WITH ref_device AS (
    SELECT d.tenant_id, d.device_type_id
    FROM devices d
    JOIN tenants t ON d.tenant_id = t.id
    WHERE d.device_id IN ('AN-RP-1', 'ES-RP-1', 'SW-RP-1', 'SM1-RP-1', 'NS-RP-1')
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

# Fix ES-RP-3
echo ""
echo "Fixing ES-RP-3 (E-Scooter 3)..."
docker exec iot-postgres psql -U iot_user -d iot_platform -c "
WITH ref_device AS (
    SELECT d.tenant_id, d.device_type_id
    FROM devices d
    JOIN tenants t ON d.tenant_id = t.id
    WHERE d.device_id IN ('AN-RP-1', 'ES-RP-1', 'SW-RP-1', 'SM1-RP-1', 'NS-RP-1')
    AND t.code = '1234'
    LIMIT 1
)
INSERT INTO devices (device_id, name, device_type_id, tenant_id, is_active, is_provisioned, device_metadata)
SELECT 
    'ES-RP-3',
    'E-Scooter 3',
    ref_device.device_type_id,
    ref_device.tenant_id,
    true,
    false,
    '{\"access_token\": \"murraba\", \"mqtt_topic\": \"device/ES-RP-3/telemetry\"}'
FROM ref_device
ON CONFLICT (device_id) 
DO UPDATE SET
    is_active = true,
    device_metadata = '{\"access_token\": \"murraba\", \"mqtt_topic\": \"device/ES-RP-3/telemetry\"}',
    tenant_id = (SELECT tenant_id FROM ref_device),
    device_type_id = (SELECT device_type_id FROM ref_device);
"

# Fix SB-RP-3
echo ""
echo "Fixing SB-RP-3 (Smart Bin 3)..."
docker exec iot-postgres psql -U iot_user -d iot_platform -c "
WITH ref_device AS (
    SELECT d.tenant_id, d.device_type_id
    FROM devices d
    JOIN tenants t ON d.tenant_id = t.id
    WHERE d.device_id IN ('AN-RP-1', 'ES-RP-1', 'SW-RP-1', 'SM1-RP-1', 'NS-RP-1', 'SB-RP-1', 'SB-RP-2')
    AND t.code = '1234'
    LIMIT 1
)
INSERT INTO devices (device_id, name, device_type_id, tenant_id, is_active, is_provisioned, device_metadata)
SELECT 
    'SB-RP-3',
    'Smart Bin 3',
    ref_device.device_type_id,
    ref_device.tenant_id,
    true,
    false,
    '{\"access_token\": \"murraba\", \"mqtt_topic\": \"device/SB-RP-3/telemetry\"}'
FROM ref_device
ON CONFLICT (device_id) 
DO UPDATE SET
    is_active = true,
    device_metadata = '{\"access_token\": \"murraba\", \"mqtt_topic\": \"device/SB-RP-3/telemetry\"}',
    tenant_id = (SELECT tenant_id FROM ref_device),
    device_type_id = (SELECT device_type_id FROM ref_device);
"

echo ""
echo "Verifying device configurations..."
docker exec iot-postgres psql -U iot_user -d iot_platform -c "SELECT d.device_id, d.name, d.is_active FROM devices d WHERE d.device_id IN ('SB1-RP-2', 'ES-RP-3', 'SB-RP-3');"

echo ""
echo "=========================================="
echo "✅ DEVICES ACTIVATED!"
echo "=========================================="
echo ""
echo "Next steps - Start simulators:"
echo ""
echo "1. SB1-RP-2:"
echo "   MQTT_HOST=localhost MQTT_PORT=1884 ACCESS_TOKEN=murraba python3 scripts/smartbench_sb1rp2_sim.py &"
echo ""
echo "2. ES-RP-3:"
echo "   MQTT_HOST=localhost MQTT_PORT=1884 ACCESS_TOKEN=murraba python3 scripts/escooter_esrp3_sim.py &"
echo ""
echo "3. SB-RP-3:"
echo "   MQTT_HOST=localhost MQTT_PORT=1884 ACCESS_TOKEN=murraba python3 scripts/smart_bin_sbrp3_sim.py &"
echo ""
echo "Devices will appear on the map once they start sending telemetry with location data."



