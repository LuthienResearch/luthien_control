#!/usr/bin/env python
"""Loads the 'root' policy and prints its new serialized configuration."""

import asyncio
import json
import logging
import os
import sys

import httpx

# Adjust path to import from the project root
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

# Now import necessary components
try:
    from luthien_control.config.settings import Settings
    from luthien_control.db.api_key_crud import get_api_key_by_value
    from luthien_control.db.database import close_main_db_pool, create_main_db_pool
    from luthien_control.db.policy_crud import (
        ApiKeyLookupFunc,
        load_policy_from_db,
    )
except ImportError as e:
    print(f"Error importing project modules: {e}", file=sys.stderr)
    print(
        "Ensure the script is run from the project root using "
        "'poetry run python scripts/generate_root_policy_config.py'",
        file=sys.stderr,
    )
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def main():
    """Loads the root policy and prints its serialized config."""
    settings = Settings()
    http_client = httpx.AsyncClient()
    # Use the actual function for API key lookup
    api_key_lookup: ApiKeyLookupFunc = get_api_key_by_value

    try:
        # Connect to the database (required by get_api_key_by_value and potentially load_policy_from_db)
        logger.info("Connecting to the main database...")
        await create_main_db_pool()
        logger.info("Database pool initialized.")

        root_policy_name = settings.get_top_level_policy_name()
        logger.info(f"Loading policy instance: '{root_policy_name}'...")

        # Load the instance - this uses the *old* config from DB to build the object initially
        root_policy_instance = await load_policy_from_db(
            name=root_policy_name,
            settings=settings,
            http_client=http_client,
            api_key_lookup=api_key_lookup,
        )
        logger.info(f"Policy instance '{root_policy_name}' loaded successfully.")

        # Serialize the loaded instance - this uses the *new* serialize_config logic
        logger.info("Serializing the loaded policy instance...")
        new_config = root_policy_instance.serialize_config()
        logger.info("Serialization complete.")

        # Print the new config as JSON
        print("\n--- Generated Root Policy Configuration (New Format) ---")
        print(json.dumps(new_config, indent=2))
        print("--- End Configuration ---")

    except Exception as e:
        logger.exception(f"An error occurred: {e}")
        sys.exit(1)
    finally:
        # Ensure database pool is closed
        logger.info("Closing database pool...")
        await close_main_db_pool()
        await http_client.aclose()
        logger.info("Cleanup complete.")


if __name__ == "__main__":
    # Load environment variables from .env if present (important for Settings)
    from dotenv import load_dotenv

    env_path = os.path.join(project_root, ".env")
    if os.path.exists(env_path):
        logger.info(f"Loading environment variables from: {env_path}")
        load_dotenv(dotenv_path=env_path, verbose=True)
    else:
        logger.warning(f".env file not found at {env_path}, relying on system environment variables.")

    asyncio.run(main())
