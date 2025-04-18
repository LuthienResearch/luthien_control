import asyncio
import logging
import sys

from dotenv import load_dotenv

from luthien_control.config.settings import Settings
from luthien_control.db.database_async import (
    close_main_db_engine,
    create_main_db_engine,
    get_main_db_session,
)
from luthien_control.db.sqlmodel_crud import list_policies

# Configure logging to see output
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


async def main():
    load_dotenv()  # Load env vars before creating engine
    Settings()  # Initialize settings if needed elsewhere

    try:
        # Initialize the engine and session factory
        engine = await create_main_db_engine()
        if not engine:
            logger.error("Failed to create database engine. Check environment variables.")
            return

        # Use the session factory to get a session via the async generator
        async for session in get_main_db_session():  # Corrected usage: async for
            logger.info("\n--- Listing Policy Configurations ---")
            policies = await list_policies(session)  # Pass session here
            if policies:
                logger.info(f"Found {len(policies)} policy configurations:")
                for i, policy in enumerate(policies):
                    print(f"\nPolicy {i + 1}:")  # Use print for clearer output in script
                    print(f"  ID: {policy.id}")
                    print(f"  Name: {policy.name}")
                    print(f"  Class Path: {policy.policy_class_path}")
                    print(f"  Config: {policy.config}")
                    print(f"  Is Active: {policy.is_active}")
                    print(f"  Description: {policy.description}")
                    print(f"  Created At: {policy.created_at}")
                    print(f"  Updated At: {policy.updated_at}")
            else:
                logger.info("No policy configurations found in the database.")
            logger.info("--- End Listing ---\n")
            # Assuming we only need one session block for this script's purpose
            break  # Exit the loop after the first session is used

    except Exception as e:
        logger.exception(f"An error occurred: {e}")
    finally:
        # Close the engine (uses global variable)
        await close_main_db_engine()


if __name__ == "__main__":
    asyncio.run(main())
