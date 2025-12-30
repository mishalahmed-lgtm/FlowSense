-- Fix DK-RP-2 device type
-- Change from Valve Controller to generic MQTT or Digital Kiosk

-- First, check current state
SELECT d.device_id, d.name, dt.name as device_type_name, dt.id as device_type_id
FROM devices d
JOIN device_types dt ON d.device_type_id = dt.id
WHERE d.device_id = 'DK-RP-2';

-- Update to generic MQTT device type (preferred)
UPDATE devices
SET device_type_id = (
    SELECT id FROM device_types 
    WHERE name = 'MQTT' AND protocol = 'MQTT' 
    LIMIT 1
)
WHERE device_id = 'DK-RP-2'
AND device_type_id != (
    SELECT id FROM device_types 
    WHERE name = 'MQTT' AND protocol = 'MQTT' 
    LIMIT 1
);

-- Verify the change
SELECT d.device_id, d.name, dt.name as device_type_name
FROM devices d
JOIN device_types dt ON d.device_type_id = dt.id
WHERE d.device_id = 'DK-RP-2';

