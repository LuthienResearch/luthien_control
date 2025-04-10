import json
import logging
import os
from typing import Any, Dict, Optional

import asyncpg
from dotenv import load_dotenv

# Load .env file variables into environment
load_dotenv(verbose=True)

logger = logging.getLogger(__name__)

# --- Global Variables for Connection Pools --- #
# Ideally, these would be managed within an application context (e.g., FastAPI lifespan)
_log_db_pool: Optional[asyncpg.Pool] = None
_main_db_pool: Optional[asyncpg.Pool] = None


# --- Helper Function for Pool Creation --- #
async def _create_pool_internal(
    user_env: str,
    password_env: str,
    host_env: str,
    port_env: str,
    name_env: str,
    min_size_env: str,
    max_size_env: str,
    pool_desc: str,  # Description for logging (e.g., "logging", "main")
) -> Optional[asyncpg.Pool]:
    """Internal helper to create an asyncpg connection pool from environment variables."""
    try:
        db_user = os.getenv(user_env)
        db_password = os.getenv(password_env)
        db_host = os.getenv(host_env, "localhost")
        db_port_str = os.getenv(port_env, "5432")
        db_name = os.getenv(name_env)
        pool_min_size_str = os.getenv(min_size_env, "1")
        pool_max_size_str = os.getenv(max_size_env, "10")

        # Validate essential variables first
        if not all([db_user, db_password, db_host, db_name]):
            raise ValueError(
                f"Missing essential {pool_desc} database connection environment variables "
                f"({user_env}, {password_env}, {host_env}, {name_env})"
            )

        # Validate and convert types
        try:
            db_port = int(db_port_str)
        except ValueError:
            raise ValueError(f"Invalid {port_env}: '{db_port_str}' is not an integer.")
        try:
            pool_min_size = int(pool_min_size_str)
        except ValueError:
            raise ValueError(f"Invalid {min_size_env}: '{pool_min_size_str}' is not an integer.")
        try:
            pool_max_size = int(pool_max_size_str)
        except ValueError:
            raise ValueError(f"Invalid {max_size_env}: '{pool_max_size_str}' is not an integer.")

        dsn = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

    except ValueError as e:
        logger.error(f"Configuration error for {pool_desc} database pool: {e}")
        return None  # Do not proceed if config is invalid

    try:
        pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=pool_min_size,
            max_size=pool_max_size,
        )
        logger.info(
            f"{pool_desc.capitalize()} database connection pool created successfully for {db_name} @ {db_host}:{db_port}."
        )
        return pool
    except Exception as e:
        logger.exception(f"Failed to create {pool_desc} database connection pool: {e}")
        return None  # Ensure pool is None if creation failed


# --- Logging DB Pool Management --- #
async def create_log_db_pool() -> None:
    """Creates the asyncpg connection pool using environment variables for the logging DB."""
    global _log_db_pool
    if _log_db_pool:
        logger.warning("Logging database pool already initialized.")
        return

    _log_db_pool = await _create_pool_internal(
        user_env="LOG_DB_USER",
        password_env="LOG_DB_PASSWORD",
        host_env="LOG_DB_HOST",
        port_env="LOG_DB_PORT",
        name_env="LOG_DB_NAME",
        min_size_env="LOG_DB_POOL_MIN_SIZE",
        max_size_env="LOG_DB_POOL_MAX_SIZE",
        pool_desc="logging",
    )


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


# --- Main DB Pool Management --- #
async def create_main_db_pool() -> None:
    """Creates the asyncpg connection pool using environment variables for the main application DB."""
    global _main_db_pool
    if _main_db_pool:
        logger.warning("Main database pool already initialized.")
        return

    # Note: No default pool sizes specified for main DB in README, using same as log DB
    _main_db_pool = await _create_pool_internal(
        user_env="POSTGRES_USER",
        password_env="POSTGRES_PASSWORD",
        host_env="POSTGRES_HOST",
        port_env="POSTGRES_PORT",
        name_env="POSTGRES_DB",
        min_size_env="MAIN_DB_POOL_MIN_SIZE",  # Assuming these env vars might exist
        max_size_env="MAIN_DB_POOL_MAX_SIZE",  # Assuming these env vars might exist
        pool_desc="main",
    )


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
    # pool: asyncpg.Pool, # No longer needed as argument, use getter
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
