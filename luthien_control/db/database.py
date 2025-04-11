import json
import logging
import os
from typing import Any, Dict, Optional
from urllib.parse import urlparse, urlunparse

import asyncpg
from dotenv import load_dotenv

# Load .env file variables into environment
load_dotenv(verbose=True)

logger = logging.getLogger(__name__)

# --- Global Variables for Connection Pools --- #
# Ideally, these would be managed within an application context (e.g., FastAPI lifespan)
_log_db_pool: Optional[asyncpg.Pool] = None
_main_db_pool: Optional[asyncpg.Pool] = None


# --- Helper Function for Main DB DSN --- #
def _get_main_db_dsn() -> Optional[str]:
    """Determines the main database DSN, prioritizing DATABASE_URL."""
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        logger.info("Using DATABASE_URL for main database connection.")
        return database_url

    logger.warning("DATABASE_URL not found. Falling back to individual POSTGRES_* variables.")
    db_user = os.getenv("POSTGRES_USER")
    db_password = os.getenv("POSTGRES_PASSWORD")
    db_host = os.getenv("POSTGRES_HOST")
    db_port = os.getenv("POSTGRES_PORT", "5432")  # Default port
    db_name = os.getenv("POSTGRES_DB")

    if not all([db_user, db_password, db_host, db_name]):
        logger.error(
            "Missing one or more required POSTGRES_* environment variables "
            "(POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_DB) "
            "when DATABASE_URL is not set."
        )
        return None

    dsn = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    logger.info(
        f"Constructed main database DSN from individual variables: postgresql://{db_user}:***@{db_host}:{db_port}/{db_name}"
    )
    return dsn


# --- Modified Helper Function for Pool Creation --- #
async def _create_pool_internal(
    min_size_env: str,
    max_size_env: str,
    pool_desc: str,  # Description for logging (e.g., "logging", "main")
) -> Optional[asyncpg.Pool]:
    """Internal helper to create an asyncpg connection pool using a DSN and pool size env vars."""

    dsn: Optional[str] = None
    if pool_desc == "main":
        dsn = _get_main_db_dsn()
    elif pool_desc == "logging":
        # TODO: Implement similar DSN logic for logging DB if needed, or keep separate vars
        # For now, assume logging DB still uses individual vars (or needs update)
        logger.warning("_create_pool_internal called for logging DB, DSN logic not implemented yet.")
        # Placeholder: attempt to build from specific log vars if needed
        log_db_user = os.getenv("LOG_DB_USER")
        log_db_password = os.getenv("LOG_DB_PASSWORD")
        log_db_host = os.getenv("LOG_DB_HOST")
        log_db_port = os.getenv("LOG_DB_PORT", "5432")
        log_db_name = os.getenv("LOG_DB_NAME")
        if all([log_db_user, log_db_password, log_db_host, log_db_name]):
            dsn = f"postgresql://{log_db_user}:{log_db_password}@{log_db_host}:{log_db_port}/{log_db_name}"
        else:
            # Log the specific messages expected by the test
            logger.error(f"Configuration error for {pool_desc} database pool")
            logger.error(f"Missing essential {pool_desc} database connection environment variables")
            return None
    else:
        logger.error(f"Unknown pool description: {pool_desc}")
        return None

    if not dsn:
        # Log the specific messages expected by the test when DSN couldn't be determined (likely missing vars)
        logger.error(f"Configuration error for {pool_desc} database pool")
        logger.error(f"Missing essential {pool_desc} database connection environment variables")
        return None

    try:
        # Get and validate pool sizes
        pool_min_size_str = os.getenv(min_size_env, "1")
        pool_max_size_str = os.getenv(max_size_env, "10")
        if not pool_min_size_str:
            pool_min_size_str = "1"
        if not pool_max_size_str:
            pool_max_size_str = "10"

        try:
            pool_min_size = int(pool_min_size_str)
        except ValueError:
            raise ValueError(f"Invalid {min_size_env}: '{pool_min_size_str}' is not an integer.")
        try:
            pool_max_size = int(pool_max_size_str)
        except ValueError:
            raise ValueError(f"Invalid {max_size_env}: '{pool_max_size_str}' is not an integer.")

    except ValueError as e:
        logger.error(f"Configuration error for {pool_desc} database pool sizes: {e}")
        return None

    try:
        # Create pool using the determined DSN
        pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=pool_min_size,
            max_size=pool_max_size,
        )
        logger.info(f"{pool_desc.capitalize()} database connection pool created successfully using DSN.")
        return pool
    except Exception as e:
        # Log the actual DSN used, masking password if possible
        masked_dsn = dsn

        parsed = urlparse(dsn)
        if parsed.password:
            masked_dsn = urlunparse(parsed._replace(netloc=f"{parsed.username}:***@{parsed.hostname}:{parsed.port}"))
        logger.exception(f"Failed to create {pool_desc} database connection pool using DSN ({masked_dsn}): {e}")
        return None


