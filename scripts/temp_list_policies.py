import asyncio
import logging
import sys

from luthien_control.config.settings import Settings
from luthien_control.db.database import close_main_db_pool, create_main_db_pool
from luthien_control.db.policy_crud import list_policy_configs

# Configure logging to see output
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# Add project root to path to allow imports
sys.path.insert(0, ".")


async def main():
    Settings()
    pool_created = False
    try:
        # create_main_db_pool reads env vars/uses settings implicitly via os.getenv
        # so we don't need to pass settings here.
        await create_main_db_pool()
        pool_created = True  # Assume success if no exception
        print("\n--- Listing Policy Configurations ---")
        policies = await list_policy_configs()
        if policies:
            print(f"Found {len(policies)} policy configurations:")
            for i, policy in enumerate(policies):
                print(f"\nPolicy {i + 1}:")
                print(f"  ID: {policy.id}")
                print(f"  Name: {policy.name}")
                print(f"  Class Path: {policy.policy_class_path}")
                print(f"  Config: {policy.config}")
                print(f"  Is Active: {policy.is_active}")
                print(f"  Description: {policy.description}")
                print(f"  Created At: {policy.created_at}")
                print(f"  Updated At: {policy.updated_at}")
        else:
            print("No policy configurations found in the database.")
        print("--- End Listing ---\n")
    except Exception as e:
        logging.exception(f"An error occurred: {e}")
    finally:
        # Only close if we think we successfully created it
        if pool_created:
            await close_main_db_pool()


if __name__ == "__main__":
    asyncio.run(main())
