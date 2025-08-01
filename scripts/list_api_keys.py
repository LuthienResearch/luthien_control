#!/usr/bin/env python
import argparse
import asyncio
import logging
import sys

from dotenv import load_dotenv
from luthien_control.db.client_api_key_crud import list_api_keys
from luthien_control.db.database_async import (
    close_db_engine,
    create_db_engine,
    get_db_session,
)
from luthien_control.settings import Settings

# Configure logging to see output
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


async def main():
    parser = argparse.ArgumentParser(description="List all API keys in the database.")
    parser.add_argument("--active-only", action="store_true", help="Only show active API keys.")
    args = parser.parse_args()

    load_dotenv()  # Load env vars before creating engine
    Settings()  # Initialize settings if needed elsewhere

    logger.info("Attempting to list API keys...")

    try:
        engine = await create_db_engine()
        if not engine:
            logger.error("Failed to create database engine.")
            return

        async with get_db_session() as session:
            logger.info("\n--- Listing API Keys ---")
            keys = await list_api_keys(session, active_only=args.active_only)
            if keys:
                logger.info(f"Found {len(keys)} API keys:")
                for i, key in enumerate(keys):
                    print(f"\nAPI Key {i + 1}:")
                    print(f"  ID: {key.id}")
                    print(f"  Name: {key.name}")
                    print(f"  Key Value: {key.key_value}")
                    print(f"  Is Active: {key.is_active}")
                    print(f"  Created At: {key.created_at}")
                    if key.metadata_:
                        print(f"  Metadata: {key.metadata_}")
            else:
                logger.info("No API keys found in the database.")
            logger.info("--- End Listing ---")

    except Exception as e:
        logger.exception(f"An error occurred while listing API keys: {e}")
    finally:
        await close_db_engine()
        logger.info("Database connection closed.")


if __name__ == "__main__":
    asyncio.run(main())
