import json
import logging
from typing import Optional

import httpx
from pydantic import ValidationError

from luthien_control.config.settings import Settings
from luthien_control.control_policy.interface import ControlPolicy
from luthien_control.core.policy_loader import (
    ApiKeyLookupFunc,
    PolicyLoadError,
    instantiate_policy,
)

from .database import get_main_db_pool
from .models import TABLE_NAME_MAP, ClientApiKey, Policy

logger = logging.getLogger(__name__)


async def get_api_key_by_value(key_value: str) -> Optional[ClientApiKey]:
    """
    Fetches an API key record from the database based on the key value.

    Args:
        key_value: The API key string to look up.

    Returns:
        An ClientApiKey object if found. If metadata JSON is invalid, metadata will be None.
        Returns None if key not found, DB pool not initialized, or other DB error occurs.
    """
    try:
        pool = get_main_db_pool()
    except RuntimeError:
        logger.error("Cannot fetch API key: Main database pool not initialized.")
        return None

    # Get table name from the central mapping
    table_name = TABLE_NAME_MAP.get(ClientApiKey)
    if not table_name:
        # This should ideally not happen if the map is maintained
        logger.critical("CRITICAL: Table name for ClientApiKey not found in TABLE_NAME_MAP. Cannot proceed.")
        # Depending on desired robustness, could default or raise an exception
        # For now, let's prevent execution with a missing mapping
        return None  # Or raise an error

    # Use an f-string to insert the table name. This is safe as the table name
    # comes from our defined mapping, not external input.
    # Parameterization ($1) is still used for the actual key_value, preventing SQL injection.
    sql = f"""
        SELECT id, key_value, name, is_active, created_at, metadata_
        FROM {table_name}
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
                api_key = ClientApiKey(**record_dict)
                return api_key
            except ValidationError as ve:
                # Log a warning if metadata JSON is invalid
                if "metadata_" in record_dict and record_dict["metadata_"] is not None:
                    logger.warning(
                        f"Invalid JSON in metadata for key ID {record_dict.get('id', '?')}. "
                        f"Returning ClientApiKey with metadata=None. Error: {ve.errors()[0].get('msg')}"
                    )
                    # Retry creating the model with metadata explicitly set to None
                    record_dict["metadata_"] = None
                    try:
                        api_key_no_meta = ClientApiKey(**record_dict)
                        return api_key_no_meta
                    except ValidationError as ve_retry:
                        # Should not happen if only metadata was the issue, but log if it does
                        logger.error(
                            f"Failed to create ClientApiKey even after clearing metadata for key ID "
                            f"{record_dict.get('id', '?')}. Validation Errors: {ve_retry.errors()}"
                        )
                        return None  # Or re-raise, depending on desired behavior
                else:
                    # Validation error wasn't due to metadata
                    logger.error(
                        f"Pydantic validation error for API key ID {record_dict.get('id', '?')} "
                        f"(not metadata related): {ve.errors()}"
                    )
                    return None

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


# Public entry point for loading from DB
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

    # 3. Call the recursive instantiator (imported from core.policy_loader)
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
