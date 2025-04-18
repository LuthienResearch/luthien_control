import importlib
import inspect
import logging
from typing import Any, Callable, Coroutine, Dict, Optional, Type

import httpx

# Configuration and Policy Interfaces (adjust paths if necessary)
from luthien_control.config.settings import Settings
from luthien_control.control_policy.compound_policy import CompoundPolicy
from luthien_control.control_policy.interface import ControlPolicy
from luthien_control.db.sqlmodel_models import ClientApiKey

logger = logging.getLogger(__name__)

# Type alias for the API key lookup function, assuming it returns Optional[ClientApiKey]
ApiKeyLookupFunc = Callable[[str], Coroutine[Any, Any, Optional[ClientApiKey]]]


class PolicyLoadError(Exception):
    """Custom exception for errors during policy loading/instantiation."""

    pass


# --- Helper Function for Recursive Instantiation ---


async def _resolve_nested_config_values(
    value: Any,
    parent_policy_name: str,
    parent_key: str,
    settings: Settings,
    http_client: httpx.AsyncClient,
    api_key_lookup: ApiKeyLookupFunc,
) -> Any:
    """
    Recursively traverses config values (dicts, lists) and instantiates nested policies.

    Args:
        value: The config value to process (could be dict, list, or other type).
        parent_policy_name: Name of the policy whose config this value belongs to.
        parent_key: The key under which this value was found in the parent config.
        settings: Application settings.
        http_client: HTTP client.
        api_key_lookup: API key lookup function.

    Returns:
        The resolved value. If the input was a policy config dict, returns the
        instantiated policy. If it was a list containing policy configs, returns
        a list with policies instantiated. Otherwise, returns the original value.

    Raises:
        PolicyLoadError: If instantiation of a nested policy fails.
    """
    # Check if value is a dict representing a nested policy
    if isinstance(value, dict) and "policy_class_path" in value:
        nested_name = value.get("name", "<unknown_nested>")
        logger.debug(
            f"Found nested policy config '{nested_name}' under key '{parent_key}' "
            f"for '{parent_policy_name}'. Recursively instantiating..."
        )
        try:
            # Note: Recursive call back to instantiate_policy in the same module
            # Pass along necessary dependencies
            return await instantiate_policy(value, settings, http_client, api_key_lookup)
        except (PolicyLoadError, ImportError, AttributeError) as e:
            logger.error(
                f"Failed during recursive instantiation for nested policy '{nested_name}' "
                f"within '{parent_policy_name}': {e}"
            )
            # Re-raise to propagate the error upwards
            raise PolicyLoadError(
                f"Failed to instantiate nested policy '{nested_name}' within '{parent_policy_name}'."
            ) from e

    # Check if value is a list possibly containing nested policy dicts
    elif isinstance(value, list):
        resolved_list = []
        for index, item in enumerate(value):
            # Check if the item itself needs recursive resolution
            resolved_item = await _resolve_nested_config_values(
                item, parent_policy_name, f"{parent_key}[{index}]", settings, http_client, api_key_lookup
            )
            resolved_list.append(resolved_item)
        return resolved_list

    else:
        # Keep non-policy-config, non-list values as they are
        return value


# --- Instantiation Helper Functions ---


def _validate_config_keys(policy_config: Dict[str, Any]) -> None:
    """Validate that required keys are present in the policy configuration."""
    if "policy_class_path" not in policy_config:
        raise PolicyLoadError("Policy config dictionary is missing required key: 'policy_class_path'.")
    if "name" not in policy_config:
        raise PolicyLoadError("Policy config dictionary is missing required key: 'name'.")


def _import_and_validate_policy_class(policy_class_path: str, instance_name: str) -> Type[ControlPolicy]:
    """Import and validate the policy class."""
    logger.debug(f"Importing policy class '{policy_class_path}' for instance '{instance_name}'")
    try:
        module_path, class_name = policy_class_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        policy_class: Type[ControlPolicy] = getattr(module, class_name)
        logger.debug(f"Successfully imported class '{class_name}' from '{module_path}' for '{instance_name}'")
    except (ImportError, AttributeError, ValueError) as e:
        logger.error(f"Failed to import policy class '{policy_class_path}' for instance '{instance_name}': {e}")
        raise PolicyLoadError(
            f"Could not load policy class '{policy_class_path}' for instance '{instance_name}'. Check path."
        ) from e

    if not inspect.isclass(policy_class) or not issubclass(policy_class, ControlPolicy):
        raise PolicyLoadError(f"Class '{class_name}' from '{module_path}' does not inherit from ControlPolicy.")
    return policy_class


