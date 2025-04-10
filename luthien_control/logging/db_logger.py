import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

import asyncpg
from luthien_control.db.database import get_log_db_pool

logger = logging.getLogger(__name__)


async def log_db_entry(
    data: Dict[str, Any],
    client_ip: Optional[str] = None,
    log_level: str = "INFO",
    message: str = "Generic log entry",
) -> None:
    """
    Logs a dictionary entry to the logging database using a connection pool.

    Args:
        data: The dictionary data to log (will be JSON serialized).
        client_ip: The client's IP address, if available.
        log_level: The log level (e.g., INFO, WARN, ERROR).
        message: A descriptive message for the log entry.
    """
    try:
        pool = get_log_db_pool()
    except RuntimeError as e:
        # Log the error and return if the pool isn't ready.
        logger.error(f"Cannot log DB entry: Logging database pool not initialized. {e}")
        return

    sql = """
        INSERT INTO logs (client_ip, log_level, message, data, timestamp)
        VALUES ($1, $2, $3, $4, $5)
    """
    try:
        data_json = json.dumps(data)
        timestamp = datetime.utcnow()

        params = (client_ip, log_level, message, data_json, timestamp)

        # Acquire a connection from the pool and execute
        async with pool.acquire() as conn:
            await conn.execute(sql, *params)
        # logger.debug(f"Successfully logged entry: {message}")

    except Exception as e:
        # Log any other exceptions during DB operation but don't crash the app
        logger.exception(f"Failed to log entry to database: {message}. Error: {e}")
