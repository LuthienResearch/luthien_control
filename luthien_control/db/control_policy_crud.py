import logging
from typing import TYPE_CHECKING, Callable, List, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.config.settings import Settings
from luthien_control.control_policy.exceptions import PolicyLoadError
from luthien_control.control_policy.loader import load_policy

from .sqlmodel_models import ControlPolicy

if TYPE_CHECKING:
    from luthien_control.control_policy.control_policy import ControlPolicy

logger = logging.getLogger(__name__)


async def save_policy_to_db(session: AsyncSession, policy: ControlPolicy) -> Optional[ControlPolicy]:
    """Create a new policy in the database."""
    try:
        session.add(policy)
        await session.commit()
        await session.refresh(policy)
        logger.info(f"Successfully created policy with ID: {policy.id}")
        return policy
    except IntegrityError as ie:
        await session.rollback()
        logger.error(f"Integrity error creating policy: {ie}")
        raise  # Re-raise the specific integrity error
    except SQLAlchemyError as sqla_err:
        await session.rollback()
        logger.error(f"SQLAlchemy error creating policy: {sqla_err}")
        return None  # Or re-raise depending on desired handling
    except Exception as e:
        await session.rollback()
        logger.error(f"Error creating policy: {e}")
        return None


async def get_policy_by_name(session: AsyncSession, name: str) -> Optional[ControlPolicy]:
    """Get a policy by its name."""
    try:
        stmt = select(ControlPolicy).where(
            ControlPolicy.name == name,
            ControlPolicy.is_active == True,  # noqa: E712
        )
        result = await session.execute(stmt)
        policy = result.scalar_one_or_none()
        return policy
    except Exception as e:
        logger.error(f"Error fetching policy by name '{name}': {e}", exc_info=True)
        return None


async def list_policies(session: AsyncSession, active_only: bool = False) -> List[ControlPolicy]:
    """Get a list of all policies."""
    try:
        if active_only:
            stmt = select(ControlPolicy).where(ControlPolicy.is_active == True)  # noqa: E712
        else:
            stmt = select(ControlPolicy)

        result = await session.execute(stmt)
        return list(result.scalars().all())
    except Exception as e:
        logger.error(f"Error listing policies: {e}")
        return []


async def update_policy(session: AsyncSession, policy_id: int, policy_update: ControlPolicy) -> Optional[ControlPolicy]:
    """Update an existing policy."""
    try:
        stmt = select(ControlPolicy).where(ControlPolicy.id == policy_id)
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
    except IntegrityError as ie:
        await session.rollback()
        logger.error(f"Integrity error updating policy: {ie}")
        raise  # Re-raise the specific integrity error
    except SQLAlchemyError as sqla_err:
        await session.rollback()
        logger.error(f"SQLAlchemy error updating policy: {sqla_err}")
        return None  # Or re-raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Error updating policy: {e}")
        return None


async def load_policy_from_db(
    name: str,
    settings: Settings,
    http_client: httpx.AsyncClient,
    api_key_lookup: Callable,
    session: AsyncSession,
) -> "ControlPolicy":
    """Load a policy from the database using the control_policy loader."""
    policy_model = await get_policy_by_name(session, name)
    if not policy_model:
        raise PolicyLoadError(f"Active policy configuration named '{name}' not found in database.")

    # Prepare the data for the simple loader
    policy_data = {
        "name": policy_model.name,  # The loader uses this to find the class
        "config": policy_model.config or {},  # Pass the config dict directly
    }

    # Prepare available dependencies
    # The loader will filter these based on the policy's requirements
    available_dependencies = {
        "api_key_lookup": api_key_lookup,  # This function still expects session
        "settings": settings,
        "http_client": http_client,
        "db_session": session,  # Make session available if needed by future policies
    }

    try:
        # Call the simple loader from control_policy.loader
        # Note: This loader is now asynchronous.
        instance = await load_policy(policy_data, **available_dependencies)
        logger.info(f"Successfully loaded and instantiated policy '{name}' from database.")
        return instance
    except PolicyLoadError as e:
        logger.error(f"Failed to load policy '{name}' from database: {e}")
        # Re-raise cleanly, context is already included from instantiate_policy
        raise e
    except Exception as e:
        logger.exception(f"Unexpected error loading policy '{name}' from database: {e}")
        raise PolicyLoadError(f"Unexpected error during loading process for '{name}'.") from e


async def get_policy_config_by_name(session: AsyncSession, name: str) -> Optional[ControlPolicy]:
    """Get a policy configuration by its name, regardless of its active status."""
    if not isinstance(session, AsyncSession):
        raise TypeError("Invalid session object provided to get_policy_config_by_name.")
    try:
        stmt = select(ControlPolicy).where(ControlPolicy.name == name)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Error fetching policy configuration by name '{name}': {e}", exc_info=True)
        return None
