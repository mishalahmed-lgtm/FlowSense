#!/bin/bash
# Update last_seen for 50 devices using SQL

PGPASSWORD="cuhaltp9kZ7eeCPzrD5roodGh7IIMZc" psql \
  "postgresql://iot_user:cuhaltp9kZ7eeCPzrD5roodGh7IIMZc@dpg-d5afr5euk2gs73enm170-a.virginia-postgres.render.com/iot_platform?sslmode=require" \
  << 'SQL'

-- Update 50 devices with fresh last_seen timestamp
UPDATE devices_snapshot 
SET payload = jsonb_set(
    jsonb_set(
        payload, 
        '{health,last_seen_at}', 
        to_jsonb(NOW()::text), 
        true
    ),
    '{telemetry,updated_at}', 
    to_jsonb(NOW()::text), 
    true
)
WHERE id IN (
    SELECT id 
    FROM devices_snapshot 
    WHERE tenant_id = 2 
    LIMIT 50
);

-- Show count of recently updated devices
SELECT 
    COUNT(*) as devices_updated_just_now,
    MIN((payload->'health'->>'last_seen_at')::timestamp) as oldest_lastseen,
    MAX((payload->'health'->>'last_seen_at')::timestamp) as newest_lastseen
FROM devices_snapshot 
WHERE tenant_id = 2 
AND (payload->'health'->>'last_seen_at')::timestamp > NOW() - INTERVAL '5 minutes';

SQL

