import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from luthien_control.db.database_async import (
    _get_log_db_url,
    _get_main_db_url,
    close_main_db_engine,
    create_main_db_engine,
    get_main_db_session,
)


@pytest.mark.asyncio
async def test_get_main_db_url_with_database_url():
    """Test _get_main_db_url with DATABASE_URL environment variable."""
    with patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost/dbname"}):
        url = _get_main_db_url()
        assert url == "postgresql+asyncpg://user:pass@localhost/dbname"


@pytest.mark.asyncio
async def test_get_main_db_url_with_postgres_vars():
    """Test _get_main_db_url with individual DB_* environment variables."""
    env_vars = {
        "DB_USER": "testuser",
        "DB_PASSWORD": "testpass",
        "DB_HOST": "testhost",
        "DB_PORT": "5433",
        "DB_NAME": "testdb",
    }
    with patch.dict(os.environ, env_vars, clear=True):
        url = _get_main_db_url()
        assert url == "postgresql+asyncpg://testuser:testpass@testhost:5433/testdb"


@pytest.mark.asyncio
async def test_get_main_db_url_missing_vars():
    """Test _get_main_db_url with missing required environment variables."""
    with patch.dict(os.environ, {"DB_USER": "testuser"}, clear=True):
        url = _get_main_db_url()
        assert url is None


@pytest.mark.asyncio
async def test_get_log_db_url():
    """Test _get_log_db_url with environment variables."""
    env_vars = {
        "LOG_DB_USER": "loguser",
        "LOG_DB_PASSWORD": "logpass",
        "LOG_DB_HOST": "loghost",
        "LOG_DB_PORT": "5433",
        "LOG_DB_NAME": "logdb",
    }
    with patch.dict(os.environ, env_vars, clear=True):
        url = _get_log_db_url()
        assert url == "postgresql+asyncpg://loguser:logpass@loghost:5433/logdb"


@pytest.mark.asyncio
async def test_get_log_db_url_missing_vars():
    """Test _get_log_db_url with missing required environment variables."""
    with patch.dict(os.environ, {"LOG_DB_USER": "loguser"}, clear=True):
        url = _get_log_db_url()
        assert url is None


@pytest.mark.asyncio
async def test_create_main_db_engine():
    """Test creating the main database engine."""
    # Mock environment variables and URL function
    test_url = "postgresql+asyncpg://fake:fake@localhost/fake"

    with patch("luthien_control.db.database_async._get_main_db_url", return_value=test_url):
        with patch("luthien_control.db.database_async.create_async_engine") as mock_create_engine:
            # Mock the engine simply as an object with an async dispose method
            mock_engine = MagicMock()
            mock_engine.dispose = AsyncMock()
            mock_create_engine.return_value = mock_engine

            # Test the function
            engine = await create_main_db_engine()

            # Verify correct engine creation
            assert engine is not None
            mock_create_engine.assert_called_once()

            # Clean up
            await close_main_db_engine()


@pytest.mark.asyncio
async def test_create_main_db_engine_url_error():
    """Test engine creation with missing URL."""
    with patch("luthien_control.db.database_async._get_main_db_url", return_value=None):
        engine = await create_main_db_engine()
        assert engine is None


@pytest.mark.asyncio
async def test_get_main_db_session_error():
    """Test session generator fails without initialized engine."""
    # We need to patch the global variable directly in the module
    with patch("luthien_control.db.database_async._main_db_session_factory", None):
        # Using pytest.raises for an async generator is a bit tricky
        # We need to consume the generator to trigger the exception
        session_gen = get_main_db_session()
        with pytest.raises(RuntimeError):
            # Need to use anext() to get the first item from async generator
            await session_gen.__anext__()


# We need setup/teardown to properly test session functionality
# For a real test we would need a database, but that's tested in the CRUD tests
