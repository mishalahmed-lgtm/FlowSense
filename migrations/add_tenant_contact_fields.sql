-- Migration: Add contact and business information fields to tenants table
-- Date: 2024
-- Description: Adds contact_email, contact_phone, business_address, and timezone fields
-- Note: PostgreSQL doesn't support IF NOT EXISTS for ALTER TABLE ADD COLUMN
-- Run the Python migration script instead, or check column existence manually

-- Add columns (run only if columns don't exist)
ALTER TABLE tenants ADD COLUMN contact_email VARCHAR(255);
ALTER TABLE tenants ADD COLUMN contact_phone VARCHAR(50);
ALTER TABLE tenants ADD COLUMN business_address TEXT;
ALTER TABLE tenants ADD COLUMN timezone VARCHAR(100) DEFAULT 'UTC';

-- Create index on contact_email for faster lookups
CREATE INDEX idx_tenants_contact_email ON tenants(contact_email);

-- Update existing tenants to have UTC timezone if NULL
UPDATE tenants SET timezone = 'UTC' WHERE timezone IS NULL;
