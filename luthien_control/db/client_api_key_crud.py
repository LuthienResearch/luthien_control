# CRUD operations specific to ClientApiKey model.

import logging
from typing import List, Optional

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


# --- ClientApiKey CRUD Operations ---


async def create_api_key(session: AsyncSession, api_key: ClientApiKey) -> Optional[ClientApiKey]:
    """Create a new API key in the database."""
    try:
        session.add(api_key)
        await session.commit()
        await session.refresh(api_key)
        logger.info(f"Successfully created API key with ID: {api_key.id}")
        return api_key
    except Exception as e:
        await session.rollback()
        logger.error(f"Error creating API key: {e}")
        return None


async def list_api_keys(session: AsyncSession, active_only: bool = False) -> List[ClientApiKey]:
    """Get a list of all API keys."""
    try:
        if active_only:
            stmt = select(ClientApiKey).where(ClientApiKey.is_active == True)  # noqa: E712
        else:
            stmt = select(ClientApiKey)

        result = await session.execute(stmt)
        return list(result.scalars().all())
    except Exception as e:
        logger.error(f"Error listing API keys: {e}")
        return []


async def update_api_key(session: AsyncSession, key_id: int, api_key_update: ClientApiKey) -> Optional[ClientApiKey]:
    """Update an existing API key."""
    try:
        stmt = select(ClientApiKey).where(ClientApiKey.id == key_id)
        result = await session.execute(stmt)
        api_key = result.scalar_one_or_none()

        if not api_key:
            logger.warning(f"API key with ID {key_id} not found")
            return None

        # Update fields
        api_key.name = api_key_update.name
        api_key.is_active = api_key_update.is_active
        api_key.metadata_ = api_key_update.metadata_

        await session.commit()
        await session.refresh(api_key)
        logger.info(f"Successfully updated API key with ID: {api_key.id}")
        return api_key
    except Exception as e:
        await session.rollback()
        logger.error(f"Error updating API key: {e}")
        return None
