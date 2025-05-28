from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from luthien_control.db.database_async import (
    _get_db_url,
    close_db_engine,
    create_db_engine,
    get_db_session,
)
from luthien_control.db.database_async import settings as db_async_settings
from luthien_control.exceptions import LuthienDBConfigurationError


@pytest.mark.asyncio
async def test_get_db_url_with_database_url():
    """Test _get_db_url with DATABASE_URL environment variable."""
    test_db_url = "postgresql://user:pass@localhost/dbname"
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


@pytest.mark.asyncio
async def test_create_db_engine():
    """Test creating the database engine."""
    # Mock environment variables and URL function
    test_url = "postgresql+asyncpg://fake:fake@localhost/fake"
    test_connect_args = {}

    with patch("luthien_control.db.database_async._get_db_url", return_value=(test_url, test_connect_args)):
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


# We need setup/teardown to properly test session functionality
# For a real test we would need a database, but that's tested in the CRUD tests
