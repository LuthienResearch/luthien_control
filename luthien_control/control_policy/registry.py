"""Policy registry mapping policy names to classes."""

from typing import TYPE_CHECKING, Dict, Type

# Import concrete policy types to populate the registry
from .add_api_key_header import AddApiKeyHeaderPolicy
from .client_api_key_auth import ClientApiKeyAuthPolicy
from .compound_policy import CompoundPolicy
from .send_backend_request import SendBackendRequestPolicy

if TYPE_CHECKING:
    # Use forward reference for ControlPolicy to avoid circular import at runtime
    from .control_policy import ControlPolicy


# Registry mapping policy names (as used in serialization/config) to their classes
POLICY_NAME_TO_CLASS: Dict[str, Type["ControlPolicy"]] = {
    "add_api_key_header": AddApiKeyHeaderPolicy,
    "client_api_key_auth": ClientApiKeyAuthPolicy,
    "compound_policy": CompoundPolicy,
    "send_backend_request": SendBackendRequestPolicy,
    # Add other policies here as they are created
}

# Optional: A reverse mapping might be useful elsewhere, but keep it here
# with the primary registry definition.
POLICY_CLASS_TO_NAME: Dict[Type["ControlPolicy"], str] = {v: k for k, v in POLICY_NAME_TO_CLASS.items()}
