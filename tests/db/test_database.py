import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
import asyncpg
import luthien_control.db.database

# Assuming absolute imports
from luthien_control.db.database import (
    close_log_db_pool,
    create_log_db_pool,
    get_log_db_pool,
    close_main_db_pool,
    create_main_db_pool,
    get_main_db_pool,
    _log_db_pool,
    _main_db_pool,
)

# Mark all tests in this module as async tests
pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture(autouse=True)
def set_test_db_env_vars(monkeypatch):
    """Sets required database environment variables and resets global pools for tests."""
    # Use monkeypatch to ensure isolation between tests
    # Log DB Vars
    monkeypatch.setenv("LOG_DB_USER", "test_log_user")
    monkeypatch.setenv("LOG_DB_PASSWORD", "test_log_password")
    monkeypatch.setenv("LOG_DB_HOST", "localhost")
    monkeypatch.setenv("LOG_DB_PORT", "5433")  # Different port for testing
    monkeypatch.setenv("LOG_DB_NAME", "test_log_db")
    # Main DB Vars (using postgres naming convention)
    monkeypatch.setenv("POSTGRES_USER", "test_main_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test_main_password")
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "5434")  # Different port
    monkeypatch.setenv("POSTGRES_DB", "test_main_db")

    # Reset global pool variables before each test
    # Use the actual names: _log_db_pool and _main_db_pool
    monkeypatch.setattr(luthien_control.db.database, "_log_db_pool", None)
    monkeypatch.setattr(luthien_control.db.database, "_main_db_pool", None)

    yield  # Test runs here

    # Teardown: Reset globals again just in case
    # Use the actual names: _log_db_pool and _main_db_pool
    monkeypatch.setattr(luthien_control.db.database, "_log_db_pool", None)
    monkeypatch.setattr(luthien_control.db.database, "_main_db_pool", None)


@pytest.mark.asyncio
async def test_create_and_close_log_db_pool(set_test_db_env_vars):
    """Test creating and closing the logging database pool."""
    with patch("asyncpg.create_pool", new_callable=AsyncMock) as mock_create_pool:
        # Configure mock to return a mock pool object
        mock_pool_instance = AsyncMock(spec=asyncpg.Pool)
        # Mock the close method on the instance returned by create_pool
        mock_pool_instance.close = AsyncMock()
        mock_create_pool.return_value = mock_pool_instance

        # Ensure pool is initially None (using direct access for test assertion)
        assert luthien_control.db.database._log_db_pool is None

        # Create pool
        await create_log_db_pool()

        # Verify create_pool was called with correct DSN (based on fixture env vars)
        mock_create_pool.assert_awaited_once()
        call_args = mock_create_pool.await_args[1]  # Get keyword args
        assert call_args["dsn"] == "postgresql://test_log_user:test_log_password@localhost:5433/test_log_db"
        assert call_args["min_size"] == 1  # Default
        assert call_args["max_size"] == 10  # Default

        # Verify global pool variable is set
        assert luthien_control.db.database._log_db_pool == mock_pool_instance

        # Test get_log_db_pool retrieves the pool
        retrieved_pool = get_log_db_pool()
        assert retrieved_pool == mock_pool_instance

        # Close pool
        await close_log_db_pool()

        # Verify pool.close() was called
        mock_pool_instance.close.assert_awaited_once()

        # Verify global pool variable is reset
        assert luthien_control.db.database._log_db_pool is None


@pytest.mark.asyncio
async def test_create_and_close_main_db_pool(set_test_db_env_vars):
    """Test creating and closing the main database pool."""
    with patch("asyncpg.create_pool", new_callable=AsyncMock) as mock_create_pool:
        mock_pool_instance = AsyncMock(spec=asyncpg.Pool)
        mock_pool_instance.close = AsyncMock()  # Mock close on the instance
        mock_create_pool.return_value = mock_pool_instance

        assert luthien_control.db.database._main_db_pool is None

        await create_main_db_pool()

        mock_create_pool.assert_awaited_once()
        call_args = mock_create_pool.await_args[1]
        # DSN uses POSTGRES env vars set in fixture
        assert call_args["dsn"] == "postgresql://test_main_user:test_main_password@localhost:5434/test_main_db"
        assert call_args["min_size"] == 1  # Default
        assert call_args["max_size"] == 10  # Default

        assert luthien_control.db.database._main_db_pool == mock_pool_instance

        retrieved_pool = get_main_db_pool()
        assert retrieved_pool == mock_pool_instance

        await close_main_db_pool()

        mock_pool_instance.close.assert_awaited_once()

        assert luthien_control.db.database._main_db_pool is None


