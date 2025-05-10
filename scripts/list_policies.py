import asyncio
import logging
import sys

from dotenv import load_dotenv
from luthien_control.db.control_policy_crud import list_policies
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
    load_dotenv()  # Load env vars before creating engine
    Settings()  # Initialize settings if needed elsewhere

    logger.info("Attempting to list policy configurations...")

    try:
        engine = await create_db_engine()
        if not engine:
            logger.error("Failed to create database engine.")
            return

        async with get_db_session() as session:
            logger.info("\n--- Listing Policy Configurations ---")
            policies = await list_policies(session)
            if policies:
                logger.info(f"Found {len(policies)} policy configurations:")
                for i, policy in enumerate(policies):
                    print(f"\nPolicy {i + 1}:")
                    print(f"  ID: {policy.id}")
                    print(f"  Name: {policy.policy_type}")
                    print(f"  Config: {policy.config}")
                    print(f"  Is Active: {policy.is_active}")
                    print(f"  Description: {policy.description}")
                    print(f"  Created At: {policy.created_at}")
                    print(f"  Updated At: {policy.updated_at}")
            else:
                logger.info("No policy configurations found in the database.")
            logger.info("--- End Listing ---")

    except Exception as e:
        logger.exception(f"An error occurred while listing policies: {e}")
    finally:
        await close_db_engine()
        logger.info("Database connection closed.")


if __name__ == "__main__":
    asyncio.run(main())
