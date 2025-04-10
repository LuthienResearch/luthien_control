from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from luthien_control.db.crud import get_api_key_by_value
from luthien_control.db.models import ApiKey
from luthien_control.dependencies import get_current_active_api_key

# Mark all tests in this module as async
pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_api_key_crud():
    """Fixture to mock the get_api_key_by_value CRUD function."""
    return AsyncMock(spec=get_api_key_by_value)


@pytest.mark.asyncio
async def test_get_current_active_api_key_success(mock_api_key_crud):
    """Test successful authentication with a valid, active key (including Bearer prefix)."""
    test_key_value = "valid-active-key"
    api_key_instance = ApiKey(
        id=1, key_value=test_key_value, name="Test Active", is_active=True, created_at=datetime.now(UTC), metadata_=None
    )
    mock_api_key_crud.return_value = api_key_instance

    # Patch the CRUD function within the dependencies module
    with patch("luthien_control.dependencies.get_api_key_by_value", mock_api_key_crud):
        # Call with the expected input after dependency resolution (Bearer prefix is handled)
        result = await get_current_active_api_key(api_key=f"Bearer {test_key_value}")

    assert result == api_key_instance
    mock_api_key_crud.assert_awaited_once_with(test_key_value)  # Verify CRUD called with key stripped


@pytest.mark.asyncio
async def test_get_current_active_api_key_success_no_prefix(mock_api_key_crud):
    """Test successful authentication with a valid, active key (no Bearer prefix)."""
    test_key_value = "valid-active-key-no-prefix"
    api_key_instance = ApiKey(
        id=1,
        key_value=test_key_value,
        name="Test Active No Prefix",
        is_active=True,
        created_at=datetime.now(UTC),
        metadata_=None,
    )
    mock_api_key_crud.return_value = api_key_instance

    with patch("luthien_control.dependencies.get_api_key_by_value", mock_api_key_crud):
        result = await get_current_active_api_key(api_key=test_key_value)

    assert result == api_key_instance
    mock_api_key_crud.assert_awaited_once_with(test_key_value)


@pytest.mark.asyncio
async def test_get_current_active_api_key_missing_key(mock_api_key_crud):
    """Test missing API key (dependency would pass None or empty string)."""
    with patch("luthien_control.dependencies.get_api_key_by_value", mock_api_key_crud):
        with pytest.raises(HTTPException) as exc_info:
            # Simulate missing key from dependency
            await get_current_active_api_key(api_key=None)

    assert exc_info.value.status_code == 401
    assert "Missing API key" in exc_info.value.detail
    mock_api_key_crud.assert_not_awaited()

    with patch("luthien_control.dependencies.get_api_key_by_value", mock_api_key_crud):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_active_api_key(api_key="")  # Empty string case

    assert exc_info.value.status_code == 401
    assert "Missing API key" in exc_info.value.detail
    mock_api_key_crud.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_current_active_api_key_not_found(mock_api_key_crud):
    """Test when the API key is not found in the database."""
    test_key_value = "not-found-key"
    mock_api_key_crud.return_value = None  # Simulate key not found

    with patch("luthien_control.dependencies.get_api_key_by_value", mock_api_key_crud):
        with pytest.raises(HTTPException) as exc_info:
            # Pass the key value directly
            await get_current_active_api_key(api_key=test_key_value)

    assert exc_info.value.status_code == 401
    assert "Invalid API Key" in exc_info.value.detail
    mock_api_key_crud.assert_awaited_once_with(test_key_value)


@pytest.mark.asyncio
async def test_get_current_active_api_key_inactive(mock_api_key_crud):
    """Test when the API key is found but is inactive."""
    test_key_value = "valid-inactive-key"
    api_key_instance = ApiKey(
        id=2,
        key_value=test_key_value,
        name="Test Inactive",
        is_active=False,
        created_at=datetime.now(UTC),
        metadata_=None,
    )
    mock_api_key_crud.return_value = api_key_instance

    with patch("luthien_control.dependencies.get_api_key_by_value", mock_api_key_crud):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_active_api_key(api_key=test_key_value)

    assert exc_info.value.status_code == 401
    assert "Inactive API Key" in exc_info.value.detail
    mock_api_key_crud.assert_awaited_once_with(test_key_value)


@pytest.mark.asyncio
async def test_get_current_active_api_key_db_error(mock_api_key_crud):
    """Test when the underlying CRUD function raises an unexpected error."""
    test_key_value = "db-error-key"
    # Ensure the mock raises the error when awaited
    mock_api_key_crud.side_effect = Exception("Simulated DB connection error")

    with patch("luthien_control.dependencies.get_api_key_by_value", mock_api_key_crud):
        # Expect the underlying Exception, as the dependency function doesn't catch it.
        with pytest.raises(Exception, match="Simulated DB connection error"):
            await get_current_active_api_key(api_key=test_key_value)

    mock_api_key_crud.assert_awaited_once_with(test_key_value)
