import asyncio
import logging
import os

import asyncpg
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(verbose=True)

logger = logging.getLogger(__name__)

# --- Database Configuration --- #
DB_USER = os.getenv("POSTGRES_USER", "default_user")  # Provide sensible defaults or raise errors
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "default_password")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "main_app_db")

DSN = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# --- SQL Statement to Create Table --- #
# Note: 'metadata_' column uses JSONB for efficiency and indexing capabilities in Postgres
# Note: 'key_value' has a UNIQUE constraint
CREATE_API_KEYS_TABLE = """
CREATE TABLE IF NOT EXISTS api_keys (
    id SERIAL PRIMARY KEY,
    key_value TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    metadata_ JSONB
);
"""

# --- Index Creation Statements --- #
# Index on key_value for faster lookups
CREATE_KEY_VALUE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_api_keys_key_value ON api_keys (key_value);
"""

# Index on name for searching by name
CREATE_NAME_INDEX = """
CREATE INDEX IF NOT EXISTS idx_api_keys_name ON api_keys (name);
"""


async def initialize_database():
    conn = None
    try:
        logger.info(f"Attempting to connect to database '{DB_NAME}' on {DB_HOST}:{DB_PORT}...")
        conn = await asyncpg.connect(DSN)
        logger.info("Database connection established successfully.")

        # Create the table
        logger.info("Creating table 'api_keys' if it doesn't exist...")
        await conn.execute(CREATE_API_KEYS_TABLE)
        logger.info("Table 'api_keys' checked/created.")

        # Create indexes
        logger.info("Creating index 'idx_api_keys_key_value' if it doesn't exist...")
        await conn.execute(CREATE_KEY_VALUE_INDEX)
        logger.info("Index 'idx_api_keys_key_value' checked/created.")

        logger.info("Creating index 'idx_api_keys_name' if it doesn't exist...")
        await conn.execute(CREATE_NAME_INDEX)
        logger.info("Index 'idx_api_keys_name' checked/created.")

        logger.info("Database initialization complete.")

    except Exception as e:
        logger.exception(f"Database initialization failed: {e}")
    finally:
        if conn:
            await conn.close()
            logger.info("Database connection closed.")


if __name__ == "__main__":
    # Check if essential variables are set
    if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME]):
        logger.error(
            "Missing essential database connection environment variables "
            "(POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB). "
            "Cannot initialize database."
        )
    else:
        asyncio.run(initialize_database())
