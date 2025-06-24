#!/usr/bin/env python3
"""
Utility script to add/update the E2E test policy in the database.

This script creates or updates the 'e2e_db_test_policy' in the database
to match the configuration in e2e_policy.json.

Usage:
    poetry run python scripts/update_e2e_db_policy.py [--force]

Options:
    --force     Force replace even if the policy seems correct
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add the project root to the path so we can import luthien_control modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from luthien_control.db.control_policy_crud import (
    get_policy_config_by_name,
    update_policy,
)
from luthien_control.db.database_async import (
    close_db_engine,
    create_db_engine,
    get_db_session,
)
from luthien_control.db.exceptions import LuthienDBQueryError
from luthien_control.db.sqlmodel_models import ControlPolicy
from luthien_control.new_control_policy.add_api_key_header_from_env import AddApiKeyHeaderFromEnvPolicy
from luthien_control.new_control_policy.client_api_key_auth import ClientApiKeyAuthPolicy
from luthien_control.new_control_policy.leaked_api_key_detection import LeakedApiKeyDetectionPolicy
from luthien_control.new_control_policy.registry import POLICY_CLASS_TO_NAME
from luthien_control.new_control_policy.send_backend_request import SendBackendRequestPolicy
from luthien_control.new_control_policy.serial_policy import SerialPolicy
from luthien_control.new_control_policy.set_backend_policy import SetBackendPolicy
from sqlalchemy.exc import IntegrityError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

E2E_DB_POLICY_NAME = "e2e_db_test_policy"


def get_target_policy_config() -> dict:
    """Get the target policy configuration that matches e2e_policy.json."""
    return {
        "policies": [
            {
                "type": POLICY_CLASS_TO_NAME[ClientApiKeyAuthPolicy],
                "config": {"name": "E2E_ClientAPIKeyCheck"},
            },
            {
                "type": POLICY_CLASS_TO_NAME[LeakedApiKeyDetectionPolicy],
                "config": {"name": "E2E_LeakedKeyCheck"},
            },
            {
                "type": POLICY_CLASS_TO_NAME[AddApiKeyHeaderFromEnvPolicy],
                "config": {"name": "E2E_AddBackendKey", "api_key_env_var_name": "OPENAI_API_KEY"},
            },
            {
                "type": POLICY_CLASS_TO_NAME[SetBackendPolicy],
                "config": {"name": "E2E_SetBackend", "backend_url": "https://api.openai.com/v1/"},
            },
            {
                "type": POLICY_CLASS_TO_NAME[SendBackendRequestPolicy],
                "config": {"name": "E2E_ForwardRequest"},
            },
        ]
    }


async def update_e2e_db_policy(force_replace: bool = False):
    """Create or update the E2E test policy in the database."""
    engine_created = False
    logger.info(f"Starting update of E2E policy '{E2E_DB_POLICY_NAME}' in database...")

    try:
        # Create the database engine
        engine = await create_db_engine()
        if not engine:
            raise RuntimeError("Failed to create database engine.")
        engine_created = True
        logger.info("Database engine created successfully.")

        async with get_db_session() as session:
            # Try to get existing policy
            try:
                existing_policy = await get_policy_config_by_name(session, E2E_DB_POLICY_NAME)
                logger.info(f"Found existing policy '{E2E_DB_POLICY_NAME}' (ID: {existing_policy.id})")
            except LuthienDBQueryError:
                logger.info(f"Policy '{E2E_DB_POLICY_NAME}' not found. Will create new policy.")
                existing_policy = None

            # Define the target configuration
            target_config = get_target_policy_config()
            target_description = (
                "E2E DB Test Policy: Client auth -> Leaked key check -> "
                "Adds backend key -> Sets backend -> Sends request."
            )

            if existing_policy:
                # Check if policy has legacy content
                has_legacy_content = False
                if isinstance(existing_policy.config, dict) and "policies" in existing_policy.config:
                    for sub_policy in existing_policy.config["policies"]:
                        policy_type = sub_policy.get("type", "")
                        if policy_type == "TxLoggingPolicy":
                            has_legacy_content = True
                            logger.warning("🚨 Found legacy TxLoggingPolicy in existing policy!")
                            break

                if has_legacy_content or force_replace:
                    logger.info("🔄 Force replacing policy due to legacy content or --force flag")

                    # Delete existing policy by setting it inactive and creating a new one
                    logger.info("Marking old policy as inactive...")
                    update_data_inactive = ControlPolicy(
                        id=existing_policy.id,
                        name=f"{existing_policy.name}_old",  # Rename to avoid conflicts
                        type=existing_policy.type,
                        config=existing_policy.config,
                        is_active=False,
                        description=f"[REPLACED] {existing_policy.description}",
                        created_at=existing_policy.created_at,
                    )

                    assert existing_policy.id is not None
                    await update_policy(session, existing_policy.id, update_data_inactive)
                    logger.info("Old policy marked as inactive and renamed.")

                    # Now create new policy
                    existing_policy = None  # Force creation path
                else:
                    # Update existing policy normally
                    logger.info("Updating existing policy...")
                    logger.info(f"Current config: {existing_policy.config}")
                    logger.info(f"Target config: {target_config}")

                    update_data = ControlPolicy(
                        id=existing_policy.id,
                        name=existing_policy.name,
                        type=POLICY_CLASS_TO_NAME[SerialPolicy],  # Ensure correct type
                        config=target_config,
                        is_active=True,
                        description=target_description,
                        created_at=existing_policy.created_at,
                    )

                    assert existing_policy.id is not None  # Ensure ID is not None before update
                    updated_policy = await update_policy(session, existing_policy.id, update_data)
                    if updated_policy:
                        logger.info(f"✅ Successfully updated policy '{E2E_DB_POLICY_NAME}' (ID: {updated_policy.id})")
                        logger.info(f"New description: {updated_policy.description}")
                        logger.info(f"Active status: {updated_policy.is_active}")
                        logger.info(f"Type: {updated_policy.type}")
                    else:
                        logger.error(f"❌ Failed to update policy '{E2E_DB_POLICY_NAME}'")
                        return False

            if not existing_policy:  # Create new policy (either didn't exist or was force replaced)
                # Create new policy
                logger.info("Creating new policy...")
                policy_to_create = ControlPolicy(
                    name=E2E_DB_POLICY_NAME,
                    config=target_config,
                    type=POLICY_CLASS_TO_NAME[SerialPolicy],
                    is_active=True,
                    description=target_description,
                )

                session.add(policy_to_create)
                try:
                    await session.commit()
                    await session.refresh(policy_to_create)
                    logger.info(f"✅ Successfully created policy '{E2E_DB_POLICY_NAME}' (ID: {policy_to_create.id})")
                    logger.info(f"Description: {policy_to_create.description}")
                    logger.info(f"Type: {policy_to_create.type}")
                    logger.info(f"Active: {policy_to_create.is_active}")
                except IntegrityError as ie:
                    logger.error(f"❌ IntegrityError creating policy: {ie}")
                    await session.rollback()
                    return False
                except Exception as e:
                    logger.error(f"❌ Unexpected error creating policy: {e}")
                    await session.rollback()
                    return False

        logger.info("✅ Policy update completed successfully!")
        return True

    except Exception as e:
        logger.exception(f"❌ Error updating E2E policy: {e}")
        return False
    finally:
        if engine_created:
            await close_db_engine()
            logger.info("Database engine closed.")


async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Update E2E DB Policy")
    parser.add_argument("--force", action="store_true", help="Force replace even if policy seems correct")
    args = parser.parse_args()

    logger.info("E2E DB Policy Update Utility")
    logger.info("=" * 50)

    if args.force:
        logger.info("🔄 Force mode enabled - will replace existing policy")

    success = await update_e2e_db_policy(force_replace=args.force)

    if success:
        logger.info("✅ Policy update completed successfully!")
        logger.info(f"The policy '{E2E_DB_POLICY_NAME}' is now ready for E2E testing.")
        sys.exit(0)
    else:
        logger.error("❌ Policy update failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
