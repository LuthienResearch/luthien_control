import importlib
import inspect
import json
import logging
from typing import Any, Callable, Dict, Optional, Type

import httpx
from pydantic_core import ValidationError

from luthien_control.config.settings import Settings
from luthien_control.control_policy.compound_policy import CompoundPolicy
from luthien_control.control_policy.interface import ControlPolicy

from .database import get_main_db_pool
from .models import ApiKey, Policy

logger = logging.getLogger(__name__)


# Type alias for the API key lookup function, assuming it returns Optional[ApiKey]
ApiKeyLookupFunc = Callable[[str], Callable[..., Optional[ApiKey]]]  # Simplified based on previous usage


class PolicyLoadError(Exception):
    """Custom exception for errors during policy loading/instantiation."""

    pass


async def get_api_key_by_value(key_value: str) -> Optional[ApiKey]:
    """
    Fetches an API key record from the database based on the key value.

    Args:
        key_value: The API key string to look up.

    Returns:
        An ApiKey object if found. If metadata JSON is invalid, metadata will be None.
        Returns None if key not found, DB pool not initialized, or other DB error occurs.
    """
    try:
        pool = get_main_db_pool()
    except RuntimeError:
        logger.error("Cannot fetch API key: Main database pool not initialized.")
        return None

    sql = """
        SELECT id, key_value, name, is_active, created_at, metadata_
        FROM api_keys
        WHERE key_value = $1
    """

    record = None
    try:
        async with pool.acquire() as conn:
            record = await conn.fetchrow(sql, key_value)

        if record:
            logger.debug(f"Found API key record for key starting with: {key_value[:4]}...")
            record_dict = dict(record)

            # Ensure metadata_ is None or a string before potential Pydantic validation
            if "metadata_" in record_dict and not isinstance(record_dict["metadata_"], (str, type(None))):
                logger.warning(
                    f"Unexpected type for metadata_ from DB: {type(record_dict['metadata_'])}. "
                    f"Expected string or None. Setting to None before validation."
                )
                record_dict["metadata_"] = None

            try:
                # Attempt to create the model
                api_key = ApiKey(**record_dict)
                return api_key
            except ValidationError as ve:
                # Check if the ONLY error was related to metadata_ parsing
                is_only_metadata_error = False
                if len(ve.errors()) == 1:
                    error_details = ve.errors()[0]
                    if error_details.get("loc") == ("metadata_",) and error_details.get("type") == "json_invalid":
                        is_only_metadata_error = True

                if is_only_metadata_error:
                    logger.warning(
                        f"Invalid JSON in metadata for key ID {record_dict.get('id', '?')}. "
                        f"Returning ApiKey with metadata=None. Error: {ve.errors()[0].get('msg')}"
                    )
                    # Retry creating the model with metadata explicitly set to None
                    record_dict["metadata_"] = None
                    try:
                        api_key_no_meta = ApiKey(**record_dict)
                        return api_key_no_meta
                    except ValidationError as ve_retry:
                        # Should not happen if only metadata was the issue, but log if it does
                        logger.error(
                            f"Failed to create ApiKey even after clearing metadata for key ID "
                            f"{record_dict.get('id', '?')}. Validation Errors: {ve_retry.errors()}"
                        )
                        # Fall through to the main exception handler -> return None
                else:
                    # Validation error was not just metadata or there were multiple errors
                    logger.error(
                        f"Pydantic validation failed for key ID {record_dict.get('id', '?')} "
                        f"(not just metadata): {ve.errors()}"
                    )
                    # Fall through to the main exception handler -> return None

        else:
            logger.debug(f"No API key record found for key starting with: {key_value[:4]}...")
            return None  # Key not found

    except Exception as e:
        # Catch other database errors or unexpected issues during processing
        if isinstance(e, ValidationError):
            # If we reached here from the ValidationError blocks above, log was already specific
            pass  # Already logged sufficiently
        else:
            logger.exception(f"Database error fetching API key for key starting with {key_value[:4]}...: {e}")
        return None


