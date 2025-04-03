import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# Assuming absolute imports
from luthien_control.db.database import (
    DBSettings,
    close_db_pool,
    create_db_pool,
    get_db_pool,
    log_request_response,
)

# Mark all tests in this module as async tests
pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def mock_pool(monkeypatch):
    """Fixture to provide a mock asyncpg pool and manage global state."""
    mock_pool_instance = AsyncMock()
    mock_conn = AsyncMock()

    # Create a mock for the context manager returned by acquire()
    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__.return_value = mock_conn
    # __aexit__ needs to be an async def or AsyncMock for 'async with'
    # It takes args (exc_type, exc_val, exc_tb)
    mock_context_manager.__aexit__ = AsyncMock(
        return_value=None
    )  # Mock __aexit__ as well

    # Configure pool.acquire() to return the mock context manager
    # Importantly, acquire() itself is likely NOT async, it just returns the async context manager
    mock_pool_instance.acquire = MagicMock(return_value=mock_context_manager)

    # Mock release if it's called on the pool (check asyncpg docs if needed)
    # If release is called on the connection, mock it there.
    # Assuming release is called on the pool:
    mock_pool_instance.release = AsyncMock()

    # Patch the global _db_pool variable within the database module
    monkeypatch.setattr("luthien_control.db.database._db_pool", mock_pool_instance)

    yield mock_pool_instance, mock_conn  # Yield connection too for assertions

    # Clean up global state after test
    monkeypatch.setattr("luthien_control.db.database._db_pool", None)


async def test_log_request_response_executes_insert(mock_pool):
    """Test that log_request_response attempts to execute the correct INSERT statement."""
    pool, conn = mock_pool  # Unpack pool and connection mock

    request_data = {
        "method": "POST",
        "url": "http://example.com/test",
        "headers": {"Content-Type": "application/json", "X-Trace": "123"},
        "body": '{"key": "value"}',
    }
    response_data = {
        "status_code": 201,
        "headers": {"Content-Length": "50", "X-Request-ID": "abc"},
        "body": '{"result": "created"}',
    }
    client_ip = "192.168.0.100"
    # Assume processing_time_ms is calculated and added within the calling function or middleware
    # For this test, let's add it to the data passed in.
    request_data["processing_time_ms"] = 150

    # --- This is the part that will FAIL until implemented ---
    # We call the function, which currently raises NotImplementedError
    await log_request_response(
        pool=pool,
        request_data=request_data,
        response_data=response_data,
        client_ip=client_ip,
    )
    # --- End Failing Section ---

    # Assert that pool.acquire was called to get a connection
    pool.acquire.assert_called_once()

    # Assert that conn.execute was called
    conn.execute.assert_awaited_once()

    # Define the expected SQL (adjust table/column names if needed)
    # Using numbered placeholders ($1, $2, etc.) for asyncpg
    expected_sql = """
        INSERT INTO request_log (
            client_ip, request_method, request_url, request_headers, request_body,
            response_status_code, response_headers, response_body, processing_time_ms
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
    """

    # Get the actual arguments passed to conn.execute
    actual_args = conn.execute.call_args[0]  # Positional args
    actual_sql = actual_args[0]

    # Normalize whitespace for comparison
    assert " ".join(actual_sql.split()) == " ".join(expected_sql.split())

    # Check the parameters passed to execute
    expected_params = (
        client_ip,
        request_data["method"],
        request_data["url"],
        json.dumps(request_data["headers"]),  # Expect headers to be JSON encoded
        request_data["body"],
        response_data["status_code"],
        json.dumps(response_data["headers"]),  # Expect headers to be JSON encoded
        response_data["body"],
        request_data["processing_time_ms"],
    )
    assert actual_args[1:] == expected_params  # Compare parameters

    # Assert that the context manager was exited (implicitly checks release logic)
    # Check __aexit__ was awaited on the context manager object returned by acquire
    pool.acquire.return_value.__aexit__.assert_awaited_once()


@pytest_asyncio.fixture(autouse=True)
def reset_global_pool(monkeypatch):
    """Ensures the global _db_pool is reset before/after each test in this module."""
    # Reset before test
    monkeypatch.setattr("luthien_control.db.database._db_pool", None)
    yield
    # Reset after test
    monkeypatch.setattr("luthien_control.db.database._db_pool", None)


@patch("luthien_control.db.database.asyncpg.create_pool", new_callable=AsyncMock)
async def test_create_db_pool_success(mock_create_pool):
    """Test successful creation and retrieval of the DB pool."""
    settings = DBSettings(
        db_host="fake_host"
    )  # Use fake settings to avoid real connections
    mock_pool_instance = AsyncMock()
    mock_create_pool.return_value = mock_pool_instance

    # Expect RuntimeError when getting pool before creation
    with pytest.raises(RuntimeError, match="Database pool has not been initialized."):
        get_db_pool()

    await create_db_pool(settings)

    mock_create_pool.assert_awaited_once_with(
        dsn=settings.dsn,
        min_size=settings.db_pool_min_size,
        max_size=settings.db_pool_max_size,
    )
    assert get_db_pool() is mock_pool_instance

    # Test idempotency (calling again should not recreate)
    mock_create_pool.reset_mock()
    await create_db_pool(settings)
    mock_create_pool.assert_not_called()


@patch("luthien_control.db.database.asyncpg.create_pool", new_callable=AsyncMock)
async def test_create_db_pool_failure(mock_create_pool):
    """Test handling of failure during pool creation."""
    settings = DBSettings(db_host="another_fake")
    mock_create_pool.side_effect = Exception("Connection refused")

    await create_db_pool(settings)

    mock_create_pool.assert_awaited_once()
    with pytest.raises(RuntimeError, match="Database pool has not been initialized."):
        get_db_pool()  # Pool should be None or accessing it should raise


async def test_get_db_pool_not_initialized():
    """Test that get_db_pool raises RuntimeError if called before initialization."""
    # reset_global_pool fixture ensures _db_pool is None here
    with pytest.raises(RuntimeError, match="Database pool has not been initialized."):
        get_db_pool()


@patch(
    "luthien_control.db.database._db_pool", new_callable=AsyncMock
)  # Directly patch the global pool
async def test_close_db_pool(mock_global_pool):
    """Test closing the database pool."""
    # Ensure the mock pool has a close method
    mock_global_pool.close = AsyncMock()

    # Set the global pool to our mock for the test
    # (reset_global_pool clears it afterwards)

    await close_db_pool()

    mock_global_pool.close.assert_awaited_once()
    # After closing, accessing the pool should fail
    with pytest.raises(RuntimeError, match="Database pool has not been initialized."):
        get_db_pool()


async def test_close_db_pool_idempotent():
    """Test that closing a non-existent pool does nothing."""
    # reset_global_pool ensures pool is None
    # No mocks needed, just call close and ensure no error
    await close_db_pool()
    # Assertions? Maybe check logs if needed, but primarily testing for no exceptions.
    pass
