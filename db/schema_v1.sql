-- Enable UUID generation if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Table for the overall interaction lifecycle
CREATE TABLE interactions (
    interaction_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    start_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    origin TEXT NOT NULL,
    end_timestamp TIMESTAMPTZ,
    final_status_code INTEGER,
    notes JSONB
);
CREATE INDEX idx_interactions_start_timestamp ON interactions (start_timestamp);
CREATE INDEX idx_interactions_origin ON interactions (origin);


-- Table for policy definitions
CREATE TABLE policies (
    policy_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR NOT NULL UNIQUE,
    definition JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_policies_name ON policies (name);


-- Base table for all interaction events
CREATE TABLE interaction_events (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    interaction_id UUID NOT NULL REFERENCES interactions(interaction_id) ON DELETE CASCADE,
    parent_event_id UUID REFERENCES interaction_events(event_id), -- Causal link
    sequence_number BIGINT NOT NULL, -- Monotonic sequence within interaction
    event_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_type VARCHAR NOT NULL CHECK (event_type IN ('http_request', 'http_response', 'policy_evaluation')),
    CONSTRAINT uq_interaction_sequence UNIQUE (interaction_id, sequence_number)
);

-- Note: Underlying index for uq_interaction_sequence supports interaction_id + sequence lookups
CREATE INDEX idx_interaction_events_event_timestamp ON interaction_events (event_timestamp);
CREATE INDEX idx_interaction_events_parent_event_id ON interaction_events (parent_event_id);


-- Table for HTTP request specific data
CREATE TABLE http_request_events (
    event_id UUID PRIMARY KEY REFERENCES interaction_events(event_id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    destination TEXT NOT NULL,
    method VARCHAR NOT NULL,
    url TEXT NOT NULL,
    headers JSONB,
    body JSONB
);
-- Optional GIN indexes on headers/body:
-- CREATE INDEX idx_http_request_events_headers_gin ON http_request_events USING GIN (headers);
-- CREATE INDEX idx_http_request_events_body_gin ON http_request_events USING GIN (body);


-- Table for HTTP response specific data
CREATE TABLE http_response_events (
    event_id UUID PRIMARY KEY REFERENCES interaction_events(event_id) ON DELETE CASCADE,
    request_event_id UUID NOT NULL REFERENCES interaction_events(event_id), -- Specific request this response is for
    source TEXT NOT NULL,
    destination TEXT NOT NULL,
    status_code INTEGER NOT NULL,
    headers JSONB,
    body JSONB
);
CREATE INDEX idx_http_response_events_request_event_id ON http_response_events (request_event_id);
-- Optional GIN indexes on headers/body:
-- CREATE INDEX idx_http_response_events_headers_gin ON http_response_events USING GIN (headers);
-- CREATE INDEX idx_http_response_events_body_gin ON http_response_events USING GIN (body);


-- Table for policy evaluation specific data
CREATE TABLE policy_evaluation_events (
    event_id UUID PRIMARY KEY REFERENCES interaction_events(event_id) ON DELETE CASCADE,
    policy_id UUID NOT NULL REFERENCES policies(policy_id),
    evaluation_end_timestamp TIMESTAMPTZ,
    status VARCHAR NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'completed', 'failed')),
    decision VARCHAR,
    details JSONB
);
CREATE INDEX idx_policy_evaluation_events_policy_id ON policy_evaluation_events (policy_id);
