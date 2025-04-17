import logging
from typing import Optional

from pydantic import ValidationError

from .database import get_main_db_pool
from .models import TABLE_NAME_MAP, ClientApiKey

logger = logging.getLogger(__name__)


async def get_api_key_by_value(key_value: str) -> Optional[ClientApiKey]:
    """
    Fetches an API key record from the database based on the key value.

    Args:
        key_value: The API key string to look up.

    Returns:
        An ClientApiKey object if found. If metadata JSON is invalid, metadata will be None.
        Returns None if key not found, DB pool not initialized, or other DB error occurs.
    """
    try:
        pool = get_main_db_pool()
    except RuntimeError:
        logger.error("Cannot fetch API key: Main database pool not initialized.")
        return None

    # Get table name from the central mapping
    table_name = TABLE_NAME_MAP.get(ClientApiKey)
    if not table_name:
        # This should ideally not happen if the map is maintained
        logger.critical("CRITICAL: Table name for ClientApiKey not found in TABLE_NAME_MAP. Cannot proceed.")
        # Depending on desired robustness, could default or raise an exception
        # For now, let's prevent execution with a missing mapping
        return None  # Or raise an error

    # Use an f-string to insert the table name. This is safe as the table name
    # comes from our defined mapping, not external input.
    # Parameterization ($1) is still used for the actual key_value, preventing SQL injection.
    sql = f"""
        SELECT id, key_value, name, is_active, created_at, metadata_
        FROM {table_name}
        WHERE key_value = $1
    """

    record = None
    try:
        async with pool.acquire() as conn:
            record = await conn.fetchrow(sql, key_value)

        if record:
            logger.debug(f"Found API key record for key starting with: {key_value[:4]}...")
            record_dict = dict(record)

            # Ensure metadata_ is None or a string before potential Pydantic validation
            if "metadata_" in record_dict and not isinstance(record_dict["metadata_"], (str, type(None))):
                logger.warning(
                    f"Unexpected type for metadata_ from DB: {type(record_dict['metadata_'])}. "
                    f"Expected string or None. Setting to None before validation."
                )
                record_dict["metadata_"] = None

            try:
                # Attempt to create the model
                api_key = ClientApiKey(**record_dict)
                return api_key
            except ValidationError as ve:
                # Log a warning if metadata JSON is invalid
                if "metadata_" in record_dict and record_dict["metadata_"] is not None:
                    logger.warning(
                        f"Invalid JSON in metadata for key ID {record_dict.get('id', '?')}. "
                        f"Returning ClientApiKey with metadata=None. Error: {ve.errors()[0].get('msg')}"
                    )
                    # Retry creating the model with metadata explicitly set to None
                    record_dict["metadata_"] = None
                    try:
                        api_key_no_meta = ClientApiKey(**record_dict)
                        return api_key_no_meta
                    except ValidationError as ve_retry:
                        # Should not happen if only metadata was the issue, but log if it does
                        logger.error(
                            f"Failed to create ClientApiKey even after clearing metadata for key ID "
                            f"{record_dict.get('id', '?')}. Validation Errors: {ve_retry.errors()}"
                        )
                        return None  # Or re-raise, depending on desired behavior
                else:
                    # Validation error wasn't due to metadata
                    logger.error(
                        f"Pydantic validation error for API key ID {record_dict.get('id', '?')} "
                        f"(not metadata related): {ve.errors()}"
                    )
                    return None

        else:
            logger.debug(f"No API key record found for key starting with: {key_value[:4]}...")
            return None  # Key not found

    except Exception as e:
        # Catch other database errors or unexpected issues during processing
        if isinstance(e, ValidationError):
            # If we reached here from the ValidationError blocks above, log was already specific
            pass  # Already logged sufficiently
        else:
            logger.exception(f"Database error fetching API key for key starting with {key_value[:4]}...: {e}")
        return None
