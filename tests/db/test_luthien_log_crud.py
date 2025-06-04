from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from luthien_control.db.exceptions import (
    LuthienDBOperationError,
    LuthienDBQueryError,
)
from luthien_control.db.luthien_log_crud import (
    count_logs,
    get_log_by_id,
    get_unique_datatypes,
    get_unique_transaction_ids,
    list_logs,
)
from luthien_control.db.sqlmodel_models import LuthienLog
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

# Mark all tests as async
pytestmark = pytest.mark.asyncio


async def test_list_logs_empty(async_session: AsyncSession):
    """Test listing logs when none exist."""
    logs = await list_logs(async_session)
    assert logs == []


async def test_list_logs_with_data(async_session: AsyncSession):
    """Test listing logs with sample data."""
    # Create test log entries
    log1 = LuthienLog(
        transaction_id="tx-123",
        datetime=datetime.now(timezone.utc),
        datatype="test_type",
        data={"message": "test data 1"},
        notes={"test": True},
    )
    log2 = LuthienLog(
        transaction_id="tx-456",
        datetime=datetime.now(timezone.utc),
        datatype="another_type",
        data={"message": "test data 2"},
    )

    async_session.add(log1)
    async_session.add(log2)
    await async_session.commit()
    await async_session.refresh(log1)
    await async_session.refresh(log2)

    # List all logs
    logs = await list_logs(async_session)
    assert len(logs) == 2

    # Check ordering (should be by datetime desc)
    log_ids = [log.id for log in logs]
    assert log2.id in log_ids
    assert log1.id in log_ids


async def test_list_logs_with_filters(async_session: AsyncSession):
    """Test listing logs with various filters."""
    # Create test log entries
    log1 = LuthienLog(
        transaction_id="tx-123",
        datetime=datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        datatype="test_type",
        data={"message": "test data 1"},
    )
    log2 = LuthienLog(
        transaction_id="tx-456",
        datetime=datetime(2023, 1, 2, 12, 0, 0, tzinfo=timezone.utc),
        datatype="another_type",
        data={"message": "test data 2"},
    )

    async_session.add(log1)
    async_session.add(log2)
    await async_session.commit()
    await async_session.refresh(log1)
    await async_session.refresh(log2)

    # Filter by transaction_id
    logs = await list_logs(async_session, transaction_id="tx-123")
    assert len(logs) == 1
    assert logs[0].transaction_id == "tx-123"

    # Filter by datatype
    logs = await list_logs(async_session, datatype="test_type")
    assert len(logs) == 1
    assert logs[0].datatype == "test_type"

    # Filter by datetime range
    start_dt = datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    end_dt = datetime(2023, 1, 1, 23, 59, 59, tzinfo=timezone.utc)
    logs = await list_logs(async_session, start_datetime=start_dt, end_datetime=end_dt)
    assert len(logs) == 1
    assert logs[0].datetime.date() == datetime(2023, 1, 1).date()


async def test_list_logs_pagination(async_session: AsyncSession):
    """Test pagination of log listing."""
    # Create multiple test logs
    for i in range(5):
        log = LuthienLog(
            transaction_id=f"tx-{i}",
            datetime=datetime.now(timezone.utc),
            datatype="test_type",
            data={"index": i},
        )
        async_session.add(log)

    await async_session.commit()

    # Test limit
    logs = await list_logs(async_session, limit=3)
    assert len(logs) == 3

    # Test offset
    logs = await list_logs(async_session, limit=2, offset=2)
    assert len(logs) == 2


async def test_get_log_by_id(async_session: AsyncSession):
    """Test getting a specific log by ID."""
    # Create test log
    log = LuthienLog(
        transaction_id="tx-123",
        datetime=datetime.now(timezone.utc),
        datatype="test_type",
        data={"message": "test data"},
    )

    async_session.add(log)
    await async_session.commit()
    await async_session.refresh(log)

    # Get log by ID
    retrieved_log = await get_log_by_id(async_session, log.id)
    assert retrieved_log.id == log.id
    assert retrieved_log.transaction_id == "tx-123"
    assert retrieved_log.datatype == "test_type"


async def test_get_log_by_id_not_found(async_session: AsyncSession):
    """Test getting a log by ID that doesn't exist."""
    with pytest.raises(LuthienDBQueryError, match="Log with ID 999 not found"):
        await get_log_by_id(async_session, 999)


