-- Fix RS-RP-1 rain sensor device registration
-- Ensure it exists, is active, and has correct access token

-- First, check if RS-RP-1 exists
SELECT d.device_id, d.name, d.is_active, d.device_metadata, dt.name as device_type_name, t.name as tenant_name
FROM devices d
LEFT JOIN device_types dt ON d.device_type_id = dt.id
LEFT JOIN tenants t ON d.tenant_id = t.id
WHERE d.device_id = 'RS-RP-1';

-- Get reference device info (AN-RP-1 or ES-RP-1 from Murabba tenant)
SELECT d.device_id, d.tenant_id, d.device_type_id, t.code as tenant_code
FROM devices d
JOIN tenants t ON d.tenant_id = t.id
WHERE d.device_id IN ('AN-RP-1', 'ES-RP-1', 'SW-RP-1')
AND t.code = '1234'
LIMIT 1;

-- Insert or update RS-RP-1
-- First, try to get tenant_id and device_type_id from a reference device
WITH ref_device AS (
    SELECT d.tenant_id, d.device_type_id
    FROM devices d
    JOIN tenants t ON d.tenant_id = t.id
    WHERE d.device_id IN ('AN-RP-1', 'ES-RP-1', 'SW-RP-1')
    AND t.code = '1234'
    LIMIT 1
)
INSERT INTO devices (device_id, name, device_type_id, tenant_id, is_active, is_provisioned, device_metadata)
SELECT 
    'RS-RP-1',
    'Rain Sensor 1',
    ref_device.device_type_id,
    ref_device.tenant_id,
    true,
    false,
    '{"access_token": "murraba", "mqtt_topic": "device/RS-RP-1/telemetry"}'
FROM ref_device
ON CONFLICT (device_id) 
DO UPDATE SET
    is_active = true,
    device_metadata = '{"access_token": "murraba", "mqtt_topic": "device/RS-RP-1/telemetry"}',
    tenant_id = (SELECT tenant_id FROM ref_device),
    device_type_id = (SELECT device_type_id FROM ref_device);

-- Verify the fix
SELECT d.device_id, d.name, d.is_active, d.device_metadata, dt.name as device_type_name, t.name as tenant_name
FROM devices d
LEFT JOIN device_types dt ON d.device_type_id = dt.id
LEFT JOIN tenants t ON d.tenant_id = t.id
WHERE d.device_id = 'RS-RP-1';

