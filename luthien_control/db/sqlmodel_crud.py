import logging
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .sqlmodel_models import ClientApiKey, Policy

logger = logging.getLogger(__name__)


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


async def get_api_key_by_value(session: AsyncSession, key_value: str) -> Optional[ClientApiKey]:
    """Get an API key by its value."""
    try:
        stmt = select(ClientApiKey).where(
            ClientApiKey.key_value == key_value,
            ClientApiKey.is_active == True  # noqa: E712
        )
        result = await session.execute(stmt)
        api_key = result.scalar_one_or_none()
        return api_key
    except Exception as e:
        logger.error(f"Error fetching API key by value: {e}")
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


async def update_api_key(
    session: AsyncSession, key_id: int, api_key_update: ClientApiKey
) -> Optional[ClientApiKey]:
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


# --- Policy CRUD Operations ---

async def create_policy(session: AsyncSession, policy: Policy) -> Optional[Policy]:
    """Create a new policy in the database."""
    try:
        session.add(policy)
        await session.commit()
        await session.refresh(policy)
        logger.info(f"Successfully created policy with ID: {policy.id}")
        return policy
    except Exception as e:
        await session.rollback()
        logger.error(f"Error creating policy: {e}")
        return None


async def get_policy_by_name(session: AsyncSession, name: str) -> Optional[Policy]:
    """Get a policy by its name."""
    try:
        stmt = select(Policy).where(
            Policy.name == name,
            Policy.is_active == True  # noqa: E712
        )
        result = await session.execute(stmt)
        policy = result.scalar_one_or_none()
        return policy
    except Exception as e:
        logger.error(f"Error fetching policy by name: {e}")
        return None


async def list_policies(session: AsyncSession, active_only: bool = False) -> List[Policy]:
    """Get a list of all policies."""
    try:
        if active_only:
            stmt = select(Policy).where(Policy.is_active == True)  # noqa: E712
        else:
            stmt = select(Policy)

        result = await session.execute(stmt)
        return list(result.scalars().all())
    except Exception as e:
        logger.error(f"Error listing policies: {e}")
        return []


async def update_policy(
    session: AsyncSession, policy_id: int, policy_update: Policy
) -> Optional[Policy]:
    """Update an existing policy."""
    try:
        stmt = select(Policy).where(Policy.id == policy_id)
        result = await session.execute(stmt)
        policy = result.scalar_one_or_none()

        if not policy:
            logger.warning(f"Policy with ID {policy_id} not found")
            return None

        # Update fields
        policy.name = policy_update.name
        policy.policy_class_path = policy_update.policy_class_path
        policy.config = policy_update.config
        policy.is_active = policy_update.is_active
        policy.description = policy_update.description

        await session.commit()
        await session.refresh(policy)
        logger.info(f"Successfully updated policy with ID: {policy.id}")
        return policy
    except Exception as e:
        await session.rollback()
        logger.error(f"Error updating policy: {e}")
        return None