async def get_policy_config_by_name(name: str) -> Optional[Policy]:
    """
    Fetches an active policy configuration record from the database by its unique name.

    Args:
        name: The unique name of the policy instance to look up.

    Returns:
        A Policy object if an active policy with the given name is found.
        Returns None if the policy is not found, not active, the DB pool is not initialized,
        or a database or validation error occurs.
    """
    try:
        pool = get_main_db_pool()
    except RuntimeError:
        logger.error("Cannot fetch policy config: Main database pool not initialized.")
        return None

    sql = """
        SELECT id, name, policy_class_path, config, is_active, description, created_at, updated_at
        FROM policies
        WHERE name = $1 AND is_active = TRUE
    """

    record = None
    try:
        async with pool.acquire() as conn:
            record = await conn.fetchrow(sql, name)

        if record:
            logger.debug(f"Found active policy record for name: {name}")
            record_dict = dict(record)

            # Ensure the 'config' field is parsed from JSON string if necessary
            config_value = record_dict.get("config")
            if isinstance(config_value, str):
                try:
                    record_dict["config"] = json.loads(config_value)
                    logger.debug(f"Parsed JSON string in 'config' for policy '{name}'.")
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON string in 'config' for policy '{name}'. Setting config to None.")
                    record_dict["config"] = None
            elif config_value is not None and not isinstance(config_value, dict):
                logger.warning(
                    f"Unexpected type for 'config' field for policy '{name}': "
                    f"{type(config_value)}. Attempting to proceed."
                )
            elif config_value is None:  # Ensure config is always a dict
                record_dict["config"] = {}

            try:
                policy_config_model = Policy(**record_dict)
                return policy_config_model
            except ValidationError as ve:
                logger.error(
                    f"Pydantic validation failed for policy name '{name}'. Record: {record_dict}. Errors: {ve.errors()}"
                )
                return None  # Validation failed
        else:
            logger.debug(f"No active policy record found for name: {name}")
            return None  # Policy not found or not active

    except Exception as e:
        logger.exception(f"Database error fetching policy config for name '{name}': {e}")
        return None


