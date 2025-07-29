"""Tests for SetBackendPolicy with dual-mode transactions."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from luthien_control.api.openai_chat_completions.datatypes import Message
from luthien_control.api.openai_chat_completions.request import OpenAIChatCompletionsRequest
from luthien_control.control_policy.set_backend_policy import SetBackendPolicy
from luthien_control.core.raw_request import RawRequest
from luthien_control.core.request import Request
from luthien_control.core.transaction import Transaction
from psygnal.containers import EventedList


@pytest.mark.asyncio
class TestSetBackendPolicyDualMode:
    """Test SetBackendPolicy with both OpenAI and raw transactions."""

    async def test_set_backend_openai_transaction(self):
        """Test SetBackendPolicy with OpenAI transaction."""
        # Create OpenAI transaction
        openai_request = Request(
            payload=OpenAIChatCompletionsRequest(
                model="gpt-3.5-turbo", messages=EventedList([Message(role="user", content="Hello")])
            ),
            api_endpoint="https://original.com",
            api_key="test-key",
        )
        transaction = Transaction(openai_request=openai_request)

        # Apply policy
        policy = SetBackendPolicy(backend_url="https://new-backend.com")
        mock_container = MagicMock()
        mock_session = AsyncMock()
        result = await policy.apply(transaction, mock_container, mock_session)

        # Verify backend URL was set for OpenAI request
        assert result.openai_request is not None
        assert result.openai_request.api_endpoint == "https://new-backend.com"

    async def test_set_backend_raw_transaction(self):
        """Test SetBackendPolicy with raw transaction."""
        # Create raw transaction
        raw_request = RawRequest(method="GET", path="v1/models", api_key="test-key", backend_url=None)
        transaction = Transaction(raw_request=raw_request)

        # Apply policy
        policy = SetBackendPolicy(backend_url="https://new-backend.com")
        mock_container = MagicMock()
        mock_session = AsyncMock()
        result = await policy.apply(transaction, mock_container, mock_session)

        # Verify backend URL was set for raw request
        assert result.raw_request is not None
        assert result.raw_request.backend_url == "https://new-backend.com"

    async def test_set_backend_no_url_configured(self):
        """Test SetBackendPolicy when no backend_url is configured."""
        # Create OpenAI transaction
        openai_request = Request(
            payload=OpenAIChatCompletionsRequest(
                model="gpt-3.5-turbo", messages=EventedList([Message(role="user", content="Hello")])
            ),
            api_endpoint="https://original.com",
            api_key="test-key",
        )
        transaction = Transaction(openai_request=openai_request)
        assert transaction.openai_request is not None
        original_endpoint = transaction.openai_request.api_endpoint

        # Apply policy with no backend_url
        policy = SetBackendPolicy(backend_url=None)
        mock_container = MagicMock()
        mock_session = AsyncMock()
        result = await policy.apply(transaction, mock_container, mock_session)

        # Verify nothing changed
        assert result.openai_request is not None
        assert result.openai_request.api_endpoint == original_endpoint

    async def test_set_backend_raw_transaction_no_url(self):
        """Test SetBackendPolicy with raw transaction when no backend_url is configured."""
        # Create raw transaction
        raw_request = RawRequest(method="GET", path="v1/models", api_key="test-key", backend_url="original-url")
        transaction = Transaction(raw_request=raw_request)
        assert transaction.raw_request is not None
        original_url = transaction.raw_request.backend_url

        # Apply policy with no backend_url
        policy = SetBackendPolicy(backend_url=None)
        mock_container = MagicMock()
        mock_session = AsyncMock()
        result = await policy.apply(transaction, mock_container, mock_session)

        # Verify nothing changed
        assert result.raw_request is not None
        assert result.raw_request.backend_url == original_url
