# CRUD operations specific to ClientApiKey model.

import logging
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.db.exceptions import (
    LuthienDBIntegrityError,
    LuthienDBOperationError,
    LuthienDBQueryError,
    LuthienDBTransactionError,
)
from .sqlmodel_models import ClientApiKey

logger = logging.getLogger(__name__)


async def get_api_key_by_value(session: AsyncSession, key_value: str) -> Optional[ClientApiKey]:
    """Get an active API key by its value.

    Args:
        session: The database session
        key_value: The value of the API key to retrieve

    Returns:
        The API key if found, None otherwise

    Raises:
        TypeError: If the session is not an AsyncSession
        LuthienDBQueryError: If the query execution fails
    """
    if not isinstance(session, AsyncSession):
        # This check might be better handled by type hinting/DI framework upstream
        logger.error("Invalid session object type passed to get_api_key_by_value")
        raise TypeError("Invalid session object provided to get_api_key_by_value.")
    try:
        stmt = select(ClientApiKey).where(
            ClientApiKey.key_value == key_value,  # type: ignore[arg-type]
            ClientApiKey.is_active,  # type: ignore[arg-type]
        )
        result = await session.execute(stmt)
        api_key = result.scalar_one_or_none()
        # logger.debug(f"API key lookup for value ending '...{key_value[-4:]}': {'Found' if api_key else 'Not Found'}")
        return api_key
    except SQLAlchemyError as sqla_err:
        # Avoid logging the key_value directly in case of errors if it's sensitive
        logger.error(f"SQLAlchemy error fetching API key by value: {sqla_err}", exc_info=True)
        raise LuthienDBQueryError(f"Database query failed while fetching API key: {sqla_err}") from sqla_err
    except Exception as e:
        logger.error(f"Unexpected error fetching API key by value: {e}", exc_info=True)
        raise LuthienDBOperationError(f"Unexpected error during API key lookup: {e}") from e


# --- ClientApiKey CRUD Operations ---


async def create_api_key(session: AsyncSession, api_key: ClientApiKey) -> ClientApiKey:
    """Create a new API key in the database.

    Args:
        session: The database session
        api_key: The API key to create

    Returns:
        The created API key with updated ID

    Raises:
        LuthienDBIntegrityError: If a constraint violation occurs
        LuthienDBTransactionError: If the transaction fails
        LuthienDBOperationError: For other database errors
    """
    try:
        session.add(api_key)
        await session.commit()
        await session.refresh(api_key)
        logger.info(f"Successfully created API key with ID: {api_key.id}")
        return api_key
    except IntegrityError as ie:
        await session.rollback()
        logger.error(f"Integrity error creating API key: {ie}")
        raise LuthienDBIntegrityError(f"Could not create API key due to constraint violation: {ie}", ie) from ie
    except SQLAlchemyError as sqla_err:
        await session.rollback()
        logger.error(f"SQLAlchemy error creating API key: {sqla_err}")
        raise LuthienDBTransactionError(f"Database transaction failed while creating API key: {sqla_err}") from sqla_err
    except Exception as e:
        await session.rollback()
        logger.error(f"Unexpected error creating API key: {e}")
        raise LuthienDBOperationError(f"Unexpected error during API key creation: {e}") from e


async def list_api_keys(session: AsyncSession, active_only: bool = False) -> List[ClientApiKey]:
    """Get a list of all API keys.

    Args:
        session: The database session
        active_only: If True, only return active API keys

    Returns:
        A list of API keys

    Raises:
        LuthienDBQueryError: If the query execution fails
    """
    try:
        if active_only:
            stmt = select(ClientApiKey).where(ClientApiKey.is_active)  # type: ignore[arg-type]
        else:
            stmt = select(ClientApiKey)

        result = await session.execute(stmt)
        return list(result.scalars().all())
    except SQLAlchemyError as sqla_err:
        logger.error(f"SQLAlchemy error listing API keys: {sqla_err}")
        raise LuthienDBQueryError(f"Database query failed while listing API keys: {sqla_err}") from sqla_err
    except Exception as e:
        logger.error(f"Unexpected error listing API keys: {e}")
        raise LuthienDBOperationError(f"Unexpected error during API key listing: {e}") from e


async def update_api_key(session: AsyncSession, key_id: int, api_key_update: ClientApiKey) -> Optional[ClientApiKey]:
    """Update an existing API key.

    Args:
        session: The database session
        key_id: The ID of the API key to update
        api_key_update: The updated API key data

    Returns:
        The updated API key if found, None if the API key doesn't exist

    Raises:
        LuthienDBIntegrityError: If a constraint violation occurs
        LuthienDBTransactionError: If the transaction fails
        LuthienDBOperationError: For other database errors
    """
    try:
        stmt = select(ClientApiKey).where(ClientApiKey.id == key_id)  # type: ignore[arg-type]
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
    except IntegrityError as ie:
        await session.rollback()
        logger.error(f"Integrity error updating API key: {ie}")
        raise LuthienDBIntegrityError(f"Could not update API key due to constraint violation: {ie}", ie) from ie
    except SQLAlchemyError as sqla_err:
        await session.rollback()
        logger.error(f"SQLAlchemy error updating API key: {sqla_err}")
        raise LuthienDBTransactionError(f"Database transaction failed while updating API key: {sqla_err}") from sqla_err
    except Exception as e:
        await session.rollback()
        logger.error(f"Unexpected error updating API key: {e}")
        raise LuthienDBOperationError(f"Unexpected error during API key update: {e}") from e
