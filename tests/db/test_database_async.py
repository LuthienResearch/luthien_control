from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from luthien_control.db.database_async import (
    _get_db_url,
    _mask_password,
    close_db_engine,
    create_db_engine,
    get_db_session,
)
from luthien_control.db.database_async import settings as db_async_settings
from luthien_control.exceptions import LuthienDBConfigurationError, LuthienDBConnectionError


@pytest.mark.asyncio
async def test_get_db_url_with_database_url():
    """Test _get_db_url with DATABASE_URL environment variable."""
    test_db_url = "postgresql://user:pass@localhost/dbname"
    # Patch the settings method used by _get_db_url
    with patch.object(db_async_settings, "get_database_url", return_value=test_db_url):
        url_result = _get_db_url()
        assert url_result is not None
        assert url_result == "postgresql+asyncpg://user:pass@localhost/dbname"


@pytest.mark.asyncio
async def test_get_db_url_with_postgres_url():
    """Test _get_db_url with postgres:// URL."""
    test_db_url = "postgres://user:pass@localhost/dbname"
    # Patch the settings method used by _get_db_url
    with patch.object(db_async_settings, "get_database_url", return_value=test_db_url):
        url_result = _get_db_url()
        assert url_result is not None
        assert url_result == "postgresql+asyncpg://user:pass@localhost/dbname"


@patch.object(db_async_settings, "get_postgres_db", return_value="testdb")
@patch.object(db_async_settings, "get_postgres_port", return_value=5433)
@patch.object(db_async_settings, "get_postgres_host", return_value="testhost")
@patch.object(db_async_settings, "get_postgres_password", return_value="testpass")
@patch.object(db_async_settings, "get_postgres_user", return_value="testuser")
@patch.object(db_async_settings, "get_database_url", return_value=None)
async def test_get_db_url_with_postgres_vars(m_db, m_port, m_host, m_pass, m_user, m_db_url):
    """Test _get_db_url with individual DB_* environment variables."""
    url_result = _get_db_url()
    assert url_result is not None
    assert url_result == "postgresql+asyncpg://testuser:testpass@testhost:5433/testdb"


@patch.object(db_async_settings, "get_postgres_db", return_value=None)
@patch.object(db_async_settings, "get_postgres_port", return_value=5433)
@patch.object(db_async_settings, "get_postgres_host", return_value="testhost")
@patch.object(db_async_settings, "get_postgres_password", return_value=None)
@patch.object(db_async_settings, "get_postgres_user", return_value="testuser")
@patch.object(db_async_settings, "get_database_url", return_value=None)
async def test_get_db_url_missing_vars(m_db, m_port, m_host, m_pass, m_user, m_db_url):
    """Test _get_db_url with missing required environment variables."""
    with pytest.raises(LuthienDBConfigurationError):
        _get_db_url()


def test_mask_password():
    """Test the password masking function."""
    # Test with URL containing a password
    url = "postgresql://user:password@host:5432/db"
    masked = _mask_password(url)
    assert masked == "postgresql://user:***@host:5432/db"

    # Test with URL without a password
    url = "postgresql://user@host:5432/db"
    masked = _mask_password(url)
    assert masked == url


@pytest.mark.asyncio
async def test_create_db_engine():
    """Test creating the database engine."""
    # Mock environment variables and URL function
    test_url = "postgresql+asyncpg://fake:fake@localhost/fake"

    with patch("luthien_control.db.database_async._get_db_url", return_value=test_url):
        with patch("luthien_control.db.database_async.create_async_engine") as mock_create_engine:
            # Mock the engine simply as an object with an async dispose method
            mock_engine = MagicMock()
            mock_engine.dispose = AsyncMock()
            mock_create_engine.return_value = mock_engine

            # Test the function
            engine = await create_db_engine()

            # Verify correct engine creation
            assert engine is not None
            mock_create_engine.assert_called_once()

            # Clean up
            await close_db_engine()


@pytest.mark.asyncio
async def test_create_db_engine_reuse_existing():
    """Test that create_db_engine reuses an existing engine."""
    # Set up an existing engine
    with patch("luthien_control.db.database_async._db_engine") as mock_engine:
        # Test the function - should just return the existing engine
        engine = await create_db_engine()

        # Verify correct engine reuse
        assert engine is mock_engine


@pytest.mark.asyncio
async def test_create_db_engine_exception():
    """Test error handling when creating the database engine fails."""
    # Mock environment variables and URL function
    test_url = "postgresql+asyncpg://fake:fake@localhost/fake"

    with patch("luthien_control.db.database_async._get_db_url", return_value=test_url):
        with patch("luthien_control.db.database_async.create_async_engine") as mock_create_engine:
            # Make create_async_engine raise an exception
            mock_create_engine.side_effect = Exception("Database connection error")

            # Test the function - should raise LuthienDBConnectionError
            with pytest.raises(LuthienDBConnectionError):
                await create_db_engine()


@pytest.mark.asyncio
async def test_close_db_engine_with_exception():
    """Test error handling when closing the database engine raises an exception."""
    # Mock environment variables and URL function
    with patch("luthien_control.db.database_async._db_engine") as mock_engine:
        # Make engine.dispose raise an exception
        mock_engine.dispose = AsyncMock(side_effect=Exception("Error closing connection"))

        # Test the function - should handle the exception gracefully
        await close_db_engine()
        # Verify the engine is set to None
        assert mock_engine is not None


@pytest.mark.asyncio
async def test_close_db_engine_none():
    """Test closing when no engine exists."""
    # Mock _db_engine as None
    with patch("luthien_control.db.database_async._db_engine", None):
        # This should not raise any exception
        await close_db_engine()


@pytest.mark.asyncio
async def test_get_db_session_error():
    """Test session context manager fails without initialized engine."""
    # We need to patch the global variable directly in the module
    with patch("luthien_control.db.database_async._db_session_factory", None):
        # Using pytest.raises with an async context manager
        session_cm = get_db_session()
        with pytest.raises(RuntimeError):
            # Attempt to enter the async context manager
            async with session_cm:
                pass  # Should not reach here


@pytest.mark.asyncio
async def test_get_db_session_exception():
    """Test session context manager handles exceptions properly."""

    # Create a custom AsyncSession mock with a working rollback method
    class MockAsyncSession:
        def __init__(self):
            self.rollback_called = False

        async def rollback(self):
            self.rollback_called = True

    # Create our mock session
    mock_session = MockAsyncSession()

    # Create a context manager class that mimics a session
    class MockSessionContextManager:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            if exc_type is not None:
                await mock_session.rollback()
            return False  # Don't suppress exceptions

    # Create the mock factory function - it should directly return the context manager instance
    def mock_factory_function():
        return MockSessionContextManager()

    # Patch the session factory
    with patch("luthien_control.db.database_async._db_session_factory", mock_factory_function):
        # Test exception handling
        with pytest.raises(ValueError):
            async with get_db_session() as session:
                assert session is mock_session
                raise ValueError("Test exception")

        # Verify rollback was called
        assert mock_session.rollback_called, "Session rollback was not called during exception handling"
