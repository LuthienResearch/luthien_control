#!/usr/bin/env python
"""Loads the 'root' policy and prints its new serialized configuration."""

import asyncio
import json
import logging
import sys

import httpx

# Load environment variables from .env if present BEFORE importing Settings
from dotenv import load_dotenv
from luthien_control.db.database_async import get_main_db_session  # noqa: E402

load_dotenv(verbose=True)  # load_dotenv searches for .env automatically

# Now import settings AFTER dotenv may have loaded variables
from luthien_control.config.settings import Settings  # noqa: E402

# Now import necessary components
try:
    from luthien_control.db.sqlmodel_crud import (
        ApiKeyLookupFunc,
        get_api_key_by_value,
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
        # Removed explicit pool creation - get_main_db_session handles engine/session
        logger.info("Database session will be managed by get_main_db_session.")

        root_policy_name = settings.get_top_level_policy_name()
        logger.info(f"Loading policy instance: '{root_policy_name}'...")

        # Load the instance - this uses the *old* config from DB to build the object initially
        # get_main_db_session manages the underlying engine and session
        async with get_main_db_session() as session:
            root_policy_instance = await load_policy_from_db(
                name=root_policy_name,
                settings=settings,
                http_client=http_client,
                api_key_lookup=api_key_lookup,
                session=session,
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
        # Removed explicit pool closing
        await http_client.aclose()
        logger.info("Cleanup complete (HTTP client closed).")


if __name__ == "__main__":
    asyncio.run(main())
