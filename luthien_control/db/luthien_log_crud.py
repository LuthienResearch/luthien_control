# CRUD operations specific to LuthienLog model.

import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy import desc, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.db.exceptions import (
    LuthienDBOperationError,
    LuthienDBQueryError,
)

from .sqlmodel_models import LuthienLog

logger = logging.getLogger(__name__)


async def list_logs(
    session: AsyncSession,
    transaction_id: Optional[str] = None,
    datatype: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    start_datetime: Optional[datetime] = None,
    end_datetime: Optional[datetime] = None,
) -> List[LuthienLog]:
    """Get a list of logs with optional filtering.

    Args:
        session: The database session
        transaction_id: Optional filter by transaction ID
        datatype: Optional filter by datatype
        limit: Maximum number of logs to return (default: 100)
        offset: Number of logs to skip (default: 0)
        start_datetime: Optional filter for logs after this datetime
        end_datetime: Optional filter for logs before this datetime

    Returns:
        A list of LuthienLog entries

    Raises:
        LuthienDBQueryError: If the query execution fails
        LuthienDBOperationError: For unexpected errors
    """
    try:
        stmt = select(LuthienLog).order_by(desc(LuthienLog.datetime))  # type: ignore[arg-type]

        # Apply filters
        if transaction_id:
            stmt = stmt.where(LuthienLog.transaction_id == transaction_id)  # type: ignore[arg-type]
        if datatype:
            stmt = stmt.where(LuthienLog.datatype == datatype)  # type: ignore[arg-type]
        if start_datetime:
            stmt = stmt.where(LuthienLog.datetime >= start_datetime)  # type: ignore[arg-type]
        if end_datetime:
            stmt = stmt.where(LuthienLog.datetime <= end_datetime)  # type: ignore[arg-type]

        # Apply pagination
        stmt = stmt.limit(limit).offset(offset)

        result = await session.execute(stmt)
        return list(result.scalars().all())
    except SQLAlchemyError as sqla_err:
        logger.error(f"SQLAlchemy error listing logs: {sqla_err}")
        raise LuthienDBQueryError(f"Database query failed while listing logs: {sqla_err}") from sqla_err
    except Exception as e:
        logger.error(f"Unexpected error listing logs: {e}")
        raise LuthienDBOperationError(f"Unexpected error during log listing: {e}") from e


async def get_log_by_id(session: AsyncSession, log_id: int) -> LuthienLog:
    """Get a specific log by its ID.

    Args:
        session: The database session
        log_id: The ID of the log to retrieve

    Returns:
        The log entry

    Raises:
        LuthienDBQueryError: If the log is not found or if the query execution fails
        LuthienDBOperationError: For unexpected errors during lookup
    """
    try:
        stmt = select(LuthienLog).where(LuthienLog.id == log_id)  # type: ignore[arg-type]
        result = await session.execute(stmt)
        log_entry = result.scalar_one_or_none()
    except SQLAlchemyError as sqla_err:
        logger.error(f"SQLAlchemy error fetching log by ID: {sqla_err}", exc_info=True)
        raise LuthienDBQueryError(f"Database query failed while fetching log: {sqla_err}") from sqla_err
    except Exception as e:
        logger.error(f"Unexpected error fetching log by ID: {e}", exc_info=True)
        raise LuthienDBOperationError(f"Unexpected error during log lookup: {e}") from e

    if not log_entry:
        raise LuthienDBQueryError(f"Log with ID {log_id} not found")

    return log_entry


async def get_unique_datatypes(session: AsyncSession) -> List[str]:
    """Get a list of unique datatypes from the logs.

    Args:
        session: The database session

    Returns:
        A list of unique datatype values

    Raises:
        LuthienDBQueryError: If the query execution fails
        LuthienDBOperationError: For unexpected errors
    """
    try:
        stmt = select(LuthienLog.datatype).distinct().order_by(LuthienLog.datatype)  # type: ignore[arg-type]
        result = await session.execute(stmt)
        return list(result.scalars().all())
    except SQLAlchemyError as sqla_err:
        logger.error(f"SQLAlchemy error fetching unique datatypes: {sqla_err}")
        raise LuthienDBQueryError(f"Database query failed while fetching datatypes: {sqla_err}") from sqla_err
    except Exception as e:
        logger.error(f"Unexpected error fetching unique datatypes: {e}")
        raise LuthienDBOperationError(f"Unexpected error during datatype lookup: {e}") from e


async def get_unique_transaction_ids(session: AsyncSession, limit: int = 100) -> List[str]:
    """Get a list of unique transaction IDs from recent logs.

    Args:
        session: The database session
        limit: Maximum number of transaction IDs to return (default: 100)

    Returns:
        A list of unique transaction ID values

    Raises:
        LuthienDBQueryError: If the query execution fails
        LuthienDBOperationError: For unexpected errors
    """
    try:
        # Get distinct transaction_ids ordered by the most recent datetime for each transaction
        stmt = (
            select(LuthienLog.transaction_id)  # type: ignore[arg-type]
            .group_by(LuthienLog.transaction_id)  # type: ignore[arg-type]
            .order_by(desc(LuthienLog.transaction_id))  # type: ignore[arg-type]
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())
    except SQLAlchemyError as sqla_err:
        logger.error(f"SQLAlchemy error fetching unique transaction IDs: {sqla_err}")
        raise LuthienDBQueryError(f"Database query failed while fetching transaction IDs: {sqla_err}") from sqla_err
    except Exception as e:
        logger.error(f"Unexpected error fetching unique transaction IDs: {e}")
        raise LuthienDBOperationError(f"Unexpected error during transaction ID lookup: {e}") from e


async def count_logs(
    session: AsyncSession,
    transaction_id: Optional[str] = None,
    datatype: Optional[str] = None,
    start_datetime: Optional[datetime] = None,
    end_datetime: Optional[datetime] = None,
) -> int:
    """Count logs with optional filtering.

    Args:
        session: The database session
        transaction_id: Optional filter by transaction ID
        datatype: Optional filter by datatype
        start_datetime: Optional filter for logs after this datetime
        end_datetime: Optional filter for logs before this datetime

    Returns:
        The count of matching logs

    Raises:
        LuthienDBQueryError: If the query execution fails
        LuthienDBOperationError: For unexpected errors
    """
    try:
        stmt = select(LuthienLog.id)  # type: ignore[arg-type]

        # Apply filters
        if transaction_id:
            stmt = stmt.where(LuthienLog.transaction_id == transaction_id)  # type: ignore[arg-type]
        if datatype:
            stmt = stmt.where(LuthienLog.datatype == datatype)  # type: ignore[arg-type]
        if start_datetime:
            stmt = stmt.where(LuthienLog.datetime >= start_datetime)  # type: ignore[arg-type]
        if end_datetime:
            stmt = stmt.where(LuthienLog.datetime <= end_datetime)  # type: ignore[arg-type]

        result = await session.execute(stmt)
        return len(list(result.scalars().all()))
    except SQLAlchemyError as sqla_err:
        logger.error(f"SQLAlchemy error counting logs: {sqla_err}")
        raise LuthienDBQueryError(f"Database query failed while counting logs: {sqla_err}") from sqla_err
    except Exception as e:
        logger.error(f"Unexpected error counting logs: {e}")
        raise LuthienDBOperationError(f"Unexpected error during log counting: {e}") from e
