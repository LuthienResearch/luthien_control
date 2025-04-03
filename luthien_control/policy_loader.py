import importlib
import logging
from typing import Type

from luthien_control.config.settings import Settings
from luthien_control.policies.base import Policy

logger = logging.getLogger(__name__)


class PolicyLoadError(Exception):
    """Custom exception for errors during policy loading."""
    pass


def load_policy(settings: Settings) -> Policy:
    """
    Loads and instantiates the policy class specified in the settings.

    Args:
        settings: The application settings object.

    Returns:
        An instance of the configured policy class.

    Raises:
        PolicyLoadError: If the policy module or class cannot be found,
                         or if the class is not a valid Policy subclass.
    """
    policy_path = settings.POLICY_MODULE
    logger.info(f"Attempting to load policy from: {policy_path}")

    try:
        module_path, class_name = policy_path.rsplit('.', 1)
    except ValueError:
        raise PolicyLoadError(
            f"Invalid policy path format: '{policy_path}'. "
            "Expected format: 'module.path.ClassName'"
        )

    try:
        module = importlib.import_module(module_path)
        logger.debug(f"Successfully imported module: {module_path}")
    except ImportError as e:
        logger.error(f"Failed to import policy module '{module_path}': {e}", exc_info=True)
        raise PolicyLoadError(f"Could not import policy module: {module_path}") from e

    policy_class: Type[Policy] | None = getattr(module, class_name, None)

    if policy_class is None:
        logger.error(f"Policy class '{class_name}' not found in module '{module_path}'")
        raise PolicyLoadError(
            f"Policy class '{class_name}' not found in module '{module_path}'"
        )

    # Ensure it's a class type AND a subclass of Policy
    if not isinstance(policy_class, type) or not issubclass(policy_class, Policy):
        logger.error(f"Class '{policy_path}' is not a valid subclass of {Policy.__name__}")
        raise PolicyLoadError(
            f"Class '{policy_path}' must be a valid subclass of {Policy.__name__}"
        )

    try:
        policy_instance = policy_class()
        logger.info(f"Successfully loaded and instantiated policy: {policy_instance}")
        return policy_instance
    except Exception as e:
        logger.error(f"Failed to instantiate policy class '{policy_path}': {e}", exc_info=True)
        raise PolicyLoadError(f"Could not instantiate policy class '{policy_path}'") from e
