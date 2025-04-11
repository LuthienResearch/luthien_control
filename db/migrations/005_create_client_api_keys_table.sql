-- Migration to create the client_api_keys table
-- Corresponds to the ClientApiKey model in db/models.py

CREATE TABLE client_api_keys (
    id SERIAL PRIMARY KEY,
    key_value TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata_ JSONB NULL
);

-- Add index for faster lookups by name (key_value is indexed by UNIQUE)
CREATE INDEX idx_client_api_keys_name ON client_api_keys (name);

-- Optional: Add index for active keys if frequently queried
-- CREATE INDEX idx_api_keys_is_active ON api_keys (is_active);

COMMENT ON TABLE client_api_keys IS 'Stores API keys issued to clients';
COMMENT ON COLUMN client_api_keys.id IS 'Primary key, auto-incrementing';
COMMENT ON COLUMN client_api_keys.key_value IS 'The actual API key string, unique';
COMMENT ON COLUMN client_api_keys.name IS 'A user-friendly name for the key';
COMMENT ON COLUMN client_api_keys.is_active IS 'Flag indicating if the key is currently active';
COMMENT ON COLUMN client_api_keys.created_at IS 'Timestamp when the key was created (UTC)';
COMMENT ON COLUMN client_api_keys.metadata_ IS 'Optional JSON blob for storing arbitrary metadata';
