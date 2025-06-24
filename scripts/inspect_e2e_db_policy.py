#!/usr/bin/env python3
"""
Utility script to inspect the current E2E test policy in the database.

This script shows the current configuration of 'e2e_db_test_policy'
to help debug policy loading issues.

Usage:
    poetry run python scripts/inspect_e2e_db_policy.py
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add the project root to the path so we can import luthien_control modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from luthien_control.db.control_policy_crud import get_policy_config_by_name
from luthien_control.db.database_async import close_db_engine, create_db_engine, get_db_session
from luthien_control.db.exceptions import LuthienDBQueryError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

E2E_DB_POLICY_NAME = "e2e_db_test_policy"


async def inspect_e2e_db_policy():
    """Inspect the current E2E test policy in the database."""
    engine_created = False
    logger.info(f"Inspecting E2E policy '{E2E_DB_POLICY_NAME}' in database...")

    try:
        # Create the database engine
        engine = await create_db_engine()
        if not engine:
            raise RuntimeError("Failed to create database engine.")
        engine_created = True
        logger.info("Database engine created successfully.")

        async with get_db_session() as session:
            try:
                policy = await get_policy_config_by_name(session, E2E_DB_POLICY_NAME)
                logger.info(f"✅ Found policy '{E2E_DB_POLICY_NAME}'")
                logger.info("=" * 60)
                logger.info(f"ID: {policy.id}")
                logger.info(f"Name: {policy.name}")
                logger.info(f"Type: {policy.type}")
                logger.info(f"Active: {policy.is_active}")
                logger.info(f"Description: {policy.description}")
                logger.info(f"Created: {policy.created_at}")
                logger.info(f"Updated: {policy.updated_at}")
                logger.info("=" * 60)
                logger.info("Configuration:")
                logger.info(json.dumps(policy.config, indent=2))
                logger.info("=" * 60)

                # Check for legacy policy types
                if isinstance(policy.config, dict) and "policies" in policy.config:
                    logger.info("Checking for legacy policy types...")
                    for i, sub_policy in enumerate(policy.config["policies"]):
                        policy_type = sub_policy.get("type", "unknown")
                        policy_name = sub_policy.get("config", {}).get("name", "unknown")
                        logger.info(f"  [{i}] Type: {policy_type}, Name: {policy_name}")

                        if policy_type == "TxLoggingPolicy":
                            logger.warning(f"  ⚠️  Found legacy TxLoggingPolicy at index {i}")
                        elif policy_type not in [
                            "ClientApiKeyAuth",
                            "LeakedApiKeyDetection",
                            "AddApiKeyHeaderFromEnv",
                            "SetBackendPolicy",
                            "SendBackendRequest",
                        ]:
                            logger.warning(f"  ⚠️  Unexpected policy type: {policy_type}")

                return True

            except LuthienDBQueryError:
                logger.warning(f"❌ Policy '{E2E_DB_POLICY_NAME}' not found in database")
                return False

    except Exception as e:
        logger.exception(f"❌ Error inspecting policy: {e}")
        return False
    finally:
        if engine_created:
            await close_db_engine()
            logger.info("Database engine closed.")


async def main():
    """Main function."""
    logger.info("E2E DB Policy Inspector")
    logger.info("=" * 50)

    success = await inspect_e2e_db_policy()

    if success:
        logger.info("✅ Inspection completed successfully!")
    else:
        logger.error("❌ Inspection failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
