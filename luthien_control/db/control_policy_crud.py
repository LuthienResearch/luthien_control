import logging
from typing import List

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.db.exceptions import (
    LuthienDBIntegrityError,
    LuthienDBOperationError,
    LuthienDBQueryError,
    LuthienDBTransactionError,
)
from luthien_control.control_policy.control_policy import ControlPolicy as ABCControlPolicy
from luthien_control.control_policy.exceptions import PolicyLoadError
from luthien_control.control_policy.loader import load_policy
from luthien_control.control_policy.serialization import SerializedPolicy

from .sqlmodel_models import ControlPolicy as DBControlPolicy

logger = logging.getLogger(__name__)


async def save_policy_to_db(session: AsyncSession, policy: DBControlPolicy) -> DBControlPolicy:
    """Create a new policy in the database.

    Args:
        session: The database session
        policy: The policy to create

    Returns:
        The created policy with updated ID

    Raises:
        LuthienDBIntegrityError: If a constraint violation occurs
        LuthienDBTransactionError: If the transaction fails
        LuthienDBOperationError: For other database errors
    """
    try:
        session.add(policy)
        await session.commit()
        await session.refresh(policy)
        logger.info(f"Successfully created policy with ID: {policy.id}")
        return policy
    except IntegrityError as ie:
        await session.rollback()
        logger.error(f"Integrity error creating policy: {ie}")
        raise LuthienDBIntegrityError(f"Could not create policy due to constraint violation: {ie}", ie) from ie
    except SQLAlchemyError as sqla_err:
        await session.rollback()
        logger.error(f"SQLAlchemy error creating policy: {sqla_err}")
        raise LuthienDBTransactionError(f"Database transaction failed while creating policy: {sqla_err}") from sqla_err
    except Exception as e:
        await session.rollback()
        logger.error(f"Error creating policy: {e}")
        raise LuthienDBOperationError(f"Unexpected error during policy creation: {e}") from e


async def get_policy_by_name(session: AsyncSession, name: str) -> DBControlPolicy:
    """Get a policy by its name.

    Args:
        session: The database session
        name: The name of the policy to retrieve

    Returns:
        The policy

    Raises:
        LuthienDBQueryError: If the policy is not found or if the query execution fails
        LuthienDBOperationError: For unexpected errors during lookup
    """
    try:
        stmt = select(DBControlPolicy).where(
            DBControlPolicy.name == name,  # type: ignore[arg-type]
            DBControlPolicy.is_active,  # type: ignore[arg-type]
        )
        result = await session.execute(stmt)
        policy = result.scalar_one_or_none()
        if not policy:
            raise LuthienDBQueryError(f"Policy with name '{name}' not found")
        return policy
    except LuthienDBQueryError:
        raise
    except SQLAlchemyError as sqla_err:
        logger.error(f"SQLAlchemy error fetching policy by name '{name}': {sqla_err}", exc_info=True)
        raise LuthienDBQueryError(f"Database query failed while fetching policy '{name}': {sqla_err}") from sqla_err
    except Exception as e:
        logger.error(f"Unexpected error fetching policy by name '{name}': {e}", exc_info=True)
        raise LuthienDBOperationError(f"Unexpected error during policy lookup: {e}") from e


async def list_policies(session: AsyncSession, active_only: bool = False) -> List[DBControlPolicy]:
    """Get a list of all policies.

    Args:
        session: The database session
        active_only: If True, only return active policies

    Returns:
        A list of policies

    Raises:
        LuthienDBQueryError: If the query execution fails
    """
    try:
        if active_only:
            stmt = select(DBControlPolicy).where(DBControlPolicy.is_active)  # type: ignore[arg-type]
        else:
            stmt = select(DBControlPolicy)

        result = await session.execute(stmt)
        return list(result.scalars().all())
    except SQLAlchemyError as sqla_err:
        logger.error(f"SQLAlchemy error listing policies: {sqla_err}")
        raise LuthienDBQueryError(f"Database query failed while listing policies: {sqla_err}") from sqla_err
    except Exception as e:
        logger.error(f"Unexpected error listing policies: {e}")
        raise LuthienDBOperationError(f"Unexpected error during policy listing: {e}") from e


