from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request
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
from luthien_control.core.context import TransactionContext
from luthien_control.db.sqlmodel_models import ClientApiKey
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
@patch("luthien_control.control_policy.client_api_key_auth.get_db_session")
async def test_apply_calls_lookup_with_correct_args(mock_get_session_cm):
    """
    Verify that apply calls the api_key_lookup with the session and key value.
    """
    # Arrange
    mock_session = AsyncMock(spec=AsyncSession)

    # Set up the mock context manager to return our session
    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_session
    mock_get_session_cm.return_value = mock_context

    mock_api_key_lookup = AsyncMock()
    mock_db_key = MagicMock(spec=ClientApiKey)
    mock_db_key.is_active = True
    mock_db_key.name = "TestKey"
    mock_db_key.id = 1
    mock_api_key_lookup.return_value = mock_db_key

    policy = ClientApiKeyAuthPolicy(api_key_lookup=mock_api_key_lookup)

    test_api_key = "test-secret-key-123"
    headers = {API_KEY_HEADER: f"{BEARER_PREFIX}{test_api_key}"}
    mock_scope = {"type": "http", "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()]}
    mock_request = Request(scope=mock_scope)

    context = TransactionContext(transaction_id="test-tx-correct-args")
    context.fastapi_request = mock_request

    # Act
    await policy.apply(context)

    # Assert
    mock_api_key_lookup.assert_awaited_once_with(mock_session, test_api_key)


@pytest.mark.asyncio
async def test_apply_no_request_raises_error():
    """Verify NoRequestError is raised if context has no fastapi_request."""
    # We don't need to mock get_db_session here since the code raises
    # an error before trying to get a session
    mock_api_key_lookup = AsyncMock()
    policy = ClientApiKeyAuthPolicy(api_key_lookup=mock_api_key_lookup)
    context = TransactionContext(transaction_id="test-tx-no-request")
    context.fastapi_request = None

    with pytest.raises(NoRequestError):
        await policy.apply(context)


@pytest.mark.asyncio
async def test_apply_missing_header_raises_error():
    """Verify ClientAuthenticationNotFoundError is raised if header is missing."""
    # We don't need to mock get_db_session here since the code raises
    # an error before trying to get a session
    mock_api_key_lookup = AsyncMock()
    policy = ClientApiKeyAuthPolicy(api_key_lookup=mock_api_key_lookup)

    headers = {} # Missing header
    mock_scope = {"type": "http", "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()]}
    mock_request = Request(scope=mock_scope)

    context = TransactionContext(transaction_id="test-tx-missing-header")
    context.fastapi_request = mock_request

    with pytest.raises(ClientAuthenticationNotFoundError):
        await policy.apply(context)
    assert context.response is not None
    assert context.response.status_code == 401
    # assert b"Missing API key" in context.response.body # Can't easily check body without more setup


@pytest.mark.asyncio
@patch("luthien_control.control_policy.client_api_key_auth.get_db_session")
async def test_apply_key_not_found_raises_error(mock_get_session_cm):
    """Verify ClientAuthenticationError is raised if key is not found in DB."""
    mock_session = AsyncMock(spec=AsyncSession)

    # Set up the mock context manager
    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_session
    mock_get_session_cm.return_value = mock_context

    mock_api_key_lookup = AsyncMock(return_value=None) # Key not found

    policy = ClientApiKeyAuthPolicy(api_key_lookup=mock_api_key_lookup)

    test_api_key = "non-existent-key"
    headers = {API_KEY_HEADER: f"{BEARER_PREFIX}{test_api_key}"}
    mock_scope = {"type": "http", "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()]}
    mock_request = Request(scope=mock_scope)

    context = TransactionContext(transaction_id="test-tx-key-not-found")
    context.fastapi_request = mock_request

    with pytest.raises(ClientAuthenticationError, match="Invalid API Key"):
        await policy.apply(context)
    mock_api_key_lookup.assert_awaited_once_with(mock_session, test_api_key)
    assert context.response is not None
    assert context.response.status_code == 401
    # assert b"Invalid API Key" in context.response.body


@pytest.mark.asyncio
@patch("luthien_control.control_policy.client_api_key_auth.get_db_session")
async def test_apply_inactive_key_raises_error(mock_get_session_cm):
    """Verify ClientAuthenticationError is raised if key is inactive."""
    mock_session = AsyncMock(spec=AsyncSession)

    # Set up the mock context manager
    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_session
    mock_get_session_cm.return_value = mock_context

    mock_db_key = MagicMock(spec=ClientApiKey)
    mock_db_key.is_active = False # Key is inactive
    mock_db_key.name = "InactiveKey"
    mock_db_key.id = 2
    mock_api_key_lookup = AsyncMock(return_value=mock_db_key)

    policy = ClientApiKeyAuthPolicy(api_key_lookup=mock_api_key_lookup)

    test_api_key = "inactive-key-456"
    headers = {API_KEY_HEADER: f"{BEARER_PREFIX}{test_api_key}"}
    mock_scope = {"type": "http", "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()]}
    mock_request = Request(scope=mock_scope)

    context = TransactionContext(transaction_id="test-tx-inactive-key")
    context.fastapi_request = mock_request

    with pytest.raises(ClientAuthenticationError, match="Inactive API Key"):
        await policy.apply(context)
    mock_api_key_lookup.assert_awaited_once_with(mock_session, test_api_key)
    assert context.response is not None
    assert context.response.status_code == 401
    # assert b"Inactive API Key" in context.response.body


@pytest.mark.asyncio
@patch("luthien_control.control_policy.client_api_key_auth.get_db_session")
async def test_apply_no_bearer_prefix_success(mock_get_session_cm):
    """Verify that apply works correctly if 'Bearer ' prefix is missing."""
    # Arrange
    mock_session = AsyncMock(spec=AsyncSession)

    # Set up the mock context manager
    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_session
    mock_get_session_cm.return_value = mock_context

    mock_api_key_lookup = AsyncMock()
    mock_db_key = MagicMock(spec=ClientApiKey)
    mock_db_key.is_active = True
    mock_db_key.name = "TestKeyNoBearer"
    mock_db_key.id = 3
    mock_api_key_lookup.return_value = mock_db_key

    policy = ClientApiKeyAuthPolicy(api_key_lookup=mock_api_key_lookup)

    test_api_key = "key-without-bearer-prefix"
    headers = {API_KEY_HEADER: test_api_key} # No Bearer prefix
    mock_scope = {"type": "http", "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()]}
    mock_request = Request(scope=mock_scope)

    context = TransactionContext(transaction_id="test-tx-no-bearer")
    context.fastapi_request = mock_request

    # Act
    result_context = await policy.apply(context)

    # Assert
    mock_api_key_lookup.assert_awaited_once_with(mock_session, test_api_key)
    assert result_context == context # Should return the same context on success
    assert context.response is None # Response should not be set on success
