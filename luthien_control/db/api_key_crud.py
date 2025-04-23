"""CRUD operations specific to ClientApiKey model."""

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .sqlmodel_models import ClientApiKey

logger = logging.getLogger(__name__)


async def get_api_key_by_value(session: AsyncSession, key_value: str) -> Optional[ClientApiKey]:
    """Get an active API key by its value."""
    if not isinstance(session, AsyncSession):
        # This check might be better handled by type hinting/DI framework upstream
        logger.error("Invalid session object type passed to get_api_key_by_value")
        raise TypeError("Invalid session object provided to get_api_key_by_value.")
    try:
        stmt = select(ClientApiKey).where(
            ClientApiKey.key_value == key_value,
            ClientApiKey.is_active == True,  # noqa: E712 - Explicit comparison is often clearer
        )
        result = await session.execute(stmt)
        api_key = result.scalar_one_or_none()
        # logger.debug(f"API key lookup for value ending '...{key_value[-4:]}': {'Found' if api_key else 'Not Found'}")
        return api_key
    except Exception as e:
        # Avoid logging the key_value directly in case of errors if it's sensitive
        logger.error(f"Error fetching API key by value: {e}", exc_info=True)
        # Depending on policy, might want to raise exception instead of returning None
        return None
