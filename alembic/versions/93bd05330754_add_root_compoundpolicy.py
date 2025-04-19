"""Add root CompoundPolicy

Revision ID: 93bd05330754
Revises: 6e27f83a84ac
Create Date: 2025-04-18 17:55:16.262055

"""
import json
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '93bd05330754'
down_revision: Union[str, None] = '6e27f83a84ac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# --- Configuration for the root policy ---
ROOT_POLICY_NAME = 'root'
ROOT_POLICY_CLASS_PATH = 'luthien_control.control_policy.compound_policy.CompoundPolicy'
ROOT_POLICY_CONFIG = {
  "policies": [
    {
      "name": "ClientAPIKeyCheck",
      "policy_class_path": "luthien_control.control_policy.client_api_key_auth.ClientApiKeyAuthPolicy"
    },
    {
      "name": "AddBackendKey",
      "policy_class_path": "luthien_control.control_policy.add_api_key_header.AddApiKeyHeaderPolicy"
    },
    {
      "name": "ForwardRequest",
      "policy_class_path": "luthien_control.control_policy.send_backend_request.SendBackendRequestPolicy"
    }
  ]
}
ROOT_POLICY_DESCRIPTION = "Root policy configuration defining the core request flow"
# --- End Configuration ---


def upgrade() -> None:
    """Insert the root policy configuration if it doesn't exist."""
    config_json_str = json.dumps(ROOT_POLICY_CONFIG).replace("'", "''")
    now_iso = datetime.now(timezone.utc).isoformat()

    # Use ON CONFLICT to avoid errors if 'root' policy already exists
    op.execute(
        f"""
        INSERT INTO policies (name, policy_class_path, config, is_active, description, created_at, updated_at)
        VALUES
        ('{ROOT_POLICY_NAME}',
         '{ROOT_POLICY_CLASS_PATH}',
         '{config_json_str}'::jsonb,
         true,
         '{ROOT_POLICY_DESCRIPTION.replace("'", "''")}',
         '{now_iso}',
         '{now_iso}')
        ON CONFLICT (name) DO NOTHING;
        """
    )


def downgrade() -> None:
    """Remove the root policy configuration only if it matches the one we inserted."""

    # Convert config dict to a JSON string suitable for SQL comparison
    config_json_str = json.dumps(ROOT_POLICY_CONFIG).replace("'", "''")

    # Only delete if name, class path, and config match exactly
    op.execute(
        f"""
        DELETE FROM policies
        WHERE name = '{ROOT_POLICY_NAME}'
          AND policy_class_path = '{ROOT_POLICY_CLASS_PATH}'
          AND config = '{config_json_str}'::jsonb;
        """
    )
