-- Enable UUID generation if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Table for policy definitions
CREATE TABLE policies (
    policy_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR NOT NULL UNIQUE,
    definition JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_policies_name ON policies (name);


-- Logging table for requests and responses
-- Kept IF NOT EXISTS for idempotency, although migration runner should handle it.
CREATE TABLE IF NOT EXISTS request_log (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    client_ip TEXT,
    request_method TEXT NOT NULL,
    request_url TEXT NOT NULL,
    request_headers JSONB,
    request_body TEXT,
    response_status_code INTEGER,
    response_headers JSONB,
    response_body TEXT,
    processing_time_ms INTEGER
);

-- Optional: Index frequently queried columns
-- Kept IF NOT EXISTS for idempotency.
CREATE INDEX IF NOT EXISTS idx_request_log_timestamp ON request_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_request_log_request_url ON request_log(request_url);