# NEW: Recursive Instantiator
async def instantiate_policy(
    policy_config: Dict[str, Any],
    settings: Settings,
    http_client: httpx.AsyncClient,
    api_key_lookup: ApiKeyLookupFunc,
) -> ControlPolicy:
    """
    Recursively instantiates a ControlPolicy from its configuration dictionary.

    Identifies nested policies within the config dict (or lists therein) by checking
    for the presence of 'policy_class_path' and recursively calls itself.

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
        PolicyLoadError: If required keys are missing, class cannot be imported,
                         is invalid, or instantiation fails.
        ImportError/AttributeError: If the policy class cannot be imported.
    """
    # 1. Validate required keys in the input config
    if "policy_class_path" not in policy_config:
        raise PolicyLoadError("Policy config dictionary is missing required key: 'policy_class_path'.")
    if "name" not in policy_config:
        raise PolicyLoadError("Policy config dictionary is missing required key: 'name'.")

    policy_class_path = policy_config["policy_class_path"]
    instance_name = policy_config["name"]
    logger.debug(f"Starting instantiation for policy '{instance_name}' with class path '{policy_class_path}'")

    # 2. Import the policy class dynamically
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

    # 3. Recursively resolve nested policies within a copy of the config
    resolved_config: Dict[str, Any] = {}
    try:
        logger.debug(f"Processing config keys for '{instance_name}' to resolve nested policies...")
        for key, value in policy_config.items():
            # Skip meta-keys needed earlier but not for recursion/injection
            if key in ["policy_class_path", "name"]:
                continue

            # Check if value is a dict representing a nested policy
            if isinstance(value, dict) and "policy_class_path" in value:
                nested_name = value.get("name", "<unknown_nested>")
                logger.debug(
                    f"Found nested policy config '{nested_name}' under key '{key}' "
                    f"for '{instance_name}'. Recursively instantiating..."
                )
                resolved_config[key] = await instantiate_policy(value, settings, http_client, api_key_lookup)
            # Check if value is a list possibly containing nested policy dicts
            elif isinstance(value, list):
                resolved_list = []
                for index, item in enumerate(value):
                    if isinstance(item, dict) and "policy_class_path" in item:
                        nested_name = item.get("name", f"<unknown_nested_in_list_idx_{index}>")
                        logger.debug(
                            f"Found nested policy config '{nested_name}' in list under key "
                            f"'{key}' (index {index}) for '{instance_name}'. Recursively instantiating..."
                        )
                        resolved_list.append(await instantiate_policy(item, settings, http_client, api_key_lookup))
                    else:
                        # If item in list is not a policy config dict, keep it as is
                        # We don't recursively process arbitrary dicts/lists within lists here,
                        # only dicts identified as policy configs.
                        resolved_list.append(item)
                resolved_config[key] = resolved_list
            else:
                # Keep non-policy-config values as they are
                resolved_config[key] = value
        logger.debug(f"Finished resolving nested configurations for '{instance_name}'.")
    except PolicyLoadError as e:
        # Propagate errors from recursive calls, adding context
        logger.error(f"Failed during recursive instantiation for nested policy within '{instance_name}': {e}")
        raise PolicyLoadError(f"Failed to instantiate nested policy within '{instance_name}'.") from e
    except Exception as e:  # Catch unexpected errors during resolution
        logger.exception(f"Unexpected error resolving nested config for '{instance_name}': {e}")
        raise PolicyLoadError(f"Unexpected error resolving nested config for '{instance_name}'.") from e

    # 4. Prepare arguments for final instantiation
    instance_args: Dict[str, Any] = {}
    sig = inspect.signature(policy_class.__init__)
    init_params = sig.parameters

    # 5. Inject common dependencies
    if "settings" in init_params:
        instance_args["settings"] = settings
    if "http_client" in init_params:
        instance_args["http_client"] = http_client
    if "api_key_lookup" in init_params:
        instance_args["api_key_lookup"] = api_key_lookup

    # 6. Inject resolved configuration parameters
    for key, value in resolved_config.items():
        if key in init_params and key not in instance_args:
            instance_args[key] = value
            logger.debug(f"Injecting resolved config key '{key}' into '{instance_name}' ({class_name})")
        elif key not in init_params:
            # Only warn if the key was present in config but not used by __init__
            logger.warning(
                f"Config key '{key}' for policy '{instance_name}' was processed but does not match any parameter "
                f"in {class_name}.__init__. Ignoring."
            )

    # --- Special Handling for Known Composite Types --- #
    # Map specific config keys to expected constructor arguments if needed.
    # Example: Map 'member_policy_configs' from config to 'policies' constructor arg for CompoundPolicy.
    if issubclass(policy_class, CompoundPolicy) and "member_policy_configs" in resolved_config:
        if "policies" not in instance_args:  # Check if already injected (e.g., by dependency)
            # Ensure the resolved value is a list, as expected by CompoundPolicy
            member_policies = resolved_config.pop("member_policy_configs")
            if isinstance(member_policies, list):
                instance_args["policies"] = member_policies
                logger.debug(f"Mapped resolved 'member_policy_configs' list to 'policies' arg for {instance_name}")
            else:
                # This shouldn't happen if the config resolution worked correctly,
                # but raise an error just in case.
                raise PolicyLoadError(
                    f"Configuration error for {instance_name}: 'member_policy_configs' resolved to type "
                    f"{type(member_policies).__name__}, but expected a list for CompoundPolicy."
                )
        else:
            logger.warning(
                f"'policies' argument for {instance_name} was already populated, "
                f"skipping mapping from 'member_policy_configs'."
            )
    # Add elif issubclass(...) blocks here for other composite types requiring specific mapping

    # 7. Parameter Validation (Check for missing required args)
    missing_required = []
    for param_name, param in init_params.items():
        if param.name == "self":
            continue
        if param_name not in instance_args and param.default is inspect.Parameter.empty:
            missing_required.append(param_name)

    if missing_required:
        raise PolicyLoadError(
            f"Cannot instantiate policy '{instance_name}' ({class_name}). "
            f"Missing required arguments: {missing_required}. "
            f"Provided arguments: {list(instance_args.keys())}. Resolved config keys: {list(resolved_config.keys())}. "
            f"Required by __init__: {list(p for p in init_params if p != 'self')}"
        )

    # 8. Instantiate the policy
    try:
        instance = policy_class(**instance_args)
        logger.info(f"Successfully instantiated policy instance '{instance_name}' of type '{class_name}'")
    except TypeError as e:
        logger.error(
            f"TypeError instantiating policy '{instance_name}' ({class_name}). "
            f"Attempted args: { {k: type(v).__name__ for k, v in instance_args.items()} }. Error: {e}"
        )
        raise PolicyLoadError(
            f"Failed to instantiate policy '{instance_name}' ({class_name}) "
            "due to TypeError. Check constructor signature."
        ) from e
    except Exception as e:
        logger.exception(
            f"Unexpected error instantiating policy '{instance_name}' ({class_name}) with args {instance_args}"
        )
        raise PolicyLoadError(f"Unexpected error instantiating policy '{instance_name}' ({class_name})") from e

    # 9. Assign instance name and class path (useful for logging/identification/serialization)
    # Ensure these attributes exist and are writable, log warning if not.
    try:
        setattr(instance, "name", instance_name)
    except AttributeError:
        logger.warning(f"Could not set 'name' attribute on policy instance '{instance_name}' ({class_name}).")

    try:
        setattr(instance, "policy_class_path", policy_class_path)
    except AttributeError:
        logger.warning(f"Could not set 'policy_class_path' attribute on instance '{instance_name}' ({class_name}).")

    return instance


