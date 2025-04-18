"""add_root_policy_data

Revision ID: ab5c8efa5a4b
Revises: 6e27f83a84ac
Create Date: 2025-04-18 15:29:12.005424

"""
from typing import Sequence, Union
from datetime import datetime, timezone
import json

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'ab5c8efa5a4b'
down_revision: Union[str, None] = '6e27f83a84ac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Define the root policy configuration
    root_policy_class_path = "luthien_control.control_policy.compound_policy.CompoundPolicy"
    
    # Root policy configuration as a Python dictionary
    root_policy_config = {
        "type": "luthien_control.control_policy.compound_policy.CompoundPolicy",
        "config": {
            "policies": [
                {
                    "type": "luthien_control.control_policy.client_api_key_auth_policy.ClientApiKeyAuthPolicy",
                    "config": {
                        "allow_no_authentication_paths": [
                            "/docs",
                            "/redoc",
                            "/openapi.json",
                            "/health"
                        ]
                    }
                },
                {
                    "type": "luthien_control.control_policy.add_api_key_header.AddApiKeyHeaderPolicy",
                    "config": {}
                },
                {
                    "type": "luthien_control.control_policy.send_backend_request_policy.SendBackendRequestPolicy",
                    "config": {
                        "rewrite_url": True,
                        "backend_url": "${BACKEND_URL}"
                    }
                }
            ]
        }
    }
    
    # Convert to JSON string for storage
    root_policy_json = json.dumps(root_policy_config)
    
    # Insert the policy only if it doesn't already exist
    op.execute(
        f"""
        INSERT INTO policies (name, policy_class_path, config, is_active, description, created_at, updated_at)
        VALUES 
        ('root', 
         '{root_policy_class_path}', 
         '{root_policy_json}'::json, 
         true, 
         'Root policy configuration defining the core request flow', 
         '{datetime.now(timezone.utc).isoformat()}', 
         '{datetime.now(timezone.utc).isoformat()}')
        ON CONFLICT (name) DO NOTHING
        """
    )


def downgrade() -> None:
    # Define the root policy configuration (same as in upgrade)
    root_policy_config = {
        "type": "luthien_control.control_policy.compound_policy.CompoundPolicy",
        "config": {
            "policies": [
                {
                    "type": "luthien_control.control_policy.client_api_key_auth_policy.ClientApiKeyAuthPolicy",
                    "config": {
                        "allow_no_authentication_paths": [
                            "/docs",
                            "/redoc",
                            "/openapi.json",
                            "/health"
                        ]
                    }
                },
                {
                    "type": "luthien_control.control_policy.add_api_key_header.AddApiKeyHeaderPolicy",
                    "config": {}
                },
                {
                    "type": "luthien_control.control_policy.send_backend_request_policy.SendBackendRequestPolicy",
                    "config": {
                        "rewrite_url": True,
                        "backend_url": "${BACKEND_URL}"
                    }
                }
            ]
        }
    }
    
    # Convert to JSON string for comparison
    root_policy_json = json.dumps(root_policy_config)
    
    # Delete the policy only if it matches our expected configuration
    op.execute(
        f"""
        DELETE FROM policies 
        WHERE name = 'root' 
        AND config::text = '{root_policy_json}'::text
        """
    )