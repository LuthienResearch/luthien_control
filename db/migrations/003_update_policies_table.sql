-- Migration 003: Update policies table schema to match models.py
-- Align policies table with luthien_control.db.models.Policy

-- Ensure transaction safety
BEGIN;

-- Drop the old UUID primary key constraint
-- Note: The constraint name might be different (e.g., policies_policy_id_pkey).
-- Use \d policies in psql to check the exact name if this fails.
ALTER TABLE policies DROP CONSTRAINT policies_pkey;

-- Drop the old UUID primary key column
ALTER TABLE policies DROP COLUMN policy_id;

-- Drop the old JSONB definition column
ALTER TABLE policies DROP COLUMN definition;

-- Add the new SERIAL primary key column
-- SERIAL implicitly creates sequence, sets primary key, and NOT NULL
ALTER TABLE policies ADD COLUMN id SERIAL PRIMARY KEY;

-- Add other missing columns to match the Policy model
ALTER TABLE policies ADD COLUMN policy_class_path TEXT; -- Using TEXT for flexibility
ALTER TABLE policies ADD COLUMN config JSONB; -- Nullable as per model
ALTER TABLE policies ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE; -- Matches model default
ALTER TABLE policies ADD COLUMN description TEXT; -- Nullable as per model
ALTER TABLE policies ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(); -- Matches model default

-- Add a comment to the table indicating the schema change
COMMENT ON TABLE policies IS 'Schema updated by 003 migration to match db.models.Policy: Added id (serial pk), policy_class_path, config, is_active, description, updated_at. Dropped policy_id (uuid pk) and definition.';

-- Commit the transaction
COMMIT; 