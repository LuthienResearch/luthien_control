"""Policy registry mapping policy names to classes."""

from typing import TYPE_CHECKING, Dict, Type

# Import concrete policy types to populate the registry
from .add_api_key_header import AddApiKeyHeaderPolicy
from .add_api_key_header_from_env import AddApiKeyHeaderFromEnvPolicy
from .client_api_key_auth import ClientApiKeyAuthPolicy
from .compound_policy import CompoundPolicy
from .send_backend_request import SendBackendRequestPolicy

if TYPE_CHECKING:
    # Use forward reference for ControlPolicy to avoid circular import at runtime
    from .control_policy import ControlPolicy


# Registry mapping policy names (as used in serialization/config) to their classes
POLICY_NAME_TO_CLASS: Dict[str, Type["ControlPolicy"]] = {
    "AddApiKeyHeader": AddApiKeyHeaderPolicy,
    "ClientApiKeyAuth": ClientApiKeyAuthPolicy,
    "CompoundPolicy": CompoundPolicy,
    "SendBackendRequest": SendBackendRequestPolicy,
    "AddApiKeyHeaderFromEnv": AddApiKeyHeaderFromEnvPolicy,
    # Add other policies here as they are created
}

POLICY_CLASS_TO_NAME: Dict[Type["ControlPolicy"], str] = {v: k for k, v in POLICY_NAME_TO_CLASS.items()}
