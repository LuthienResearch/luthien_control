import importlib
import inspect
import logging
from typing import List, Sequence, Type

import httpx

from luthien_control.config.settings import Settings
from luthien_control.control_policy.interface import ControlPolicy
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
    policy_path = settings.get_policy_module()
    logger.info(f"Attempting to load policy from: {policy_path}")

    try:
        module_path, class_name = policy_path.rsplit(".", 1)
    except ValueError:
        raise PolicyLoadError(f"Invalid policy path format: '{policy_path}'. Expected format: 'module.path.ClassName'")

    try:
        module = importlib.import_module(module_path)
        logger.debug(f"Successfully imported module: {module_path}")
    except ImportError as e:
        logger.error(f"Failed to import policy module '{module_path}': {e}", exc_info=True)
        raise PolicyLoadError(f"Could not import policy module: {module_path}") from e

    policy_class: Type[Policy] | None = getattr(module, class_name, None)

    if policy_class is None:
        logger.error(f"Policy class '{class_name}' not found in module '{module_path}'")
        raise PolicyLoadError(f"Policy class '{class_name}' not found in module '{module_path}'")

    # Ensure it's a class type AND a subclass of Policy
    if not isinstance(policy_class, type) or not issubclass(policy_class, Policy):
        logger.error(f"Class '{policy_path}' is not a valid subclass of {Policy.__name__}")
        raise PolicyLoadError(f"Class '{policy_path}' must be a valid subclass of {Policy.__name__}")

    try:
        policy_instance = policy_class()
        logger.info(f"Successfully loaded and instantiated policy: {policy_instance}")
        return policy_instance
    except Exception as e:
        logger.error(f"Failed to instantiate policy class '{policy_path}': {e}", exc_info=True)
        raise PolicyLoadError(f"Could not instantiate policy class '{policy_path}'") from e


def load_control_policies(settings: Settings, http_client: httpx.AsyncClient) -> Sequence[ControlPolicy]:
    """
    Loads and instantiates a sequence of ControlPolicy classes specified in settings.

    Reads the comma-separated list from settings.CONTROL_POLICIES.
    Injects 'settings' and 'http_client' dependencies into policy constructors
    if their __init__ method accepts them by those exact names.

    Args:
        settings: The application settings object.
        http_client: The shared httpx AsyncClient.

    Returns:
        A sequence of instantiated ControlPolicy objects.

    Raises:
        PolicyLoadError: If any policy module/class cannot be found, is invalid,
                         or fails instantiation.
    """
    # Call the getter method
    policy_paths_str = settings.get_control_policies_list()
    if not policy_paths_str:
        logger.warning("CONTROL_POLICIES setting is empty or not set. No control policies loaded.")
        return []

    policy_paths = [path.strip() for path in policy_paths_str.split(",") if path.strip()]
    logger.info(f"Attempting to load {len(policy_paths)} control policies: {policy_paths}")

    loaded_policies: List[ControlPolicy] = []

    for policy_path in policy_paths:
        logger.debug(f"Loading control policy: {policy_path}")
        try:
            module_path, class_name = policy_path.rsplit(".", 1)
        except ValueError:
            raise PolicyLoadError(
                f"Invalid policy path format: '{policy_path}'. Expected format: 'module.path.ClassName'"
            )

        try:
            module = importlib.import_module(module_path)
            logger.debug(f"Successfully imported module: {module_path}")
        except ImportError as e:
            logger.error(f"Failed to import control policy module '{module_path}': {e}", exc_info=True)
            raise PolicyLoadError(f"Could not import control policy module: {module_path}") from e

        policy_class: Type[ControlPolicy] | None = getattr(module, class_name, None)

        if policy_class is None:
            logger.error(f"Control policy class '{class_name}' not found in module '{module_path}'")
            raise PolicyLoadError(f"Control policy class '{class_name}' not found in module '{module_path}'")

        if not isinstance(policy_class, type) or not issubclass(policy_class, ControlPolicy):
            logger.error(f"Class '{policy_path}' is not a valid subclass of {ControlPolicy.__name__}")
            raise PolicyLoadError(f"Class '{policy_path}' must be a valid subclass of {ControlPolicy.__name__}")

        # --- Dependency Injection for Policy Constructor ---
        constructor_params = inspect.signature(policy_class.__init__).parameters
        init_kwargs = {}
        if "settings" in constructor_params:
            init_kwargs["settings"] = settings
            logger.debug(f"Injecting 'settings' into {class_name}")
        if "http_client" in constructor_params:
            init_kwargs["http_client"] = http_client
            logger.debug(f"Injecting 'http_client' into {class_name}")
        # --- End Dependency Injection ---

        try:
            policy_instance = policy_class(**init_kwargs)
            logger.info(f"Successfully loaded and instantiated control policy: {policy_path} as {policy_instance}")
            loaded_policies.append(policy_instance)
        except Exception as e:
            logger.error(
                f"Failed to instantiate control policy class '{policy_path}' with args {init_kwargs.keys()}: {e}",
                exc_info=True,
            )
            raise PolicyLoadError(f"Could not instantiate control policy class '{policy_path}'") from e

    return loaded_policies
