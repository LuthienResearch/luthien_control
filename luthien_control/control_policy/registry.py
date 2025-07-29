# Policy registry mapping policy names to classes.

from typing import Dict, Type

from .add_api_key_header import AddApiKeyHeaderPolicy
from .add_api_key_header_from_env import AddApiKeyHeaderFromEnvPolicy
from .backend_call_policy import BackendCallPolicy
from .branching_policy import BranchingPolicy
from .client_api_key_auth import ClientApiKeyAuthPolicy
from .control_policy import ControlPolicy
from .leaked_api_key_detection import LeakedApiKeyDetectionPolicy
from .model_name_replacement import ModelNameReplacementPolicy
from .noop_policy import NoopPolicy
from .send_backend_request import SendBackendRequestPolicy
from .serial_policy import SerialPolicy
from .set_backend_policy import SetBackendPolicy
from .transaction_context_logging_policy import TransactionContextLoggingPolicy

# Registry mapping policy names (as used in serialization/config) to their classes
POLICY_NAME_TO_CLASS: Dict[str, Type["ControlPolicy"]] = {
    "AddApiKeyHeader": AddApiKeyHeaderPolicy,
    "BackendCallPolicy": BackendCallPolicy,
    "BranchingPolicy": BranchingPolicy,
    "ClientApiKeyAuth": ClientApiKeyAuthPolicy,
    "SendBackendRequest": SendBackendRequestPolicy,
    "SerialPolicy": SerialPolicy,
    "AddApiKeyHeaderFromEnv": AddApiKeyHeaderFromEnvPolicy,
    "LeakedApiKeyDetection": LeakedApiKeyDetectionPolicy,
    "ModelNameReplacement": ModelNameReplacementPolicy,
    "SetBackendPolicy": SetBackendPolicy,
    "NoopPolicy": NoopPolicy,
    "TransactionContextLoggingPolicy": TransactionContextLoggingPolicy,
}

POLICY_CLASS_TO_NAME: Dict[Type["ControlPolicy"], str] = {v: k for k, v in POLICY_NAME_TO_CLASS.items()}

# Legacy compatibility
POLICY_NAME_TO_CLASS["CompoundPolicy"] = SerialPolicy