# NEW: Public entry point for loading from DB
async def load_policy_from_db(
    name: str,
    settings: Settings,
    http_client: httpx.AsyncClient,
    api_key_lookup: ApiKeyLookupFunc,
) -> ControlPolicy:
    """
    Loads and instantiates a ControlPolicy instance by fetching its configuration
    from the database by name and then recursively instantiating it.

    Args:
        name: The unique name of the policy instance to load from the database.
        settings: The application settings instance.
        http_client: The shared httpx client instance.
        api_key_lookup: The function to look up API keys.

    Returns:
        An instantiated ControlPolicy object.

    Raises:
        PolicyLoadError: If the policy configuration cannot be found in the DB,
                         is invalid, or instantiation fails.
    """
    logger.info(f"Loading policy configuration from database for: '{name}'")

    # 1. Fetch the root policy configuration model from the database
    policy_model = await get_policy_config_by_name(name)
    if not policy_model:
        raise PolicyLoadError(f"Active policy configuration named '{name}' not found in database.")

    if not policy_model.policy_class_path:
        raise PolicyLoadError(f"Policy configuration for '{name}' fetched from DB is missing 'policy_class_path'.")

    # 2. Prepare the initial configuration dictionary for the instantiator
    # The instantiator expects 'name' and 'policy_class_path' directly in the dict.
    initial_config = policy_model.config or {}
    initial_config["name"] = policy_model.name  # Ensure name from DB model is used
    initial_config["policy_class_path"] = policy_model.policy_class_path

    # 3. Call the recursive instantiator
    try:
        instance = await instantiate_policy(
            policy_config=initial_config,
            settings=settings,
            http_client=http_client,
            api_key_lookup=api_key_lookup,
        )
        logger.info(f"Successfully loaded and instantiated policy '{name}' from database.")
        return instance
    except PolicyLoadError as e:
        logger.error(f"Failed to instantiate policy '{name}' after fetching from DB: {e}")
        # Re-raise cleanly, context is already included from instantiate_policy
        raise e
    except Exception as e:
        logger.exception(f"Unexpected error instantiating '{name}' after fetching from DB: {e}")
        raise PolicyLoadError(f"Unexpected error during instantiation process for '{name}'.") from e
