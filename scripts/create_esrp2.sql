-- Create ES-RP-2 device if it doesn't exist
-- First, get the tenant_id and device_type_id from ES-RP-1

DO $$
DECLARE
    v_tenant_id INTEGER;
    v_device_type_id INTEGER;
    v_device_exists BOOLEAN;
BEGIN
    -- Get tenant_id and device_type_id from ES-RP-1
    SELECT tenant_id, device_type_id INTO v_tenant_id, v_device_type_id
    FROM devices
    WHERE device_id = 'ES-RP-1'
    LIMIT 1;
    
    -- Check if ES-RP-2 already exists
    SELECT EXISTS(SELECT 1 FROM devices WHERE device_id = 'ES-RP-2') INTO v_device_exists;
    
    IF v_device_exists THEN
        -- Update existing ES-RP-2
        UPDATE devices
        SET device_metadata = '{"access_token": "murraba", "mqtt_topic": "device/ES-RP-2/telemetry"}',
            is_active = true,
            tenant_id = COALESCE(tenant_id, v_tenant_id),
            device_type_id = COALESCE(device_type_id, v_device_type_id)
        WHERE device_id = 'ES-RP-2';
        RAISE NOTICE 'ES-RP-2 updated';
    ELSE
        -- Create new ES-RP-2
        INSERT INTO devices (device_id, name, device_type_id, tenant_id, is_active, is_provisioned, device_metadata)
        VALUES (
            'ES-RP-2',
            'E-Scooter 2',
            v_device_type_id,
            v_tenant_id,
            true,
            false,
            '{"access_token": "murraba", "mqtt_topic": "device/ES-RP-2/telemetry"}'
        );
        RAISE NOTICE 'ES-RP-2 created';
    END IF;
END $$;

-- Verify
SELECT device_id, name, is_active, device_metadata FROM devices WHERE device_id = 'ES-RP-2';