async def _resolve_all_nested_configs(
    policy_config: Dict[str, Any],
    instance_name: str,
    settings: Settings,
    http_client: httpx.AsyncClient,
    api_key_lookup: ApiKeyLookupFunc,
) -> Dict[str, Any]:
    """Resolve all nested policy configurations within the main config."""
    resolved_config: Dict[str, Any] = {}
    logger.debug(f"Processing config keys for '{instance_name}' to resolve nested policies...")
    try:
        for key, value in policy_config.items():
            # Skip meta-keys needed earlier but not for injection
            if key in ["policy_class_path", "name"]:
                continue

            # Use the helper to resolve the value recursively
            resolved_value = await _resolve_nested_config_values(
                value, instance_name, key, settings, http_client, api_key_lookup
            )
            resolved_config[key] = resolved_value

        logger.debug(f"Finished resolving nested configurations for '{instance_name}'.")
        return resolved_config
    except PolicyLoadError as e:
        # Error logged in helper, just re-raise
        raise e
    except Exception as e:  # Catch unexpected errors during resolution
        logger.exception(f"Unexpected error resolving nested config for '{instance_name}': {e}")
        raise PolicyLoadError(f"Unexpected error resolving nested config for '{instance_name}'.") from e


def _handle_compound_policy_args(
    policy_class: Type[ControlPolicy],
    instance_args: Dict[str, Any],
    resolved_config: Dict[str, Any],
    instance_name: str,
) -> None:
    """
    Specific handling for mapping configuration to CompoundPolicy constructor arguments.
    Modifies instance_args in place.
    """
    if not issubclass(policy_class, CompoundPolicy):
        return  # Only apply to CompoundPolicy subclasses

    if "member_policy_configs" in resolved_config:
        if "policies" not in instance_args:  # Check if 'policies' wasn't already populated directly
            member_policies = resolved_config.get("member_policy_configs")
            if isinstance(member_policies, list):
                # Map the resolved list of policies from config to the 'policies' constructor argument
                instance_args["policies"] = member_policies
                logger.debug(f"Mapped resolved 'member_policy_configs' list to 'policies' arg for {instance_name}")
            elif member_policies is not None:  # Error if key exists but isn't a list
                raise PolicyLoadError(
                    f"Configuration error for {instance_name}: 'member_policy_configs' resolved to type "
                    f"{type(member_policies).__name__}, but expected a list for CompoundPolicy."
                )
            # If member_policies is None (key present but value is null), we don't inject anything and don't error yet.
            # Validation later will catch if 'policies' is still missing and required.
        else:
            # 'policies' argument was already provided (e.g., directly in config or via dependency injection)
            logger.warning(
                f"'policies' argument for {instance_name} was already populated, "
                f"skipping automatic mapping from 'member_policy_configs'. Ensure this is intended."
            )


def _prepare_constructor_args(
    policy_class: Type[ControlPolicy],
    resolved_config: Dict[str, Any],
    settings: Settings,
    http_client: httpx.AsyncClient,
    api_key_lookup: ApiKeyLookupFunc,
    instance_name: str,
) -> Dict[str, Any]:
    """Prepare the arguments dictionary for the policy constructor."""
    instance_args: Dict[str, Any] = {}
    sig = inspect.signature(policy_class.__init__)
    init_params = sig.parameters
    class_name = policy_class.__name__

    # Inject common dependencies
    if "settings" in init_params:
        instance_args["settings"] = settings
    if "http_client" in init_params:
        instance_args["http_client"] = http_client
    if "api_key_lookup" in init_params:
        instance_args["api_key_lookup"] = api_key_lookup

    # Inject resolved configuration parameters
    for key, value in resolved_config.items():
        # Skip special keys used for mapping, handled later if needed
        if key == "member_policy_configs" and issubclass(policy_class, CompoundPolicy):
            continue  # This key is handled by _handle_compound_policy_args

        if key in init_params and key not in instance_args:
            instance_args[key] = value
            logger.debug(f"Injecting resolved config key '{key}' into '{instance_name}' ({class_name})")
        elif key not in init_params:
            # Only warn if the key was present in config but not used by __init__
            logger.warning(
                f"Config key '{key}' for policy '{instance_name}' was processed but does not match any parameter "
                f"in {class_name}.__init__. Ignoring."
            )

    # Apply specific argument handling for known composite types like CompoundPolicy
    _handle_compound_policy_args(policy_class, instance_args, resolved_config, instance_name)

    return instance_args


