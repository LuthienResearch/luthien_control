import importlib
import inspect
import logging
from typing import Any, Callable, Dict, Optional, Set, Type  # Updated

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

            # Handle potential JSON parsing for config if needed (assuming it's text/jsonb from DB)
            # Example: If DB returns JSON string, uncomment below:
            # if isinstance(record_dict.get("config"), str):
            #     try:
            #         record_dict["config"] = json.loads(record_dict["config"])
            #     except json.JSONDecodeError:
            #         logger.error(f"Invalid JSON in config for policy {name}. Setting config to None.")
            #         record_dict["config"] = None

            try:
                policy_config = Policy(**record_dict)
                return policy_config
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


async def load_policy_instance(
    name: str,
    settings: Settings,
    http_client: httpx.AsyncClient,
    api_key_lookup: ApiKeyLookupFunc,
    _visited_names: Optional[Set[str]] = None,
) -> ControlPolicy:
    """
    Loads and instantiates a ControlPolicy instance from the database by name.

    Handles dependency injection (settings, http_client, api_key_lookup), dynamic
    class loading, configuration parameter passing, and recursive loading for
    composite policies like CompoundPolicy.

    Args:
        name: The unique name of the policy instance to load.
        settings: The application settings instance.
        http_client: The shared httpx client instance.
        api_key_lookup: The function to look up API keys.
        _visited_names: A set used internally to detect circular dependencies during recursion.

    Returns:
        An instantiated ControlPolicy object.

    Raises:
        PolicyLoadError: If the policy cannot be found, loaded, or instantiated,
                         or if a circular dependency is detected.
        ImportError/AttributeError: If the policy class cannot be imported.
    """
    if _visited_names is None:
        _visited_names = set()

    if name in _visited_names:
        raise PolicyLoadError(f"Circular dependency detected while loading policy: {name} visited again.")
    _visited_names.add(name)

    logger.debug(f"Attempting to load policy instance: '{name}'")

    # 1. Fetch the policy configuration from DB
    policy_config = await get_policy_config_by_name(name)
    if not policy_config:
        raise PolicyLoadError(f"Active policy configuration named '{name}' not found in database.")

    # 2. Import the policy class dynamically
    policy_class_path = policy_config.policy_class_path
    try:
        module_path, class_name = policy_class_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        policy_class: Type[ControlPolicy] = getattr(module, class_name)
        logger.debug(f"Successfully imported class '{class_name}' from '{module_path}'")
    except (ImportError, AttributeError, ValueError) as e:
        logger.error(f"Failed to import policy class '{policy_class_path}' for instance '{name}': {e}")
        raise PolicyLoadError(
            f"Could not load policy class '{policy_class_path}' for instance '{name}'. "
            f"Check path and ensure class exists."
        ) from e

    if not issubclass(policy_class, ControlPolicy):
        raise PolicyLoadError(
            f"Class '{class_name}' from '{module_path}' does not inherit from "
            f"ControlPolicy (or is not a Protocol implementation)."
        )

    # 3. Prepare arguments for instantiation
    db_config: Dict[str, Any] = policy_config.config or {}
    instance_args: Dict[str, Any] = {}
    sig = inspect.signature(policy_class.__init__)
    init_params = sig.parameters

    # 4. Inject common dependencies
    if "settings" in init_params:
        instance_args["settings"] = settings
        logger.debug(f"Injecting 'settings' dependency into '{name}' ({class_name})")
    if "http_client" in init_params:
        instance_args["http_client"] = http_client
        logger.debug(f"Injecting 'http_client' dependency into '{name}' ({class_name})")
    if "api_key_lookup" in init_params:
        instance_args["api_key_lookup"] = api_key_lookup
        logger.debug(f"Injecting 'api_key_lookup' dependency into '{name}' ({class_name})")

    # 5. Handle Special Composite Types (Recursively Load Members)
    if issubclass(policy_class, CompoundPolicy):
        member_names = db_config.get("member_policy_names", [])
        if not isinstance(member_names, list):
            raise PolicyLoadError(
                f"Invalid config for CompoundPolicy instance '{name}': 'member_policy_names' must be a list."
            )

        if not member_names:
            logger.warning(f"CompoundPolicy instance '{name}' has no member policies configured.")

        loaded_members = []
        for member_name in member_names:
            if not isinstance(member_name, str):
                logger.warning(f"Skipping non-string member name '{member_name}' in CompoundPolicy '{name}'.")
                continue
            try:
                logger.debug(f"Recursively loading member '{member_name}' for CompoundPolicy '{name}'")
                member_instance = await load_policy_instance(
                    member_name, settings, http_client, api_key_lookup, _visited_names.copy()
                )
                loaded_members.append(member_instance)
            except PolicyLoadError as e:
                logger.error(f"Failed to load member policy '{member_name}' for CompoundPolicy '{name}': {e}")
                raise PolicyLoadError(
                    f"Failed to load member policy '{member_name}' for CompoundPolicy '{name}'"
                ) from e

        instance_args["policies"] = loaded_members  # Matches CompoundPolicy.__init__
        logger.debug(f"Injecting {len(loaded_members)} loaded members into CompoundPolicy '{name}' as 'policies' arg.")

        # Remove the name list from db_config so it's not passed as a direct arg
        db_config.pop("member_policy_names", None)

    # --- Add other composite type handlers here using `elif issubclass(...)` --- #
    # elif issubclass(policy_class, HypotheticalConditionalPolicy):
    #     # ... load true/false policies recursively ...
    #     instance_args["policy_if_true"] = loaded_true_policy
    #     instance_args["policy_if_false"] = loaded_false_policy
    #     db_config.pop("policy_if_true_name", None)
    #     db_config.pop("policy_if_false_name", None)

    # 6. Inject remaining configuration from db_config into instance_args
    for key, value in db_config.items():
        if key in init_params and key not in instance_args:
            instance_args[key] = value
            logger.debug(f"Injecting config key '{key}' into '{name}' ({class_name})")
        elif key not in init_params:
            logger.warning(
                f"Config key '{key}' for policy '{name}' does not match any parameter "
                f"in {class_name}.__init__. Ignoring."
            )

    # 7. Parameter Validation (Check for missing required args)
    missing_required = []
    for param_name, param in init_params.items():
        if param.name == "self":
            continue
        # Check if it's missing and has no default value
        if param_name not in instance_args and param.default is inspect.Parameter.empty:
            missing_required.append(param_name)

    if missing_required:
        raise PolicyLoadError(
            f"Cannot instantiate policy '{name}' ({class_name}). Missing required arguments: {missing_required}. "
            f"Provided arguments: {list(instance_args.keys())}. Required by __init__: {list(init_params.keys())}"
        )

    # 8. Instantiate the policy
    try:
        instance = policy_class(**instance_args)
        logger.info(f"Successfully instantiated policy instance '{name}' of type '{class_name}'")
    except TypeError as e:
        logger.error(f"TypeError instantiating policy '{name}' ({class_name}) with args {instance_args}: {e}")
        raise PolicyLoadError(f"Failed to instantiate policy '{name}' ({class_name}) due to TypeError") from e
    except Exception as e:
        logger.exception(f"Unexpected error instantiating policy '{name}' ({class_name})")
        raise PolicyLoadError(f"Unexpected error instantiating policy '{name}' ({class_name})") from e

    # 9. Assign instance name (useful for logging/identification)
    # Check if the instance *actually* has a 'name' attribute before assigning
    # This avoids errors if a policy class doesn't define it.
    if hasattr(instance, "name"):
        try:
            # Use setattr cautiously; direct assignment might be better if `name` is expected
            setattr(instance, "name", policy_config.name)
            logger.debug(f"Assigned instance name '{policy_config.name}' to loaded policy object.")
        except AttributeError:
            # This might happen if 'name' is a read-only property
            logger.warning(f"Could not set 'name' attribute on policy instance '{name}' ({class_name}).")
    else:
        logger.debug(
            f"Policy class '{class_name}' does not have a 'name' attribute to assign instance "
            f"name '{policy_config.name}'."
        )

    # 10. Return the instantiated policy
    return instance
