import json
import logging
from typing import List, Optional

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
from .models import Policy

logger = logging.getLogger(__name__)


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


def _parse_and_validate_policy_record(record) -> Optional[Policy]:
    """Parses and validates a single raw DB record into a Policy object."""
    try:
        record_dict = dict(record)
        config_value = record_dict.get("config")

        # Ensure 'config' is a dictionary or None
        if isinstance(config_value, str):
            try:
                record_dict["config"] = json.loads(config_value)
            except json.JSONDecodeError:
                logger.error(
                    f"Invalid JSON string in 'config' for policy ID {record_dict.get('id', '?')} "
                    f"(name: {record_dict.get('name', '?')}). Skipping this record."
                )
                return None  # Skip this record
        elif config_value is not None and not isinstance(config_value, dict):
            logger.warning(
                f"Unexpected type for 'config' field for policy ID {record_dict.get('id', '?')} "
                f"(name: {record_dict.get('name', '?')}). Type: {type(config_value)}. Attempting validation."
            )
        elif config_value is None:
            record_dict["config"] = {}  # Default to empty dict if None

        # Validate with Pydantic model
        policy_model = Policy(**record_dict)
        return policy_model

    except ValidationError as ve:
        logger.error(
            f"Pydantic validation failed for policy record ID {record.get('id', '?')} "
            f"(name: {record.get('name', '?')}). Record: {dict(record)}. Errors: {ve.errors()}. Skipping."
        )
        return None
    except Exception as e:
        # Catch unexpected errors during processing of a single record
        logger.exception(
            f"Unexpected error processing policy record ID {record.get('id', '?')} "
            f"(name: {record.get('name', '?')}): {e}. Skipping."
        )
        return None


async def list_policy_configs() -> List[Policy]:
    """
    Fetches all policy configuration records from the database.

    Returns:
        A list of Policy objects. Returns an empty list if the DB pool is not
        initialized, no policies are found, or a database error occurs during fetch.
        Invalid policy records (e.g., bad JSON config, Pydantic validation fail)
        will be logged as errors and excluded from the returned list.
    """
    try:
        pool = get_main_db_pool()
    except RuntimeError:
        logger.error("Cannot list policy configs: Main database pool not initialized.")
        return []

    # Fetch all columns needed for the Policy model
    sql = """
        SELECT id, name, policy_class_path, config, is_active, description, created_at, updated_at
        FROM policies
        ORDER BY name  -- Optional: order for consistency
    """

    records = []
    try:
        async with pool.acquire() as conn:
            records = await conn.fetch(sql)
        logger.info(f"Fetched {len(records)} policy configuration records from the database.")
    except Exception as e:
        logger.exception(f"Database error fetching all policy configs: {e}")
        return []  # Return empty list on fetch error

    valid_policies = []
    for record in records:
        policy_model = _parse_and_validate_policy_record(record)
        if policy_model:
            valid_policies.append(policy_model)

    logger.info(f"Successfully validated and returning {len(valid_policies)} policy configurations.")
    return valid_policies


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