def _validate_constructor_args(
    policy_class: Type[ControlPolicy],
    instance_args: Dict[str, Any],
    resolved_config: Dict[str, Any],
    instance_name: str,
) -> None:
    """Validate that all required constructor arguments are present."""
    sig = inspect.signature(policy_class.__init__)
    init_params = sig.parameters
    class_name = policy_class.__name__

    missing_required = []
    for param_name, param in init_params.items():
        if param.name == "self":
            continue
        # Check if the param is not in instance_args AND it doesn't have a default value
        if param_name not in instance_args and param.default is inspect.Parameter.empty:
            # Special case: CompoundPolicy 'policies' can be satisfied by 'member_policy_configs'
            is_compound_policy_case = (
                issubclass(policy_class, CompoundPolicy)
                and param_name == "policies"
                and "member_policy_configs" in resolved_config
            )
            if not is_compound_policy_case:
                missing_required.append(param_name)

    if missing_required:
        raise PolicyLoadError(
            f"Cannot instantiate policy '{instance_name}' ({class_name}). "
            f"Missing required arguments: {missing_required}. "
            f"Provided arguments: {list(instance_args.keys())}. Resolved config keys: {list(resolved_config.keys())}. "
            f"Required by __init__: {list(p for p in init_params if p != 'self')}"
        )


def _create_policy_instance(
    policy_class: Type[ControlPolicy], instance_args: Dict[str, Any], instance_name: str
) -> ControlPolicy:
    """Instantiate the policy class with the prepared arguments."""
    class_name = policy_class.__name__
    try:
        instance = policy_class(**instance_args)
        logger.info(f"Successfully instantiated policy instance '{instance_name}' of type '{class_name}'")
        return instance
    except TypeError as e:
        provided_arg_types = {k: type(v).__name__ for k, v in instance_args.items()}
        sig = inspect.signature(policy_class.__init__)
        expected_params = {name: param.annotation for name, param in sig.parameters.items() if name != "self"}
        logger.error(
            f"TypeError instantiating policy '{instance_name}' ({class_name}). "
            f"Provided args (types): {provided_arg_types}. "
            f"Expected params (annotations): {expected_params}. Error: {e}"
        )
        raise PolicyLoadError(
            f"Failed to instantiate policy '{instance_name}' ({class_name}) "
            "due to TypeError. Check constructor signature and provided config/dependencies."
        ) from e
    except Exception as e:
        logger.exception(
            f"Unexpected error instantiating policy '{instance_name}' ({class_name}) with args {instance_args}"
        )
        raise PolicyLoadError(f"Unexpected error instantiating policy '{instance_name}' ({class_name})") from e


def _set_instance_metadata(instance: ControlPolicy, instance_name: str, policy_class_path: str) -> None:
    """Set name and class path metadata on the instantiated policy."""
    class_name = instance.__class__.__name__
    try:
        setattr(instance, "name", instance_name)
    except AttributeError:
        logger.warning(f"Could not set 'name' attribute on policy instance '{instance_name}' ({class_name}).")

    try:
        setattr(instance, "policy_class_path", policy_class_path)
    except AttributeError:
        logger.warning(f"Could not set 'policy_class_path' attribute on instance '{instance_name}' ({class_name}).")


# --- MAIN Instantiator Function ---
async def instantiate_policy(
    policy_config: Dict[str, Any],
    settings: Settings,
    http_client: httpx.AsyncClient,
    api_key_lookup: ApiKeyLookupFunc,
) -> ControlPolicy:
    """
    Instantiates a ControlPolicy from its configuration dictionary, handling nested policies.

    Args:
        policy_config: The configuration dictionary for the policy. Must include
                       'policy_class_path' and 'name'. Nested policy configs should
                       be represented as dictionaries within this structure.
        settings: Application settings instance.
        http_client: Shared httpx client instance.
        api_key_lookup: API key lookup function.

    Returns:
        An instantiated ControlPolicy object.

    Raises:
        PolicyLoadError: If configuration is invalid, class cannot be loaded,
                         or instantiation fails.
    """
    # 1. Validate required keys
    _validate_config_keys(policy_config)
    policy_class_path = policy_config["policy_class_path"]
    instance_name = policy_config["name"]
    logger.debug(f"Starting instantiation for policy '{instance_name}' with class path '{policy_class_path}'")

    # 2. Import and validate the policy class
    policy_class = _import_and_validate_policy_class(policy_class_path, instance_name)

    # 3. Resolve nested policy configurations
    resolved_config = await _resolve_all_nested_configs(
        policy_config, instance_name, settings, http_client, api_key_lookup
    )

    # 4. Prepare constructor arguments (dependency injection, config mapping)
    instance_args = _prepare_constructor_args(
        policy_class, resolved_config, settings, http_client, api_key_lookup, instance_name
    )

    # 5. Validate that all required constructor arguments are present
    _validate_constructor_args(policy_class, instance_args, resolved_config, instance_name)

    # 6. Instantiate the policy
    instance = _create_policy_instance(policy_class, instance_args, instance_name)

    # 7. Set instance metadata (name, class path)
    _set_instance_metadata(instance, instance_name, policy_class_path)

    return instance
