import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import asyncpg
import pytest
from luthien_control.db.crud import get_api_key_by_value
from luthien_control.db.models import ApiKey

# Mark all tests in this module as async
pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_db_pool():
    """Fixture to mock the database pool and connection."""
    mock_conn = AsyncMock(spec=asyncpg.Connection)
    mock_pool = MagicMock(spec=asyncpg.Pool)
    # Configure the pool's acquire method to return an async context manager
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    mock_pool.acquire.return_value.__aexit__.return_value = None  # Simulate successful exit
    return mock_pool, mock_conn


async def test_get_api_key_by_value_found_active(mock_db_pool):
    """Test fetching an existing, active API key."""
    mock_pool, mock_conn = mock_db_pool
    test_key = "test-key-active"
    now = datetime.now(UTC)
    mock_metadata_dict = {"user": "test"}
    mock_metadata_str = json.dumps(mock_metadata_dict)

    # Simulate fetchrow returning a dictionary matching the ApiKey model structure
    mock_record_dict = {
        "id": 1,
        "key_value": test_key,
        "name": "Test Key Active",
        "is_active": True,
        "created_at": now,
        "metadata_": mock_metadata_str,  # DB returns JSON as string
    }
    # asyncpg returns a Record object, but we mock fetchrow to return the dict
    # This simplifies testing the Pydantic model creation
    mock_conn.fetchrow.return_value = mock_record_dict

    # Patch get_main_db_pool to return our mock pool
    with patch("luthien_control.db.crud.get_main_db_pool", return_value=mock_pool):
        result = await get_api_key_by_value(test_key)

    assert isinstance(result, ApiKey)
    assert result.key_value == test_key
    assert result.name == "Test Key Active"
    assert result.is_active is True
    assert result.created_at == now
    assert result.metadata_ == mock_metadata_dict  # Check deserialized metadata

    # Assert the SQL query was called correctly, ignoring whitespace differences
    mock_conn.fetchrow.assert_awaited_once()
    call_args = mock_conn.fetchrow.await_args
    actual_query = call_args[0][0]
    actual_param = call_args[0][1]

    expected_query = """
        SELECT id, key_value, name, is_active, created_at, metadata_
        FROM api_keys
        WHERE key_value = $1
    """

    # Normalize whitespace (split by any whitespace, join with single space)
    normalized_actual = " ".join(actual_query.split())
    normalized_expected = " ".join(expected_query.split())

    assert normalized_actual == normalized_expected
    assert actual_param == test_key


async def test_get_api_key_by_value_not_found(mock_db_pool):
    """Test fetching a non-existent API key."""
    mock_pool, mock_conn = mock_db_pool
    test_key = "test-key-nonexistent"

    # Simulate fetchrow returning None (key not found)
    mock_conn.fetchrow.return_value = None

    with patch("luthien_control.db.crud.get_main_db_pool", return_value=mock_pool):
        result = await get_api_key_by_value(test_key)

    assert result is None
    mock_conn.fetchrow.assert_awaited_once()


async def test_get_api_key_by_value_db_error(mock_db_pool):
    """Test behavior when the database query fails."""
    mock_pool, mock_conn = mock_db_pool
    test_key = "test-key-error"

    # Simulate fetchrow raising an exception
    mock_conn.fetchrow.side_effect = asyncpg.PostgresError("Simulated DB error")

    with patch("luthien_control.db.crud.get_main_db_pool", return_value=mock_pool):
        result = await get_api_key_by_value(test_key)

    assert result is None
    mock_conn.fetchrow.assert_awaited_once()


async def test_get_api_key_by_value_pool_not_initialized():
    """Test behavior when the DB pool is not initialized."""
    test_key = "test-key-no-pool"

    # Patch get_main_db_pool to raise RuntimeError
    with patch("luthien_control.db.crud.get_main_db_pool", side_effect=RuntimeError("Pool not initialized")):
        result = await get_api_key_by_value(test_key)

    assert result is None


async def test_get_api_key_by_value_found_inactive(mock_db_pool):
    """Test fetching an existing, but inactive API key (should still return it)."""
    mock_pool, mock_conn = mock_db_pool
    test_key = "test-key-inactive"
    now = datetime.now(UTC)

    mock_record_dict = {
        "id": 2,
        "key_value": test_key,
        "name": "Test Key Inactive",
        "is_active": False,
        "created_at": now,
        "metadata_": None,
    }
    mock_conn.fetchrow.return_value = mock_record_dict

    with patch("luthien_control.db.crud.get_main_db_pool", return_value=mock_pool):
        result = await get_api_key_by_value(test_key)

    assert isinstance(result, ApiKey)
    assert result.key_value == test_key
    assert result.is_active is False


async def test_get_api_key_by_value_invalid_metadata_json(mock_db_pool):
    """Test fetching a key where metadata is invalid JSON."""
    mock_pool, mock_conn = mock_db_pool
    test_key = "test-key-bad-json"
    now = datetime.now(UTC)
    mock_metadata_str = "this is not valid json"

    mock_record_dict = {
        "id": 3,
        "key_value": test_key,
        "name": "Test Key Bad JSON",
        "is_active": True,
        "created_at": now,
        "metadata_": mock_metadata_str,
    }
    mock_conn.fetchrow.return_value = mock_record_dict

    with patch("luthien_control.db.crud.get_main_db_pool", return_value=mock_pool):
        # Patch logger.warning to check if it's called
        with patch("luthien_control.db.crud.logger.warning") as mock_warning:
            result = await get_api_key_by_value(test_key)

    assert isinstance(result, ApiKey)
    assert result.key_value == test_key
    assert result.metadata_ is None  # Should be set to None due to parsing error
    mock_warning.assert_called_once()
    # Check that the specific warning about invalid JSON was logged
    assert "Invalid JSON in metadata" in mock_warning.call_args[0][0]


async def test_get_api_key_by_value_found(mock_db_pool):
    mock_pool, mock_conn = mock_db_pool
    test_key = "test-value"
    expected_record = {
        "id": 1,
        "key_value": test_key,
        "name": "Test Key",
        "is_active": True,
        "created_at": datetime.now(UTC),
        "metadata_": None,
    }
    mock_conn.fetchrow.return_value = expected_record

    with patch("luthien_control.db.crud.get_main_db_pool", return_value=mock_pool):
        result_key = await get_api_key_by_value(test_key)

    assert result_key == ApiKey(**expected_record)  # type: ignore

    # Assert the SQL query was called correctly, ignoring whitespace differences
    mock_conn.fetchrow.assert_awaited_once()
    call_args = mock_conn.fetchrow.await_args
    actual_query = call_args[0][0]
    actual_param = call_args[0][1]

    expected_query = """
        SELECT id, key_value, name, is_active, created_at, metadata_
        FROM api_keys
        WHERE key_value = $1
    """

    # Normalize whitespace (split by any whitespace, join with single space)
    normalized_actual = " ".join(actual_query.split())
    normalized_expected = " ".join(expected_query.split())

    assert normalized_actual == normalized_expected
    assert actual_param == test_key
