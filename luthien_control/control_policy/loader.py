# Loads control policies from serialized data.

import json
import logging

from luthien_control.control_policy.control_policy import ControlPolicy

# Import the load error exception
from .exceptions import PolicyLoadError

# Import serialization types
from .serialization import SerializedPolicy


def load_policy(serialized_policy: SerializedPolicy) -> "ControlPolicy":
    """
    Loads a ControlPolicy instance from a dictionary containing its name and config,
    injecting required dependencies.

    Args:
        serialized_policy: A SerializedPolicy object.

    Returns:
        An instantiated ControlPolicy object.

    Raises:
        PolicyLoadError: If the policy name is unknown, data is missing/malformed,
                         or a required dependency is not provided.
        Exception: Potentially from the policy's from_serialized method if config is invalid.
    """
    # Import the policy registry here to avoid circular import
    from .registry import POLICY_NAME_TO_CLASS  # noqa: F401

    logger = logging.getLogger(__name__)

    policy_type = serialized_policy.type
    policy_config = serialized_policy.config

    if not isinstance(policy_type, str):
        raise PolicyLoadError(f"Policy 'type' must be a string, got: {type(policy_type)}")
    if not isinstance(policy_config, dict):
        raise PolicyLoadError(f"Policy 'config' must be a dictionary, got: {type(policy_config)}")

    policy_class = POLICY_NAME_TO_CLASS.get(policy_type)

    # Explicitly check if the policy type was found in the registry
    if policy_class is None:
        raise PolicyLoadError(
            f"Unknown policy type: '{policy_type}'. Available policies: {list(POLICY_NAME_TO_CLASS.keys())}"
        )

    try:
        instance = policy_class.from_serialized(policy_config)
        logger.info(f"Successfully loaded policy: {getattr(instance, 'name', policy_type)}")
        return instance
    except Exception as e:
        logger.error(f"Error instantiating policy '{policy_type}': {e}", exc_info=True)
        raise PolicyLoadError(f"Error instantiating policy '{policy_type}': {e}") from e


def load_policy_from_file(filepath: str) -> "ControlPolicy":
    """Load a policy configuration from a file and instantiate it using the control_policy loader."""
    with open(filepath, "r") as f:
        raw_policy_data = json.load(f)

    if not isinstance(raw_policy_data, dict):
        raise PolicyLoadError(f"Policy data loaded from {filepath} must be a dictionary, got {type(raw_policy_data)}")

    policy_type = raw_policy_data.get("type")
    policy_config = raw_policy_data.get("config")

    if not isinstance(policy_type, str):
        raise PolicyLoadError(
            f"Policy file {filepath} must contain a 'type' field as a string. Got: {type(policy_type)}"
        )
    if not isinstance(policy_config, dict):
        raise PolicyLoadError(
            f"Policy file {filepath} must contain a 'config' field as a dictionary. Got: {type(policy_config)}"
        )

    serialized_policy_obj = SerializedPolicy(type=policy_type, config=policy_config)
    return load_policy(serialized_policy_obj)
