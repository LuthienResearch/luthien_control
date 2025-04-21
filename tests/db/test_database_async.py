import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from luthien_control.db.database_async import (
    _get_db_url,
    close_db_engine,
    create_db_engine,
    get_db_session,
)


@pytest.mark.asyncio
async def test_get_db_url_with_database_url():
    """Test _get_db_url with DATABASE_URL environment variable."""
    with patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost/dbname"}):
        url_result = _get_db_url()
        assert url_result is not None
        url, connect_args = url_result
        assert url == "postgresql+asyncpg://user:pass@localhost/dbname"
        assert isinstance(connect_args, dict)


@pytest.mark.asyncio
async def test_get_db_url_with_postgres_vars():
    """Test _get_db_url with individual DB_* environment variables."""
    env_vars = {
        "DB_USER": "testuser",
        "DB_PASSWORD": "testpass",
        "DB_HOST": "testhost",
        "DB_PORT": "5433",
        "DB_NAME_NEW": "testdb",
    }
    with patch.dict(os.environ, env_vars, clear=True):
        url_result = _get_db_url()
        assert url_result is not None
        url, connect_args = url_result
        assert url == "postgresql+asyncpg://testuser:testpass@testhost:5433/testdb"
        assert isinstance(connect_args, dict)


@pytest.mark.asyncio
async def test_get_db_url_missing_vars():
    """Test _get_db_url with missing required environment variables."""
    with patch.dict(os.environ, {"DB_USER": "testuser"}, clear=True):
        url_result = _get_db_url()
        assert url_result is None



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
async def test_create_db_engine_url_error():
    """Test engine creation with missing URL."""
    with patch("luthien_control.db.database_async._get_db_url", return_value=None):
        engine = await create_db_engine()
        assert engine is None


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
                pass # Should not reach here


# We need setup/teardown to properly test session functionality
# For a real test we would need a database, but that's tested in the CRUD tests
