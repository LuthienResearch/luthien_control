#!/usr/bin/env python
import argparse
import asyncio
import logging
import sys

from luthien_control.db.database_async import (
    close_db_engine,
    create_db_engine,
    get_db_session,
)
from luthien_control.db.sqlmodel_crud import create_api_key
from luthien_control.db.sqlmodel_models import ClientApiKey
from luthien_control.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


async def main():
    parser = argparse.ArgumentParser(description="Add a new Client API Key to the database.")
    parser.add_argument("--key-value", required=True, help="The value of the API key.")
    parser.add_argument("--name", required=True, help="A descriptive name for the API key.")
    parser.add_argument(
        "--inactive",
        action="store_true",
        help="Create the key in an inactive state (default: active).",
    )
    args = parser.parse_args()

    logger.info(
        f"Attempting to add API key: Name='{args.name}', "
        f"KeyValue='{args.key_value[:4]}...' "
        f"Active={not args.inactive}"
    )

    engine = await create_db_engine()
    if not engine:
        logger.error("Failed to create database engine. Aborting.")
        sys.exit(1)

    new_key = ClientApiKey(
        key_value=args.key_value,
        name=args.name,
        is_active=not args.inactive,
    )

    try:
        async with get_db_session() as session:
            created_key = await create_api_key(session, new_key)
            if created_key:
                logger.info(f"Successfully added API key ID: {created_key.id}, Name: {created_key.name}")
            else:
                logger.error("Failed to add API key to the database (create_api_key returned None).")
                # Attempting to provide more context if possible
                # Note: This check is basic, specific DB errors are logged within create_api_key
                logger.warning("This might be due to a duplicate key_value or other database constraint.")
                sys.exit(1) # Exit with error if creation failed

    except Exception as e:
        logger.exception(f"An unexpected error occurred during API key creation: {e}")
        sys.exit(1) # Exit with error on exception
    finally:
        # Ensure engine is closed regardless of success or failure
        await close_db_engine()
        logger.info("Database engine closed.")


if __name__ == "__main__":
    # Ensure Alembic operations aren't run automatically if models are imported
    # This is relevant if this script indirectly causes model imports that trigger Alembic checks
    # os.environ['ALEMBIC_CONTEXT'] = 'false'
    asyncio.run(main())
