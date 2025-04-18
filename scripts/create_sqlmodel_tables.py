#!/usr/bin/env python3
"""
Script to initialize the new SQLModel database tables.
This is a manual alternative to using Alembic, useful for testing.
"""

import asyncio
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv
from luthien_control.db.database_async import close_main_db_engine, create_main_db_engine
from sqlmodel import SQLModel

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def create_tables():
    """Create all tables defined in SQLModel models."""
    # Load environment variables
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        load_dotenv(dotenv_path=env_file)
        logger.info(f"Loaded environment variables from {env_file}")
    else:
        logger.warning(f".env file not found at {env_file}, using system environment variables")

    # Create engine
    engine = await create_main_db_engine()
    if not engine:
        logger.error("Failed to create database engine. Check your environment variables.")
        return False

    try:
        # Create tables
        async with engine.begin() as conn:
            # Import SQLModel models to ensure they're in the metadata
            logger.info("Creating tables from SQLModel definitions...")
            await conn.run_sync(SQLModel.metadata.create_all)

        logger.info("Tables created successfully!")
        return True
    except Exception as e:
        logger.error(f"Error creating tables: {e}")
        return False
    finally:
        # Close the engine
        await close_main_db_engine()


if __name__ == "__main__":
    success = asyncio.run(create_tables())
    sys.exit(0 if success else 1)
