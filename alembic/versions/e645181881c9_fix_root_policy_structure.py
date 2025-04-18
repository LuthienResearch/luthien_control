"""fix_root_policy_structure

Revision ID: e645181881c9
Revises: ab5c8efa5a4b
Create Date: 2025-04-18 16:20:07.242250

"""
from typing import Sequence, Union
from datetime import datetime, timezone
import json

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'e645181881c9'
down_revision: Union[str, None] = 'ab5c8efa5a4b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Define the root policy configuration with the proper structure for CompoundPolicy
    root_policy_class_path = "luthien_control.control_policy.compound_policy.CompoundPolicy"
    
    # Root policy configuration as a Python dictionary with the updated format
    root_policy_config = {
        "__policy_type__": "CompoundPolicy",
        "name": "root",
        "member_policy_configs": [
            {
                "__policy_type__": "ClientApiKeyAuthPolicy",
                "name": "ClientAuth",
                "policy_class_path": "luthien_control.control_policy.client_api_key_auth.ClientApiKeyAuthPolicy",
                "allow_no_authentication_paths": [
                    "/docs",
                    "/redoc",
                    "/openapi.json",
                    "/health"
                ]
            },
            {
                "__policy_type__": "AddApiKeyHeaderPolicy",
                "name": "AddBackendKey",
                "policy_class_path": "luthien_control.control_policy.add_api_key_header.AddApiKeyHeaderPolicy"
            },
            {
                "__policy_type__": "SendBackendRequestPolicy",
                "name": "ForwardRequest",
                "policy_class_path": "luthien_control.control_policy.send_backend_request.SendBackendRequestPolicy",
                "rewrite_url": True,
                "backend_url": "${BACKEND_URL}"
            }
        ],
        "policy_class_path": root_policy_class_path
    }
    
    # Convert to JSON string for storage
    root_policy_json = json.dumps(root_policy_config)
    
    # Update the existing root policy with the new structure
    op.execute(
        f"""
        UPDATE policies
        SET 
            config = '{root_policy_json}'::json,
            updated_at = '{datetime.now(timezone.utc).isoformat()}'
        WHERE name = 'root'
        """
    )


def downgrade() -> None:
    # Define the old root policy configuration to revert to if needed
    root_policy_config = {
        "type": "luthien_control.control_policy.compound_policy.CompoundPolicy",
        "config": {
            "policies": [
                {
                    "type": "luthien_control.control_policy.client_api_key_auth.ClientApiKeyAuthPolicy",
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
                    "type": "luthien_control.control_policy.send_backend_request.SendBackendRequestPolicy",
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
    
    # Revert the root policy to its previous structure
    op.execute(
        f"""
        UPDATE policies
        SET 
            config = '{root_policy_json}'::json,
            updated_at = '{datetime.now(timezone.utc).isoformat()}'
        WHERE name = 'root'
        """
    )