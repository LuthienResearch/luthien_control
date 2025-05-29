# Policy registry mapping policy names to classes.

from typing import TYPE_CHECKING, Dict, Type

# Import concrete policy types to populate the registry
from .add_api_key_header import AddApiKeyHeaderPolicy
from .add_api_key_header_from_env import AddApiKeyHeaderFromEnvPolicy
from .branching_policy import BranchingPolicy
from .client_api_key_auth import ClientApiKeyAuthPolicy
from .leaked_api_key_detection import LeakedApiKeyDetectionPolicy
from .model_name_replacement import ModelNameReplacementPolicy
from .noop_policy import NoopPolicy
from .send_backend_request import SendBackendRequestPolicy
from .serial_policy import SerialPolicy
from .tx_logging_policy import TxLoggingPolicy

if TYPE_CHECKING:
    # Use forward reference for ControlPolicy to avoid circular import at runtime
    from .control_policy import ControlPolicy


# Registry mapping policy names (as used in serialization/config) to their classes
POLICY_NAME_TO_CLASS: Dict[str, Type["ControlPolicy"]] = {
    "AddApiKeyHeader": AddApiKeyHeaderPolicy,
    "ClientApiKeyAuth": ClientApiKeyAuthPolicy,
    "SerialPolicy": SerialPolicy,
    "SendBackendRequest": SendBackendRequestPolicy,
    "AddApiKeyHeaderFromEnv": AddApiKeyHeaderFromEnvPolicy,
    "LeakedApiKeyDetection": LeakedApiKeyDetectionPolicy,
    "BranchingPolicy": BranchingPolicy,
    "ModelNameReplacement": ModelNameReplacementPolicy,
    "TxLoggingPolicy": TxLoggingPolicy,
    "NoopPolicy": NoopPolicy,
    # Add other policies here as they are created
}

POLICY_CLASS_TO_NAME: Dict[Type["ControlPolicy"], str] = {v: k for k, v in POLICY_NAME_TO_CLASS.items()}

POLICY_NAME_TO_CLASS["CompoundPolicy"] = SerialPolicy  # legacy compatibility
