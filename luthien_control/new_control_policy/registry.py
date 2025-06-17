# Policy registry mapping policy names to classes.

from typing import Dict, Type

# Import concrete policy types to populate the registry (only successfully migrated policies)
from .add_api_key_header import AddApiKeyHeaderPolicy
from .add_api_key_header_from_env import AddApiKeyHeaderFromEnvPolicy
from .branching_policy import BranchingPolicy
from .client_api_key_auth import ClientApiKeyAuthPolicy
from .control_policy import ControlPolicy
from .leaked_api_key_detection import LeakedApiKeyDetectionPolicy
from .model_name_replacement import ModelNameReplacementPolicy
from .noop_policy import NoopPolicy
from .send_backend_request import SendBackendRequestPolicy
from .serial_policy import SerialPolicy

# Registry mapping policy names (as used in serialization/config) to their classes
# Only includes policies that have been successfully migrated to the Transaction model
POLICY_NAME_TO_CLASS: Dict[str, Type["ControlPolicy"]] = {
    "AddApiKeyHeader": AddApiKeyHeaderPolicy,
    "BranchingPolicy": BranchingPolicy,
    "ClientApiKeyAuth": ClientApiKeyAuthPolicy,
    "SendBackendRequest": SendBackendRequestPolicy,
    "SerialPolicy": SerialPolicy,
    "AddApiKeyHeaderFromEnv": AddApiKeyHeaderFromEnvPolicy,
    "LeakedApiKeyDetection": LeakedApiKeyDetectionPolicy,
    "ModelNameReplacement": ModelNameReplacementPolicy,
    "NoopPolicy": NoopPolicy,
    # Policies that could not be migrated:
    # - "TxLoggingPolicy": TxLoggingPolicy (requires migrating all TxLoggingSpec classes)
}

POLICY_CLASS_TO_NAME: Dict[Type["ControlPolicy"], str] = {v: k for k, v in POLICY_NAME_TO_CLASS.items()}

# Legacy compatibility for successfully migrated policies
POLICY_NAME_TO_CLASS["CompoundPolicy"] = SerialPolicy
