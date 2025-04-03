import json
import logging
from typing import Any, Dict, Optional

import asyncpg
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Global variable to hold the connection pool
# Ideally, this would be managed within an application context (e.g., FastAPI lifespan)
_db_pool: Optional[asyncpg.Pool] = None


class DBSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    db_user: str = "user"
    db_password: str = "password"
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "luthien_log_db"
    db_pool_min_size: int = 1
    db_pool_max_size: int = 10

    @property
    def dsn(self) -> str:
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"


async def create_db_pool(settings: Optional[DBSettings] = None) -> None:
    """Creates the asyncpg connection pool."""
    global _db_pool
    if _db_pool:
        logger.warning("Database pool already initialized.")
        return

    if settings is None:
        settings = DBSettings()

    try:
        _db_pool = await asyncpg.create_pool(
            dsn=settings.dsn,
            min_size=settings.db_pool_min_size,
            max_size=settings.db_pool_max_size,
        )
        logger.info("Database connection pool created successfully.")
    except Exception as e:
        logger.exception(f"Failed to create database connection pool: {e}")
        # Depending on application structure, might want to raise or exit
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
