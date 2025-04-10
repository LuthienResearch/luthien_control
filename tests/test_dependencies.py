import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, UTC

from fastapi import HTTPException, status

from luthien_control.dependencies import get_current_active_api_key
from luthien_control.db.models import ApiKey
from luthien_control.db.crud import get_api_key_by_value

# Mark all tests in this module as async
pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_api_key_crud():
    """Fixture to mock the get_api_key_by_value CRUD function."""
    return AsyncMock(spec=get_api_key_by_value)


async def test_get_current_active_api_key_success(mock_api_key_crud):
    """Test successful authentication with a valid, active key."""
    test_key_value = "valid-active-key"
    api_key_instance = ApiKey(
        id=1, key_value=test_key_value, name="Test Active", is_active=True, created_at=datetime.now(UTC), metadata_=None
    )
    mock_api_key_crud.return_value = api_key_instance

    # Patch the CRUD function within the dependencies module
    with patch("luthien_control.dependencies.get_api_key_by_value", mock_api_key_crud):
        result = await get_current_active_api_key(authorization=f"Bearer {test_key_value}")

    assert result == api_key_instance
    mock_api_key_crud.assert_awaited_once_with(test_key_value)


async def test_get_current_active_api_key_missing_header(mock_api_key_crud):
    """Test missing Authorization header."""
    with patch("luthien_control.dependencies.get_api_key_by_value", mock_api_key_crud):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_active_api_key(authorization=None)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Authorization header missing" in exc_info.value.detail
    assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}
    mock_api_key_crud.assert_not_awaited()


@pytest.mark.parametrize(
    "auth_header, expected_detail",
    [
        ("Token somekey", "Malformed header"),  # Wrong scheme
        ("Bearer", "Malformed header"),  # Missing key
        ("Bearer ", "Malformed header"),  # Empty key -> Also malformed (split has one part)
        ("Bearer some key", "Malformed header"),  # Key with space
    ],
)
async def test_get_current_active_api_key_malformed_header(mock_api_key_crud, auth_header, expected_detail):
    """Test various malformed Authorization headers."""
    with patch("luthien_control.dependencies.get_api_key_by_value", mock_api_key_crud):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_active_api_key(authorization=auth_header)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert expected_detail in exc_info.value.detail
    assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}
    mock_api_key_crud.assert_not_awaited()


async def test_get_current_active_api_key_not_found(mock_api_key_crud):
    """Test when the API key is not found in the database."""
    test_key_value = "not-found-key"
    mock_api_key_crud.return_value = None  # Simulate key not found

    with patch("luthien_control.dependencies.get_api_key_by_value", mock_api_key_crud):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_active_api_key(authorization=f"Bearer {test_key_value}")

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert "Unknown API Key" in exc_info.value.detail
    mock_api_key_crud.assert_awaited_once_with(test_key_value)


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
            await get_current_active_api_key(authorization=f"Bearer {test_key_value}")

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert "API Key is inactive" in exc_info.value.detail
    mock_api_key_crud.assert_awaited_once_with(test_key_value)


async def test_get_current_active_api_key_db_error(mock_api_key_crud):
    """Test when the underlying CRUD function raises an unexpected error."""
    test_key_value = "db-error-key"
    mock_api_key_crud.side_effect = Exception("Simulated DB connection error")

    with patch("luthien_control.dependencies.get_api_key_by_value", mock_api_key_crud):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_active_api_key(authorization=f"Bearer {test_key_value}")

    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "database issue" in exc_info.value.detail
    mock_api_key_crud.assert_awaited_once_with(test_key_value)
