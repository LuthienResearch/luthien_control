#!/usr/bin/env python3
"""
Show the current active policy that would be loaded by the application.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add the project root to the path so we can import luthien_control modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from luthien_control.db.database_async import close_db_engine, create_db_engine, get_db_session
from luthien_control.db.sqlmodel_models import ControlPolicy
from luthien_control.settings import Settings
from sqlalchemy import select

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def show_current_policy():
    """Show the currently active policy based on environment settings."""
    load_dotenv()
    settings = Settings()

    policy_name = settings.get_top_level_policy_name()
    logger.info(f"Looking for policy with name: '{policy_name}'")

    try:
        engine = await create_db_engine()
        if not engine:
            logger.error("Failed to create database engine.")
            return

        async with get_db_session() as session:
            # Get the active policy with the specified name
            stmt = select(ControlPolicy).where(ControlPolicy.name == policy_name, ControlPolicy.is_active is True)
            result = await session.execute(stmt)
            policy = result.scalar_one_or_none()

            if not policy:
                logger.error(f"No active policy found with name '{policy_name}'")
                return

            logger.info("\n" + "=" * 60)
            logger.info(f"CURRENT ACTIVE POLICY: {policy.name}")
            logger.info("=" * 60)
            logger.info(f"ID: {policy.id}")
            logger.info(f"Type: {policy.type}")
            logger.info(f"Description: {policy.description}")
            logger.info(f"Created: {policy.created_at}")
            logger.info(f"Updated: {policy.updated_at}")
            logger.info("\nFull Configuration:")
            logger.info("-" * 40)
            print(json.dumps(policy.config, indent=2))

    except Exception as e:
        logger.exception(f"Error loading policy: {e}")
    finally:
        await close_db_engine()


if __name__ == "__main__":
    asyncio.run(show_current_policy())
