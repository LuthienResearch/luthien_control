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


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock(spec=AsyncSession)


@pytest.mark.asyncio
async def test_apply_no_request_raises_error(transaction_context, mock_session):
    """Verify NoRequestError is raised if context has no request."""
    policy = ClientApiKeyAuthPolicy()

    with pytest.raises(NoRequestError):
        await policy.apply(transaction_context, session=mock_session)


@pytest.mark.asyncio
async def test_apply_missing_header_raises_error(transaction_context_with_request, mock_session):
    """Verify ClientAuthenticationNotFoundError is raised if header is missing."""
    policy = ClientApiKeyAuthPolicy()

    transaction_context_with_request.request.headers = {}  # Set empty headers

    with pytest.raises(ClientAuthenticationNotFoundError):
        await policy.apply(transaction_context_with_request, session=mock_session)
    assert transaction_context_with_request.response is not None
    assert transaction_context_with_request.response.status_code == 401


@pytest.mark.asyncio
async def test_apply_key_not_found_raises_error(transaction_context_with_request, mock_session):
    """Verify ClientAuthenticationError is raised if key is not found in DB."""
    with patch("luthien_control.control_policy.client_api_key_auth.get_api_key_by_value") as mock_get_key_func:
        mock_get_key_func.return_value = None  # Key not found
        policy = ClientApiKeyAuthPolicy()

        test_api_key = "non-existent-key"
        headers = {API_KEY_HEADER: f"{BEARER_PREFIX}{test_api_key}"}
        transaction_context_with_request.request.headers = headers

        with pytest.raises(ClientAuthenticationError, match="Invalid API Key"):
            await policy.apply(transaction_context_with_request, session=mock_session)

        mock_get_key_func.assert_awaited_once_with(mock_session, test_api_key)

    assert transaction_context_with_request.response is not None
    assert transaction_context_with_request.response.status_code == 401


@pytest.mark.asyncio
async def test_apply_inactive_key_raises_error(transaction_context_with_request, mock_session):
    """Verify ClientAuthenticationError is raised if key is inactive."""
    mock_db_key = MagicMock(spec=ClientApiKey)
    mock_db_key.is_active = False
    mock_db_key.name = "InactiveKey"
    mock_db_key.id = 2

    with patch("luthien_control.control_policy.client_api_key_auth.get_api_key_by_value") as mock_get_key_func:
        mock_get_key_func.return_value = mock_db_key  # Return inactive key
        policy = ClientApiKeyAuthPolicy()

        test_api_key = "inactive-key-456"
        headers = {API_KEY_HEADER: f"{BEARER_PREFIX}{test_api_key}"}
        transaction_context_with_request.request.headers = headers

        with pytest.raises(ClientAuthenticationError, match="Inactive API Key"):
            await policy.apply(transaction_context_with_request, session=mock_session)

        mock_get_key_func.assert_awaited_once_with(mock_session, test_api_key)

    assert transaction_context_with_request.response is not None
    assert transaction_context_with_request.response.status_code == 401


@pytest.mark.asyncio
async def test_apply_no_bearer_prefix_success(transaction_context_with_request, mock_session):
    """Verify that apply works correctly if 'Bearer ' prefix is missing."""
    mock_db_key = MagicMock(spec=ClientApiKey)
    mock_db_key.is_active = True
    mock_db_key.name = "TestKeyNoBearer"
    mock_db_key.id = 3

    with patch("luthien_control.control_policy.client_api_key_auth.get_api_key_by_value") as mock_get_key_func:
        mock_get_key_func.return_value = mock_db_key  # Return active key
        policy = ClientApiKeyAuthPolicy()

        test_api_key = "key-without-bearer-prefix"
        headers = {API_KEY_HEADER: test_api_key}  # No Bearer prefix
        transaction_context_with_request.request.headers = headers

        result_context = await policy.apply(transaction_context_with_request, session=mock_session)

        mock_get_key_func.assert_awaited_once_with(mock_session, test_api_key)

    assert result_context == transaction_context_with_request
    assert transaction_context_with_request.response is None


@pytest.mark.asyncio
async def test_apply_valid_active_key_success(transaction_context_with_request, mock_session):
    """Verify apply succeeds with a valid, active API key and Bearer prefix."""
    mock_db_key = MagicMock(spec=ClientApiKey)
    mock_db_key.is_active = True
    mock_db_key.name = "TestKeyActive"
    mock_db_key.id = 1

    with patch("luthien_control.control_policy.client_api_key_auth.get_api_key_by_value") as mock_get_key_func:
        mock_get_key_func.return_value = mock_db_key  # Return active key
        policy = ClientApiKeyAuthPolicy()

        test_api_key_value = "valid-active-key-123"
        headers = {API_KEY_HEADER: f"{BEARER_PREFIX}{test_api_key_value}"}
        transaction_context_with_request.request.headers = headers

        result_context = await policy.apply(transaction_context_with_request, session=mock_session)

        mock_get_key_func.assert_awaited_once_with(mock_session, test_api_key_value)

    assert result_context == transaction_context_with_request
    assert transaction_context_with_request.response is None


@pytest.mark.asyncio
async def test_client_api_key_auth_policy_serialization():
    """Test that ClientApiKeyAuthPolicy can be serialized and deserialized correctly."""
    # Arrange
    # ClientApiKeyAuthPolicy no longer requires api_key_lookup on init
    original_policy = ClientApiKeyAuthPolicy(name="TestAuthPolicy")

    # Act
    serialized_data = original_policy.serialize()
    # No dependencies are needed for deserialization anymore
    rehydrated_policy = await ClientApiKeyAuthPolicy.from_serialized(serialized_data)

    # Assert
    assert isinstance(serialized_data, dict)  # Check against dict, not type alias
    assert serialized_data == {"name": "TestAuthPolicy"}
    assert isinstance(rehydrated_policy, ClientApiKeyAuthPolicy)
    assert rehydrated_policy.name == "TestAuthPolicy"
    # No internal _api_key_lookup to check anymore
    # assert rehydrated_policy._api_key_lookup is dummy_lookup
