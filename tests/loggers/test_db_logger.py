import json
from unittest.mock import AsyncMock, MagicMock, call, patch

import asyncpg
import pytest
from luthien_control.config.settings import Settings
from luthien_control.logging.db_logger import log_db_entry
from luthien_control.db.database import get_log_db_pool

# Mark all tests in this module as unit tests
pytestmark = pytest.mark.unit

# --- Fixtures ---


@pytest.fixture
def mock_log_pool() -> MagicMock:
    """Provides a mock asyncpg Pool specifically for logging tests."""
    pool = MagicMock(spec=asyncpg.Pool)
    # Mock the __aenter__ and __aexit__ methods for the async context manager
    mock_conn = AsyncMock(spec=asyncpg.Connection)
    pool.acquire.return_value.__aenter__.return_value = mock_conn
    pool.acquire.return_value.__aexit__.return_value = None
    return pool


@pytest.fixture
def mock_log_connection(mock_log_pool: MagicMock) -> AsyncMock:
    """Provides the mock asyncpg Connection from the mock_log_pool."""
    # Access the mock connection returned by the pool's acquire context manager
    return mock_log_pool.acquire.return_value.__aenter__.return_value


@pytest.fixture(autouse=True)
def patch_get_log_db_pool(mock_log_pool: MagicMock):
    """Patches get_log_db_pool to return the mock pool for all tests in this module."""
    # Patch the target function where it's *looked up* (in db_logger.py)
    with patch("luthien_control.logging.db_logger.get_log_db_pool", return_value=mock_log_pool) as patched:
        yield patched


# --- Test Cases ---


@pytest.mark.asyncio
async def test_log_db_entry_success(mock_log_connection: AsyncMock):
    """Test successful logging of a dictionary entry to the database."""
    test_data = {"key1": "value1", "number": 123, "bool": True, "nested": {"a": 1}}
    test_client_ip = "192.168.1.100"

    # Call the function under test
    await log_db_entry(data=test_data, client_ip=test_client_ip)

    # Verify the execute method was called on the connection
    mock_log_connection.execute.assert_awaited_once()

    # Extract arguments passed to execute
    # execute takes sql, *params
    call_args = mock_log_connection.execute.await_args[0]
    sql_query = call_args[0]
    params = call_args[1:]  # The rest are the parameters

    # Check the SQL query structure (basic check)
    assert "INSERT INTO logs" in sql_query
    assert "(client_ip, log_level, message, data, timestamp)" in sql_query
    assert "VALUES ($1, $2, $3, $4, $5)" in sql_query

    # Check the parameters passed
    assert params[0] == test_client_ip
    assert params[1] == "INFO"  # Default level
    assert params[2] == "Generic log entry"  # Default message
    # Data should be JSON serialized
    assert params[3] == json.dumps(test_data)
    # Timestamp ($5) is checked implicitly by being the 5th parameter
    assert len(params) == 5


@pytest.mark.asyncio
async def test_log_db_entry_custom_level_message(mock_log_connection: AsyncMock):
    """Test logging with custom log level and message."""
    test_data = {"error_code": 500}
    test_client_ip = "10.0.0.5"
    log_level = "ERROR"
    message = "An error occurred"

    await log_db_entry(data=test_data, client_ip=test_client_ip, log_level=log_level, message=message)

    mock_log_connection.execute.assert_awaited_once()
    # Correctly extract positional args passed to execute
    call_args = mock_log_connection.execute.await_args[0]
    params = call_args[1:]  # Skip the SQL query itself

    assert params[0] == test_client_ip
    assert params[1] == log_level
    assert params[2] == message
    assert params[3] == json.dumps(test_data)
    assert len(params) == 5


@pytest.mark.asyncio
async def test_log_db_entry_db_error(mock_log_connection: AsyncMock, caplog):
    """Test handling of database errors during logging."""
    # Configure the mock connection to raise an exception
    db_error = asyncpg.PostgresError("Simulated DB Error")
    mock_log_connection.execute.side_effect = db_error

    test_data = {"status": "failed"}

    # Use caplog fixture to capture logs
    import logging

    caplog.set_level(logging.ERROR)

    # Call the function, expect it to handle the error gracefully (not raise)
    await log_db_entry(data=test_data)

    # Verify execute was called (even though it failed)
    mock_log_connection.execute.assert_awaited_once()

    # Verify error was logged
    assert "Failed to log entry to database" in caplog.text
    assert "Simulated DB Error" in caplog.text


@pytest.mark.asyncio
async def test_log_db_entry_pool_not_initialized(patch_get_log_db_pool: MagicMock, caplog):
    """Test behavior when the log database pool is not initialized."""
    # Configure the patched get_log_db_pool to raise RuntimeError
    error_message = "Log pool not initialized"
    patch_get_log_db_pool.side_effect = RuntimeError(error_message)

    test_data = {"info": "cannot log this"}

    import logging

    caplog.set_level(logging.ERROR)

    # Call the function, expect it to handle the error gracefully
    await log_db_entry(data=test_data)

    # Verify error was logged (check for the specific error message)
    assert "Cannot log DB entry: Logging database pool not initialized." in caplog.text
    # Check that the original error message is also included in the log
    assert error_message in caplog.text
