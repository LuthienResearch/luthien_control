import logging
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.control_policy.exceptions import PolicyLoadError
from luthien_control.control_policy.loader import load_policy
from luthien_control.control_policy.serialization import SerializedPolicy

from .sqlmodel_models import ControlPolicy as DBControlPolicy

if TYPE_CHECKING:
    # This is the Pydantic ABC, used for instantiated policies
    from luthien_control.control_policy.control_policy import ControlPolicy as ABCControlPolicy
    from luthien_control.core.dependency_container import DependencyContainer

logger = logging.getLogger(__name__)


async def save_policy_to_db(session: AsyncSession, policy: DBControlPolicy) -> Optional[DBControlPolicy]:
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


async def get_policy_by_name(session: AsyncSession, name: str) -> Optional[DBControlPolicy]:
    """Get a policy by its name."""
    try:
        stmt = select(DBControlPolicy).where(
            DBControlPolicy.name == name,  # type: ignore[arg-type]
            DBControlPolicy.is_active,  # type: ignore[arg-type]
        )
        result = await session.execute(stmt)
        policy = result.scalar_one_or_none()
        return policy
    except Exception as e:
        logger.error(f"Error fetching policy by name '{name}': {e}", exc_info=True)
        return None


async def list_policies(session: AsyncSession, active_only: bool = False) -> List[DBControlPolicy]:
    """Get a list of all policies."""
    try:
        if active_only:
            stmt = select(DBControlPolicy).where(DBControlPolicy.is_active)  # type: ignore[arg-type]
        else:
            stmt = select(DBControlPolicy)

        result = await session.execute(stmt)
        return list(result.scalars().all())
    except Exception as e:
        logger.error(f"Error listing policies: {e}")
        return []


async def update_policy(
    session: AsyncSession, policy_id: int, policy_update: DBControlPolicy
) -> Optional[DBControlPolicy]:
    """Update an existing policy."""
    try:
        stmt = select(DBControlPolicy).where(DBControlPolicy.id == policy_id)  # type: ignore[arg-type]
        result = await session.execute(stmt)
        policy = result.scalar_one_or_none()

        if not policy:
            logger.warning(f"Policy with ID {policy_id} not found")
            return None

        # Update fields
        policy.name = policy_update.name
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
    container: "DependencyContainer",
) -> "ABCControlPolicy":
    """Load a policy configuration from the database and instantiate it using the control_policy loader."""
    async with container.db_session_factory() as session:
        policy_name = await get_policy_by_name(session, name)

    if not policy_name:
        raise PolicyLoadError(f"Active policy configuration named '{name}' not found in database.")

    # Prepare the data for the simple loader
    policy_data_dict = {
        "type": policy_name.type,  # The loader uses this to find the class
        "config": policy_name.config or {},
    }

    # Construct the SerializedPolicy dataclass instance
    serialized_policy_obj = SerializedPolicy(type=policy_data_dict["type"], config=policy_data_dict["config"])

    try:
        instance = load_policy(serialized_policy_obj)
        logger.info(f"Successfully loaded and instantiated policy '{policy_name.name}' from database.")
        return instance
    except PolicyLoadError as e:
        logger.error(f"Failed to load policy '{name}' from database: {e}")
        raise e
    except Exception as e:
        logger.exception(f"Unexpected error loading policy '{name}' from database: {e}")
        raise PolicyLoadError(f"Unexpected error during loading process for '{name}'.") from e


async def get_policy_config_by_name(session: AsyncSession, name: str) -> Optional[DBControlPolicy]:
    """Get a policy configuration by its name, regardless of its active status."""
    if not isinstance(session, AsyncSession):
        raise TypeError("Invalid session object provided to get_policy_config_by_name.")
    try:
        stmt = select(DBControlPolicy).where(DBControlPolicy.name == name)  # type: ignore[arg-type]
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Error fetching policy configuration by name '{name}': {e}", exc_info=True)
        return None