async def update_policy(session: AsyncSession, policy_id: int, policy_update: DBControlPolicy) -> DBControlPolicy:
    """Update an existing policy.

    Args:
        session: The database session
        policy_id: The ID of the policy to update
        policy_update: The updated policy data

    Returns:
        The updated policy

    Raises:
        LuthienDBQueryError: If the policy is not found
        LuthienDBIntegrityError: If a constraint violation occurs
        LuthienDBTransactionError: If the transaction fails
        LuthienDBOperationError: For other database errors
    """
    try:
        stmt = select(DBControlPolicy).where(DBControlPolicy.id == policy_id)  # type: ignore[arg-type]
        result = await session.execute(stmt)
        policy = result.scalar_one_or_none()

        if not policy:
            raise LuthienDBQueryError(f"Policy with ID {policy_id} not found")

        # Update fields
        policy.name = policy_update.name
        policy.config = policy_update.config
        policy.is_active = policy_update.is_active
        policy.description = policy_update.description

        await session.commit()
        await session.refresh(policy)
        logger.info(f"Successfully updated policy with ID: {policy.id}")
        return policy
    except LuthienDBQueryError:
        raise
    except IntegrityError as ie:
        await session.rollback()
        logger.error(f"Integrity error updating policy: {ie}")
        raise LuthienDBIntegrityError(f"Could not update policy due to constraint violation: {ie}", ie) from ie
    except SQLAlchemyError as sqla_err:
        await session.rollback()
        logger.error(f"SQLAlchemy error updating policy: {sqla_err}")
        raise LuthienDBTransactionError(f"Database transaction failed while updating policy: {sqla_err}") from sqla_err
    except Exception as e:
        await session.rollback()
        logger.error(f"Error updating policy: {e}")
        raise LuthienDBOperationError(f"Unexpected error during policy update: {e}") from e


async def load_policy_from_db(
    name: str,
    container: "DependencyContainer",
) -> "ABCControlPolicy":
    """Load a policy configuration from the database and instantiate it using the control_policy loader.

    Args:
        name: The name of the policy to load
        container: The dependency container providing access to the database session

    Returns:
        The instantiated policy

    Raises:
        LuthienDBQueryError: If the database query fails or policy is not found
        LuthienDBOperationError: If the policy cannot be instantiated or other database operation errors occur
    """
    try:
        async with container.db_session_factory() as session:
            policy_name = await get_policy_by_name(session, name)

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
            raise LuthienDBOperationError(
                f"Failed to instantiate policy '{name}' from database configuration: {e}"
            ) from e
        except Exception as e:
            logger.exception(f"Unexpected error loading policy '{name}' from database: {e}")
            raise LuthienDBOperationError(f"Unexpected error during policy instantiation for '{name}': {e}") from e
    except LuthienDBQueryError:
        raise
    except LuthienDBOperationError:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error during policy loading process for '{name}': {e}")
        raise LuthienDBOperationError(f"Unexpected error during policy loading process for '{name}': {e}") from e


async def get_policy_config_by_name(session: AsyncSession, name: str) -> DBControlPolicy:
    """Get a policy configuration by its name, regardless of its active status.

    Args:
        session: The database session
        name: The name of the policy to retrieve

    Returns:
        The policy

    Raises:
        LuthienDBQueryError: If the policy is not found or if the query execution fails
        LuthienDBOperationError: For unexpected errors during lookup
    """
    try:
        stmt = select(DBControlPolicy).where(DBControlPolicy.name == name)  # type: ignore[arg-type]
        result = await session.execute(stmt)
        policy = result.scalar_one_or_none()
        if not policy:
            raise LuthienDBQueryError(f"Policy with name '{name}' not found")
        return policy
    except LuthienDBQueryError:
        raise
    except SQLAlchemyError as sqla_err:
        logger.error(f"SQLAlchemy error fetching policy configuration by name '{name}': {sqla_err}", exc_info=True)
        raise LuthienDBQueryError(f"Database query failed while fetching policy config '{name}'") from sqla_err
    except Exception as e:
        logger.error(f"Unexpected error fetching policy configuration by name '{name}': {e}", exc_info=True)
        raise LuthienDBOperationError(f"Unexpected error during policy config lookup: {e}") from e
