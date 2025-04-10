import logging
from typing import Optional

from pydantic_core import ValidationError  # Added

from .database import get_main_db_pool
from .models import ApiKey

logger = logging.getLogger(__name__)


async def get_api_key_by_value(key_value: str) -> Optional[ApiKey]:
    """
    Fetches an API key record from the database based on the key value.

    Args:
        key_value: The API key string to look up.

    Returns:
        An ApiKey object if found. If metadata JSON is invalid, metadata will be None.
        Returns None if key not found, DB pool not initialized, or other DB error occurs.
    """
    try:
        pool = get_main_db_pool()
    except RuntimeError:
        logger.error("Cannot fetch API key: Main database pool not initialized.")
        return None

    sql = """
        SELECT id, key_value, name, is_active, created_at, metadata_
        FROM api_keys
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
                api_key = ApiKey(**record_dict)
                return api_key
            except ValidationError as ve:
                # Check if the ONLY error was related to metadata_ parsing
                is_only_metadata_error = False
                if len(ve.errors()) == 1:
                    error_details = ve.errors()[0]
                    if error_details.get("loc") == ("metadata_",) and error_details.get("type") == "json_invalid":
                        is_only_metadata_error = True

                if is_only_metadata_error:
                    logger.warning(
                        f"Invalid JSON in metadata for key ID {record_dict.get('id', '?')}. "
                        f"Returning ApiKey with metadata=None. Error: {ve.errors()[0].get('msg')}"
                    )
                    # Retry creating the model with metadata explicitly set to None
                    record_dict["metadata_"] = None
                    try:
                        api_key_no_meta = ApiKey(**record_dict)
                        return api_key_no_meta
                    except ValidationError as ve_retry:
                        # Should not happen if only metadata was the issue, but log if it does
                        logger.error(
                            f"Failed to create ApiKey even after clearing metadata for key ID "
                            f"{record_dict.get('id', '?')}. Validation Errors: {ve_retry.errors()}"
                        )
                        # Fall through to the main exception handler -> return None
                else:
                    # Validation error was not just metadata or there were multiple errors
                    logger.error(
                        f"Pydantic validation failed for key ID {record_dict.get('id', '?')} "
                        f"(not just metadata): {ve.errors()}"
                    )
                    # Fall through to the main exception handler -> return None

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