@pytest.mark.asyncio
async def test_create_pool_already_initialized(set_test_db_env_vars, caplog):
    """Test that attempting to create an already initialized pool logs a warning."""
    with patch("asyncpg.create_pool", new_callable=AsyncMock) as mock_create_pool:
        mock_pool_instance = AsyncMock(spec=asyncpg.Pool)
        mock_pool_instance.close = AsyncMock()
        mock_create_pool.return_value = mock_pool_instance

        # Create log pool first time
        await create_log_db_pool()
        assert mock_create_pool.call_count == 1
        # Check for specific part of the success message
        assert "Logging database connection pool created successfully" in caplog.text

        # Attempt to create log pool again
        caplog.clear()
        await create_log_db_pool()
        # Should not call asyncpg.create_pool again
        assert mock_create_pool.call_count == 1
        # Should log a warning
        assert "Logging database pool already initialized." in caplog.text

        # Create main pool first time
        caplog.clear()
        await create_main_db_pool()
        assert mock_create_pool.call_count == 2
        # Check for specific part of the success message
        assert "Main database connection pool created successfully" in caplog.text

        # Attempt to create main pool again
        caplog.clear()
        await create_main_db_pool()
        assert mock_create_pool.call_count == 2
        assert "Main database pool already initialized." in caplog.text


@pytest.mark.asyncio
async def test_get_pool_before_initialization(set_test_db_env_vars):
    """Test that get_pool raises RuntimeError if called before creation."""
    # Fixture ensures pools are None initially
    with pytest.raises(RuntimeError, match="Logging database pool has not been initialized."):
        get_log_db_pool()

    with pytest.raises(RuntimeError, match="Main database pool has not been initialized."):
        get_main_db_pool()


@pytest.mark.asyncio
async def test_create_pool_missing_env_vars(monkeypatch, caplog):
    """Test pool creation failure when essential env vars are missing."""
    # Use the autouse fixture `set_test_db_env_vars` first to set everything,
    # then explicitly delete some vars for this specific test.

    # Explicitly remove one essential env var for each pool type
    monkeypatch.delenv("LOG_DB_PASSWORD", raising=False)
    monkeypatch.delenv("POSTGRES_USER", raising=False)

    with patch("asyncpg.create_pool", new_callable=AsyncMock) as mock_create_pool:
        # Ensure globals are None before starting (handled by fixture)
        assert luthien_control.db.database._log_db_pool is None
        assert luthien_control.db.database._main_db_pool is None

        await create_log_db_pool()
        # Pool creation should not be attempted due to config error
        mock_create_pool.assert_not_called()
        assert "Configuration error for logging database pool" in caplog.text
        assert "Missing essential logging database connection environment variables" in caplog.text
        assert luthien_control.db.database._log_db_pool is None

        caplog.clear()  # Clear logs for the next check

        await create_main_db_pool()
        mock_create_pool.assert_not_called()  # Still not called
        assert "Configuration error for main database pool" in caplog.text
        assert "Missing essential main database connection environment variables" in caplog.text
        assert luthien_control.db.database._main_db_pool is None


@pytest.mark.asyncio
async def test_create_pool_asyncpg_error(set_test_db_env_vars, caplog):
    """Test handling of asyncpg errors during pool creation."""
    with patch("asyncpg.create_pool", new_callable=AsyncMock) as mock_create_pool:
        # Simulate an error during asyncpg.create_pool
        mock_create_pool.side_effect = asyncpg.PostgresError("Connection refused")

        # Ensure globals are None before starting (handled by fixture)
        assert luthien_control.db.database._log_db_pool is None
        assert luthien_control.db.database._main_db_pool is None

        await create_log_db_pool()

        mock_create_pool.assert_awaited_once()  # It was called
        assert "Failed to create logging database connection pool" in caplog.text
        assert "Connection refused" in caplog.text
        # Ensure pool variable remains None
        assert luthien_control.db.database._log_db_pool is None

        # Reset mock and logs for main DB test
        mock_create_pool.reset_mock()
        caplog.clear()

        await create_main_db_pool()
        mock_create_pool.assert_awaited_once()
        assert "Failed to create main database connection pool" in caplog.text
        assert "Connection refused" in caplog.text
        assert luthien_control.db.database._main_db_pool is None
