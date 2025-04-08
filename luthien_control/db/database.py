import json
import logging
import os
from typing import Any, Dict, Optional

import asyncpg
from dotenv import load_dotenv

# Load .env file variables into environment
load_dotenv(verbose=True)

logger = logging.getLogger(__name__)

# Global variable to hold the connection pool
# Ideally, this would be managed within an application context (e.g., FastAPI lifespan)
_db_pool: Optional[asyncpg.Pool] = None


async def create_db_pool() -> None:
    """Creates the asyncpg connection pool using environment variables for logging DB."""
    global _db_pool
    if _db_pool:
        logger.warning("Database pool already initialized.")
        return

    # Fetch settings from environment variables, using defaults from old DBSettings
    try:
        db_user = os.getenv("LOG_DB_USER", "user")
        db_password = os.getenv("LOG_DB_PASSWORD", "password")
        db_host = os.getenv("LOG_DB_HOST", "localhost")
        db_port_str = os.getenv("LOG_DB_PORT", "5432")
        db_name = os.getenv("LOG_DB_NAME", "luthien_log_db")
        pool_min_size_str = os.getenv("LOG_DB_POOL_MIN_SIZE", "1")
        pool_max_size_str = os.getenv("LOG_DB_POOL_MAX_SIZE", "10")

        # Validate and convert types
        try:
            db_port = int(db_port_str)
        except ValueError:
            raise ValueError(f"Invalid LOG_DB_PORT: '{db_port_str}' is not an integer.")
        try:
            pool_min_size = int(pool_min_size_str)
        except ValueError:
            raise ValueError(f"Invalid LOG_DB_POOL_MIN_SIZE: '{pool_min_size_str}' is not an integer.")
        try:
            pool_max_size = int(pool_max_size_str)
        except ValueError:
            raise ValueError(f"Invalid LOG_DB_POOL_MAX_SIZE: '{pool_max_size_str}' is not an integer.")

        # Basic check for essential connection details
        if not all([db_user, db_password, db_host, db_port, db_name]):
            raise ValueError(
                "Missing essential logging database connection environment variables "
                "(LOG_DB_USER, LOG_DB_PASSWORD, LOG_DB_HOST, LOG_DB_PORT, LOG_DB_NAME)"
            )

        dsn = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

    except ValueError as e:
        logger.exception(f"Configuration error for database pool: {e}")
        _db_pool = None
        return  # Do not proceed if config is invalid

    try:
        _db_pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=pool_min_size,
            max_size=pool_max_size,
        )
        logger.info(f"Database connection pool created successfully for {db_name}.")
    except Exception as e:
        logger.exception(f"Failed to create database connection pool: {e}")
        _db_pool = None  # Ensure pool is None if creation failed


async def close_db_pool() -> None:
    """Closes the asyncpg connection pool."""
    global _db_pool
    if _db_pool:
        await _db_pool.close()
        _db_pool = None
        logger.info("Database connection pool closed.")


def get_db_pool() -> asyncpg.Pool:
    """Returns the existing database pool. Raises Exception if not initialized."""
    if _db_pool is None:
        # This scenario should ideally be prevented by initializing the pool
        # during application startup (e.g., FastAPI lifespan event).
        logger.error("Database pool accessed before initialization.")
        raise RuntimeError("Database pool has not been initialized.")
    return _db_pool


async def log_request_response(
    pool: asyncpg.Pool,
    request_data: Dict[str, Any],
    response_data: Dict[str, Any],
    client_ip: Optional[str] = None,
) -> None:
    """
    Logs request and response data to the database.

    Args:
        pool: The asyncpg connection pool.
        request_data: Dictionary containing request details (method, url, headers, body, processing_time_ms).
        response_data: Dictionary containing response details (status_code, headers, body).
        client_ip: The IP address of the client making the request.
    """
    sql = """
        INSERT INTO request_log (
            client_ip, request_method, request_url, request_headers, request_body,
            response_status_code, response_headers, response_body, processing_time_ms
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
    """

    # Extract and prepare parameters, ensuring JSON fields are encoded
    request_headers_json = json.dumps(request_data.get("headers"))
    response_headers_json = json.dumps(response_data.get("headers"))

    params = (
        client_ip,
        request_data.get("method"),
        request_data.get("url"),
        request_headers_json,
        request_data.get("body"),  # Assuming body is already string/text
        response_data.get("status_code"),
        response_headers_json,
        response_data.get("body"),  # Assuming body is already string/text
        request_data.get("processing_time_ms"),
    )

    conn = None
    try:
        async with pool.acquire() as conn:
            await conn.execute(sql, *params)
        logger.debug(f"Successfully logged request for {request_data.get('url')}")
    except Exception as e:
        logger.exception(f"Failed to log request/response to database for {request_data.get('url')}: {e}")
        # Optionally re-raise or handle depending on desired application behavior
        # For now, we log and suppress to avoid breaking the main flow.

    # Note: `async with pool.acquire()` handles releasing the connection automatically,
    # even if errors occur within the block.
