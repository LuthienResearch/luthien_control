-- Migration 004: Insert or Update 'root' policy with Standard Flow configuration

BEGIN;

-- Insert or Update the 'root' policy record
INSERT INTO policies (name, policy_class_path, config, is_active, description, created_at, updated_at)
VALUES (
    'root', -- name
    'luthien_control.control_policy.compound_policy.CompoundPolicy', -- policy_class_path
    '{
      "__policy_type__": "CompoundPolicy",
      "name": "root",
      "policy_class_path": "luthien_control.control_policy.compound_policy.CompoundPolicy",
      "member_policy_configs": [
        {
          "__policy_type__": "ClientApiKeyAuthPolicy",
          "name": "ClientAuth",
          "policy_class_path": "luthien_control.control_policy.client_api_key_auth.ClientApiKeyAuthPolicy"
        },
        {
          "__policy_type__": "AddApiKeyHeaderPolicy",
          "name": "AddBackendKey",
          "policy_class_path": "luthien_control.control_policy.add_api_key_header.AddApiKeyHeaderPolicy"
        },
        {
          "__policy_type__": "SendBackendRequestPolicy",
          "name": "ForwardRequest",
          "policy_class_path": "luthien_control.control_policy.send_backend_request.SendBackendRequestPolicy"
        }
      ]
    }'::jsonb, -- config (Cast the string literal to JSONB)
    TRUE, -- is_active
    'Standard flow: Client Auth -> Add Backend Key -> Forward Request.', -- description
    NOW(), -- created_at
    NOW() -- updated_at
)
ON CONFLICT (name) DO UPDATE SET
    policy_class_path = EXCLUDED.policy_class_path,
    config = EXCLUDED.config,
    is_active = EXCLUDED.is_active,
    description = EXCLUDED.description,
    updated_at = NOW(); -- Update timestamp on conflict

-- Update the comment on the table
COMMENT ON TABLE policies IS 'Schema updated by 003. Root policy inserted or updated by 004 with StandardFlow config.';

COMMIT; 