import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import Request as HttpxRequest
from luthien_control.control_policy.client_api_key_auth import (
    API_KEY_HEADER,
    BEARER_PREFIX,
    ClientApiKeyAuthPolicy,
)
from luthien_control.control_policy.exceptions import (
    ClientAuthenticationError,
    ClientAuthenticationNotFoundError,
    NoRequestError,
)
from luthien_control.core.transaction_context import TransactionContext
from luthien_control.db.client_api_key_crud import get_api_key_by_value
from luthien_control.db.sqlmodel_models import ClientApiKey
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def mock_db_session_cm():
    """Fixture to mock the get_db_session async context manager defined in database_async."""
    # Patch the canonical path to the function
    with patch("luthien_control.control_policy.client_api_key_auth.get_db_session") as mock_get_cm:
        mock_session = AsyncMock(spec=AsyncSession)
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_get_cm.return_value = mock_context
        yield mock_get_cm, mock_session


@pytest.fixture
def transaction_context():
    """Provides a basic TransactionContext instance with a unique ID."""
    return TransactionContext(transaction_id=f"test-tx-{uuid.uuid4()}")


@pytest.fixture
def transaction_context_with_request(transaction_context):
    """Provides a TransactionContext with a mock HttpxRequest attached."""
    mock_request = HttpxRequest(
        method="GET",
        url="http://test.com",
    )
    transaction_context.request = mock_request
    return transaction_context


@pytest.mark.asyncio
async def test_apply_no_request_raises_error(transaction_context):
    """Verify NoRequestError is raised if context has no fastapi_request."""
    mock_api_key_lookup = AsyncMock()
    policy = ClientApiKeyAuthPolicy(api_key_lookup=mock_api_key_lookup)

    with pytest.raises(NoRequestError):
        await policy.apply(transaction_context)


@pytest.mark.asyncio
async def test_apply_missing_header_raises_error(transaction_context_with_request):
    """Verify ClientAuthenticationNotFoundError is raised if header is missing."""
    mock_api_key_lookup = AsyncMock()
    policy = ClientApiKeyAuthPolicy(api_key_lookup=mock_api_key_lookup)

    transaction_context_with_request.request.headers = {}  # Set empty headers

    with pytest.raises(ClientAuthenticationNotFoundError):
        await policy.apply(transaction_context_with_request)
    assert transaction_context_with_request.response is not None
    assert transaction_context_with_request.response.status_code == 401


@pytest.mark.asyncio
async def test_apply_key_not_found_raises_error(mock_db_session_cm, transaction_context_with_request):
    """Verify ClientAuthenticationError is raised if key is not found in DB."""
    mock_get_session_cm, mock_session = mock_db_session_cm
    mock_api_key_lookup = AsyncMock(return_value=None)  # Key not found
    policy = ClientApiKeyAuthPolicy(api_key_lookup=mock_api_key_lookup)

    test_api_key = "non-existent-key"
    headers = {API_KEY_HEADER: f"{BEARER_PREFIX}{test_api_key}"}
    transaction_context_with_request.request.headers = headers  # Set headers

    with pytest.raises(ClientAuthenticationError, match="Invalid API Key"):
        await policy.apply(transaction_context_with_request)
    mock_api_key_lookup.assert_awaited_once_with(mock_session, test_api_key)
    assert transaction_context_with_request.response is not None
    assert transaction_context_with_request.response.status_code == 401


@pytest.mark.asyncio
async def test_apply_inactive_key_raises_error(mock_db_session_cm, transaction_context_with_request):
    """Verify ClientAuthenticationError is raised if key is inactive."""
    mock_get_session_cm, mock_session = mock_db_session_cm
    mock_db_key = MagicMock(spec=ClientApiKey)
    mock_db_key.is_active = False
    mock_db_key.name = "InactiveKey"
    mock_db_key.id = 2
    mock_api_key_lookup = AsyncMock(return_value=mock_db_key)
    policy = ClientApiKeyAuthPolicy(api_key_lookup=mock_api_key_lookup)

    test_api_key = "inactive-key-456"
    headers = {API_KEY_HEADER: f"{BEARER_PREFIX}{test_api_key}"}
    transaction_context_with_request.request.headers = headers  # Set headers

    with pytest.raises(ClientAuthenticationError, match="Inactive API Key"):
        await policy.apply(transaction_context_with_request)
    mock_api_key_lookup.assert_awaited_once_with(mock_session, test_api_key)
    assert transaction_context_with_request.response is not None
    assert transaction_context_with_request.response.status_code == 401


@pytest.mark.asyncio
async def test_apply_no_bearer_prefix_success(mock_db_session_cm, transaction_context_with_request):
    """Verify that apply works correctly if 'Bearer ' prefix is missing."""
    mock_get_session_cm, mock_session = mock_db_session_cm
    mock_api_key_lookup = AsyncMock()
    mock_db_key = MagicMock(spec=ClientApiKey)
    mock_db_key.is_active = True
    mock_db_key.name = "TestKeyNoBearer"
    mock_db_key.id = 3
    mock_api_key_lookup.return_value = mock_db_key
    policy = ClientApiKeyAuthPolicy(api_key_lookup=mock_api_key_lookup)

    test_api_key = "key-without-bearer-prefix"
    headers = {API_KEY_HEADER: test_api_key}  # No Bearer prefix
    transaction_context_with_request.request.headers = headers  # Set headers

    result_context = await policy.apply(transaction_context_with_request)

    mock_api_key_lookup.assert_awaited_once_with(mock_session, test_api_key)
    assert result_context == transaction_context_with_request
    assert transaction_context_with_request.response is None


@pytest.mark.asyncio
async def test_apply_valid_active_key_success(mock_db_session_cm, transaction_context_with_request):
    """Verify apply succeeds with a valid, active API key and Bearer prefix."""
    mock_get_session_cm, mock_session = mock_db_session_cm
    mock_api_key_lookup = AsyncMock()
    mock_db_key = MagicMock(spec=ClientApiKey)
    mock_db_key.is_active = True
    mock_db_key.name = "TestKeyActive"
    mock_db_key.id = 1
    mock_api_key_lookup.return_value = mock_db_key
    policy = ClientApiKeyAuthPolicy(api_key_lookup=mock_api_key_lookup)

    test_api_key = "valid-active-key-123"
    headers = {API_KEY_HEADER: f"{BEARER_PREFIX}{test_api_key}"}
    transaction_context_with_request.request.headers = headers  # Set headers

    result_context = await policy.apply(transaction_context_with_request)

    mock_api_key_lookup.assert_awaited_once_with(mock_session, test_api_key)
    assert result_context == transaction_context_with_request
    assert transaction_context_with_request.response is None


@pytest.mark.asyncio
async def test_client_api_key_auth_policy_serialization():
    """Test that ClientApiKeyAuthPolicy can be serialized and deserialized correctly."""
    # Arrange
    # ClientApiKeyAuthPolicy requires an api_key_lookup function on init
    original_policy = ClientApiKeyAuthPolicy(api_key_lookup=get_api_key_by_value)

    # Act
    serialized_data = original_policy.serialize()
    # Pass a dummy dependency for deserialization test
    dummy_lookup = MagicMock()
    rehydrated_policy = await ClientApiKeyAuthPolicy.from_serialized(serialized_data, api_key_lookup=dummy_lookup)

    # Assert
    assert isinstance(serialized_data, dict)  # Check against dict, not type alias
    assert isinstance(rehydrated_policy, ClientApiKeyAuthPolicy)
    # Check if the rehydrated policy uses the correct lookup function
    assert rehydrated_policy._api_key_lookup is dummy_lookup