async def test_get_unique_datatypes(async_session: AsyncSession):
    """Test getting unique datatypes."""
    # Create logs with different datatypes
    log1 = LuthienLog(
        transaction_id="tx-1",
        datetime=datetime.now(timezone.utc),
        datatype="type_a",
        data={},
    )
    log2 = LuthienLog(
        transaction_id="tx-2",
        datetime=datetime.now(timezone.utc),
        datatype="type_b",
        data={},
    )
    log3 = LuthienLog(
        transaction_id="tx-3",
        datetime=datetime.now(timezone.utc),
        datatype="type_a",  # Duplicate
        data={},
    )

    async_session.add(log1)
    async_session.add(log2)
    async_session.add(log3)
    await async_session.commit()

    datatypes = await get_unique_datatypes(async_session)
    assert len(datatypes) == 2
    assert "type_a" in datatypes
    assert "type_b" in datatypes


async def test_get_unique_transaction_ids(async_session: AsyncSession):
    """Test getting unique transaction IDs."""
    # Create logs with different transaction IDs
    log1 = LuthienLog(
        transaction_id="tx-1",
        datetime=datetime.now(timezone.utc),
        datatype="test",
        data={},
    )
    log2 = LuthienLog(
        transaction_id="tx-2",
        datetime=datetime.now(timezone.utc),
        datatype="test",
        data={},
    )
    log3 = LuthienLog(
        transaction_id="tx-1",  # Duplicate
        datetime=datetime.now(timezone.utc),
        datatype="test",
        data={},
    )

    async_session.add(log1)
    async_session.add(log2)
    async_session.add(log3)
    await async_session.commit()

    transaction_ids = await get_unique_transaction_ids(async_session, limit=10)
    assert len(transaction_ids) == 2
    assert "tx-1" in transaction_ids
    assert "tx-2" in transaction_ids


async def test_count_logs(async_session: AsyncSession):
    """Test counting logs."""
    # Create test logs
    log1 = LuthienLog(
        transaction_id="tx-123",
        datetime=datetime.now(timezone.utc),
        datatype="test_type",
        data={},
    )
    log2 = LuthienLog(
        transaction_id="tx-456",
        datetime=datetime.now(timezone.utc),
        datatype="another_type",
        data={},
    )

    async_session.add(log1)
    async_session.add(log2)
    await async_session.commit()

    # Count all logs
    count = await count_logs(async_session)
    assert count == 2

    # Count with filters
    count = await count_logs(async_session, transaction_id="tx-123")
    assert count == 1

    count = await count_logs(async_session, datatype="test_type")
    assert count == 1


async def test_list_logs_sqlalchemy_error(async_session: AsyncSession):
    """Test handling of SQLAlchemy errors in list_logs."""
    # Mock the session to raise SQLAlchemyError
    mock_session = Mock()
    mock_session.execute.side_effect = SQLAlchemyError("Database error")

    with pytest.raises(LuthienDBQueryError, match="Database query failed while listing logs"):
        await list_logs(mock_session)


async def test_get_log_by_id_sqlalchemy_error(async_session: AsyncSession):
    """Test handling of SQLAlchemy errors in get_log_by_id."""
    # Mock the session to raise SQLAlchemyError
    mock_session = Mock()
    mock_session.execute.side_effect = SQLAlchemyError("Database error")

    with pytest.raises(LuthienDBQueryError, match="Database query failed while fetching log"):
        await get_log_by_id(mock_session, 1)


async def test_get_unique_datatypes_sqlalchemy_error(async_session: AsyncSession):
    """Test handling of SQLAlchemy errors in get_unique_datatypes."""
    # Mock the session to raise SQLAlchemyError
    mock_session = Mock()
    mock_session.execute.side_effect = SQLAlchemyError("Database error")

    with pytest.raises(LuthienDBQueryError, match="Database query failed while fetching datatypes"):
        await get_unique_datatypes(mock_session)


async def test_list_logs_unexpected_error(async_session: AsyncSession):
    """Test handling of unexpected errors in list_logs."""
    # Mock the session to raise a generic exception
    mock_session = Mock()
    mock_session.execute.side_effect = Exception("Unexpected error")

    with pytest.raises(LuthienDBOperationError, match="Unexpected error during log listing"):
        await list_logs(mock_session)
