"""Loads control policies from serialized data."""

import logging
from typing import TYPE_CHECKING, Type

# Import the load error exception
from .exceptions import PolicyLoadError

# Import serialization types
from .serialization import SerializedPolicy

if TYPE_CHECKING:
    # Use forward reference for ControlPolicy to avoid circular import at runtime
    from .control_policy import ControlPolicy


async def load_policy(serialized_policy: SerializedPolicy) -> "ControlPolicy":
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

    policy_type = serialized_policy["type"]
    policy_config = serialized_policy["config"]

    if not isinstance(policy_type, str):
        raise PolicyLoadError(f"Policy 'type' must be a string, got: {type(policy_type)}")
    if not isinstance(policy_config, dict):
        raise PolicyLoadError(f"Policy 'config' must be a dictionary, got: {type(policy_config)}")

    try:
        policy_class = POLICY_NAME_TO_CLASS.get(policy_type)
    except KeyError:
        raise PolicyLoadError(
            f"Unknown policy type: '{policy_type}'. Available policies: {list(POLICY_NAME_TO_CLASS.keys())}"
        )

    try:
        instance = await policy_class.from_serialized(policy_config)
        instance_name = policy_config.get("name", None)
        if instance_name:
            instance.name = instance_name
        logger.info(f"Successfully loaded policy: {getattr(instance, 'name', policy_type)}")
        return instance
    except Exception as e:
        logger.error(f"Error instantiating policy '{policy_type}': {e}", exc_info=True)
        raise PolicyLoadError(f"Error instantiating policy '{policy_type}': {e}") from e