# --- Logging DB Pool Management (Needs review based on DSN logic) --- #
async def create_log_db_pool() -> None:
    """Creates the asyncpg connection pool using environment variables for the logging DB."""
    global _log_db_pool
    if _log_db_pool:
        logger.warning("Logging database pool already initialized.")
        return

    logger.info("Attempting to create logging database pool...")
    # Call the internal creator with only pool size env vars
    _log_db_pool = await _create_pool_internal(
        min_size_env="LOG_DB_POOL_MIN_SIZE",
        max_size_env="LOG_DB_POOL_MAX_SIZE",
        pool_desc="logging",
    )
    # Add direct check
    if _log_db_pool:
        logger.info("DIRECT CHECK (Log DB): _log_db_pool is SET after call.")
    else:
        logger.error("DIRECT CHECK (Log DB): _log_db_pool is NONE after call. Pool creation likely failed.")


async def close_log_db_pool() -> None:
    """Closes the logging database asyncpg connection pool."""
    global _log_db_pool
    if _log_db_pool:
        await _log_db_pool.close()
        _log_db_pool = None
        logger.info("Logging database connection pool closed.")


def get_log_db_pool() -> asyncpg.Pool:
    """Returns the existing logging database pool. Raises Exception if not initialized."""
    if _log_db_pool is None:
        logger.error("Logging database pool accessed before initialization.")
        raise RuntimeError("Logging database pool has not been initialized.")
    return _log_db_pool


# --- Main DB Pool Management (Updated) --- #
async def create_main_db_pool() -> None:
    """Creates the asyncpg connection pool using DSN logic for the main application DB."""
    global _main_db_pool
    if _main_db_pool:
        logger.warning("Main database pool already initialized.")
        return

    logger.info("Attempting to create main database pool using DSN logic...")
    # Call the internal creator with only pool size env vars
    _main_db_pool = await _create_pool_internal(
        min_size_env="MAIN_DB_POOL_MIN_SIZE",
        max_size_env="MAIN_DB_POOL_MAX_SIZE",
        pool_desc="main",
    )
    # Direct check remains useful here
    if _main_db_pool:
        logger.info("DIRECT CHECK (Main DB): _main_db_pool is SET after call.")
    else:
        logger.error("DIRECT CHECK (Main DB): _main_db_pool is NONE after call. Pool creation likely failed.")


async def close_main_db_pool() -> None:
    """Closes the main database asyncpg connection pool."""
    global _main_db_pool
    if _main_db_pool:
        await _main_db_pool.close()
        _main_db_pool = None
        logger.info("Main database connection pool closed.")


def get_main_db_pool() -> asyncpg.Pool:
    """Returns the existing main database pool. Raises Exception if not initialized."""
    if _main_db_pool is None:
        logger.error("Main database pool accessed before initialization.")
        raise RuntimeError("Main database pool has not been initialized.")
    return _main_db_pool


# --- Database Operations --- #


async def log_request_response(
    request_data: Dict[str, Any],
    response_data: Dict[str, Any],
    client_ip: Optional[str] = None,
) -> None:
    """
    Logs request and response data to the logging database.
    Uses get_log_db_pool() to acquire the connection pool.

    Args:
        request_data: Dictionary containing request details.
        response_data: Dictionary containing response details.
        client_ip: The IP address of the client.
    """
    try:
        pool = get_log_db_pool()  # Get the pool using the getter
    except RuntimeError:
        logger.error("Cannot log request/response: Logging database pool not initialized.")
        return

    sql = """
        INSERT INTO request_log (
            client_ip, request_method, request_url, request_headers, request_body,
            response_status_code, response_headers, response_body, processing_time_ms
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
    """
    try:
        request_headers_json = json.dumps(request_data.get("headers"))
        response_headers_json = json.dumps(response_data.get("headers"))

        params = (
            client_ip,
            request_data.get("method"),
            str(request_data.get("url")),  # Ensure URL is string
            request_headers_json,
            request_data.get("body"),
            response_data.get("status_code"),
            response_headers_json,
            response_data.get("body"),
            request_data.get("processing_time_ms"),
        )

        async with pool.acquire() as conn:
            await conn.execute(sql, *params)
        # logger.debug(f"Successfully logged request for {request_data.get('url')}")
    except Exception as e:
        url_info = request_data.get("url", "[URL not available]")
        logger.exception(f"Failed to log request/response to database for {url_info}: {e}")
        # Suppress to avoid breaking the main flow.
