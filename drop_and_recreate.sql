-- Drop all tables and types, then recreate everything
-- This script will completely reset the database

-- Step 1: Drop all tables (CASCADE handles foreign keys)
DROP TABLE IF EXISTS devices_snapshot CASCADE;
DROP TABLE IF EXISTS fota_job_devices CASCADE;
DROP TABLE IF EXISTS alert_audit_logs CASCADE;
DROP TABLE IF EXISTS notifications CASCADE;
DROP TABLE IF EXISTS fota_jobs CASCADE;
DROP TABLE IF EXISTS alerts CASCADE;
DROP TABLE IF EXISTS device_health_history CASCADE;
DROP TABLE IF EXISTS pattern_analyses CASCADE;
DROP TABLE IF EXISTS predictions CASCADE;
DROP TABLE IF EXISTS analytics_jobs CASCADE;
DROP TABLE IF EXISTS device_health_metrics CASCADE;
DROP TABLE IF EXISTS device_firmware_status CASCADE;
DROP TABLE IF EXISTS firmware_versions CASCADE;
DROP TABLE IF EXISTS alert_rules CASCADE;
DROP TABLE IF EXISTS utility_invoices CASCADE;
DROP TABLE IF EXISTS utility_consumption CASCADE;
DROP TABLE IF EXISTS utility_tariffs CASCADE;
DROP TABLE IF EXISTS utility_device_contracts CASCADE;
DROP TABLE IF EXISTS telemetry_timeseries CASCADE;
DROP TABLE IF EXISTS telemetry_latest CASCADE;
DROP TABLE IF EXISTS device_dashboards CASCADE;
DROP TABLE IF EXISTS device_rules CASCADE;
DROP TABLE IF EXISTS provisioning_keys CASCADE;
DROP TABLE IF EXISTS external_integrations CASCADE;
DROP TABLE IF EXISTS correlation_results CASCADE;
DROP TABLE IF EXISTS ml_models CASCADE;
DROP TABLE IF EXISTS firmwares CASCADE;
DROP TABLE IF EXISTS cep_rules CASCADE;
DROP TABLE IF EXISTS devices CASCADE;
DROP TABLE IF EXISTS device_types CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS tenants CASCADE;

-- Step 2: Drop all custom types (enums)
DROP TYPE IF EXISTS userrole CASCADE;
DROP TYPE IF EXISTS alertpriority CASCADE;
DROP TYPE IF EXISTS alertstatus CASCADE;
DROP TYPE IF EXISTS firmwareupdatestatus CASCADE;
DROP TYPE IF EXISTS fotajobstatus CASCADE;
DROP TYPE IF EXISTS analyticsjobtype CASCADE;
DROP TYPE IF EXISTS analyticsjobstatus CASCADE;

-- Step 3: Now run init_db.py or use SQLAlchemy to recreate tables
-- The tables will be recreated by models.py when you run the application

