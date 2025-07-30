"""Tests specifically for streaming response handling in SendBackendRequestPolicy."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from luthien_control.api.openai_chat_completions.datatypes import Message
from luthien_control.api.openai_chat_completions.request import OpenAIChatCompletionsRequest
from luthien_control.control_policy.send_backend_request import SendBackendRequestPolicy
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.request import Request
from luthien_control.core.transaction import Transaction
from psygnal.containers import EventedList
from sqlalchemy.ext.asyncio import AsyncSession


class MockAsyncStream:
    """Mock AsyncStream object that doesn't have model_dump method."""

    def __init__(self):
        self.is_streaming = True

    def __aiter__(self):
        return self

    async def __anext__(self):
        # Just raise StopAsyncIteration for this test
        raise StopAsyncIteration

    def __str__(self):
        return "MockAsyncStream()"


class TestSendBackendRequestPolicyStreaming:
    """Test streaming response handling in SendBackendRequestPolicy."""

    @pytest.fixture
    def streaming_transaction(self):
        """Create a transaction with a streaming request."""
        request = Request(
            payload=OpenAIChatCompletionsRequest(
                model="gpt-4",
                messages=EventedList([Message(role="user", content="Test message")]),
                stream=True,  # This is the key - requesting streaming
            ),
            api_endpoint="https://api.openai.com/v1/chat/completions",
            api_key="test_key",
        )
        return Transaction(openai_request=request)

    @pytest.fixture
    def mock_container(self):
        """Create a mock dependency container."""
        container = MagicMock(spec=DependencyContainer)

        # Mock the OpenAI client
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock()
        container.create_openai_client.return_value = mock_client

        return container

    @pytest.mark.asyncio
    async def test_handles_streaming_response_without_model_dump(self, streaming_transaction, mock_container):
        """Test that policy handles streaming responses that don't have model_dump."""
        policy = SendBackendRequestPolicy()
        session = MagicMock(spec=AsyncSession)

        # Mock the streaming response (AsyncStream-like object without model_dump)
        mock_streaming_response = MockAsyncStream()
        mock_container.create_openai_client.return_value.chat.completions.create.return_value = mock_streaming_response

        # This should not raise an AttributeError
        result = await policy.apply(streaming_transaction, mock_container, session)

        # Verify the transaction was updated correctly
        assert result is streaming_transaction

        # Verify response object was created with streaming iterator
        assert result.openai_response is not None
        assert result.openai_response.payload is None
        assert result.openai_response.api_endpoint is not None
        assert result.openai_response.is_streaming is True
        assert result.openai_response.streaming_iterator is not None

        # Verify the streaming iterator wraps our mock
        # Check that it's an OpenAIStreamingIterator and has the correct stream
        from luthien_control.core.streaming_response import OpenAIStreamingIterator

        assert isinstance(result.openai_response.streaming_iterator, OpenAIStreamingIterator)
        assert result.openai_response.streaming_iterator.stream is mock_streaming_response

    @pytest.mark.asyncio
    async def test_handles_regular_response_with_model_dump(self, streaming_transaction, mock_container):
        """Test that policy still handles regular responses correctly."""
        policy = SendBackendRequestPolicy()
        session = MagicMock(spec=AsyncSession)

        # Create a mock regular response with model_dump method
        mock_regular_response = MagicMock()
        mock_regular_response.model_dump.return_value = {
            "id": "test-id",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "gpt-4",
            "choices": [
                {"index": 0, "message": {"role": "assistant", "content": "Test response"}, "finish_reason": "stop"}
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

        mock_container.create_openai_client.return_value.chat.completions.create.return_value = mock_regular_response

        # Make the transaction non-streaming
        streaming_transaction.openai_request.payload.stream = False

        result = await policy.apply(streaming_transaction, mock_container, session)

        # Verify regular response handling
        assert result is streaming_transaction
        assert result.openai_response is not None
        assert result.openai_response.payload is not None
        assert result.openai_response.payload.id == "test-id"

        # Should not have streaming iterator for non-streaming response
        assert result.openai_response.is_streaming is False
        assert result.openai_response.streaming_iterator is None

    @pytest.mark.asyncio
    async def test_detection_works_for_objects_without_model_dump(self):
        """Test that our detection correctly identifies objects without model_dump."""
        # Objects without model_dump
        stream_obj = MockAsyncStream()
        string_obj = "just a string"
        dict_obj = {"key": "value"}

        # Objects with model_dump
        mock_with_model_dump = MagicMock()
        mock_with_model_dump.model_dump = MagicMock(return_value={})

        # Test our detection logic
        assert not (hasattr(stream_obj, "model_dump") and callable(getattr(stream_obj, "model_dump")))
        assert not (hasattr(string_obj, "model_dump") and callable(getattr(string_obj, "model_dump")))
        assert not (hasattr(dict_obj, "model_dump") and callable(getattr(dict_obj, "model_dump")))
        assert hasattr(mock_with_model_dump, "model_dump") and callable(getattr(mock_with_model_dump, "model_dump"))

    @pytest.mark.asyncio
    async def test_streaming_response_creates_response_object_when_none(self, streaming_transaction, mock_container):
        """Test that policy creates response object for streaming when none exists."""
        policy = SendBackendRequestPolicy()
        session = MagicMock(spec=AsyncSession)

        # Ensure no existing response
        streaming_transaction.openai_response = None

        # Mock streaming response
        mock_streaming_response = MockAsyncStream()
        mock_container.create_openai_client.return_value.chat.completions.create.return_value = mock_streaming_response

        result = await policy.apply(streaming_transaction, mock_container, session)

        # Verify response object was created
        assert result.openai_response is not None
        assert result.openai_response.api_endpoint == "https://api.openai.com/v1/chat/completions"
        assert result.openai_response.streaming_iterator is not None
        assert result.openai_response.payload is None  # Streaming responses don't have payload

    @pytest.mark.asyncio
    async def test_raw_streaming_request_with_sse_header(self, mock_container):
        """Test raw streaming request with Accept: text/event-stream header."""
        from unittest.mock import patch

        from luthien_control.core.raw_request import RawRequest

        policy = SendBackendRequestPolicy()
        session = MagicMock(spec=AsyncSession)

        # Create raw request with streaming header
        raw_request = RawRequest(
            method="POST",
            path="v1/chat/completions",
            headers={"Accept": "text/event-stream", "Content-Type": "application/json"},
            body=b'{"stream": true}',
            api_key="test-key",
            backend_url="https://api.streaming.com",
        )
        transaction = Transaction(raw_request=raw_request)

        # Mock httpx streaming response
        with patch("httpx.AsyncClient") as mock_client_class:
            # Create a proper async context manager for stream
            class MockAsyncContextManager:
                def __init__(self, response):
                    self.response = response

                async def __aenter__(self):
                    return self.response

                async def __aexit__(self, *args):
                    return None

            # Mock streaming response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "text/event-stream"}

            # Create a mock client with proper stream method
            class MockAsyncClient:
                def __init__(self):
                    self.stream_called_with = None

                def stream(self, **kwargs):
                    self.stream_called_with = kwargs
                    return MockAsyncContextManager(mock_response)

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    return None

            mock_client = MockAsyncClient()
            mock_client_class.return_value = mock_client

            result = await policy.apply(transaction, mock_container, session)

            # Verify streaming request was made
            expected_call = {
                "method": "POST",
                "url": "https://api.streaming.com/v1/chat/completions",
                "headers": {
                    "Accept": "text/event-stream",
                    "Content-Type": "application/json",
                    "Authorization": "Bearer test-key",
                },
                "content": b'{"stream": true}',
            }
            assert mock_client.stream_called_with == expected_call

            # Verify streaming response was created
            assert result.raw_response is not None
            assert result.raw_response.status_code == 200
            assert result.raw_response.streaming_iterator is not None
            assert result.raw_response.body is None  # Streaming responses don't have body

    @pytest.mark.asyncio
    async def test_raw_request_non_streaming(self, mock_container):
        """Test regular raw request without streaming headers."""
        from unittest.mock import patch

        from luthien_control.core.raw_request import RawRequest

        policy = SendBackendRequestPolicy()
        session = MagicMock(spec=AsyncSession)

        # Create regular raw request
        raw_request = RawRequest(
            method="GET",
            path="v1/models",
            headers={"Accept": "application/json"},
            body=b"",
            api_key="test-key",
            backend_url="https://api.regular.com",
        )
        transaction = Transaction(raw_request=raw_request)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "application/json"}
            mock_response.content = b'{"models": []}'
            mock_response.text = '{"models": []}'
            mock_client.request.return_value = mock_response

            result = await policy.apply(transaction, mock_container, session)

            # Verify non-streaming request was made
            mock_client.request.assert_called_once_with(
                method="GET",
                url="https://api.regular.com/v1/models",
                headers={"Accept": "application/json", "Authorization": "Bearer test-key"},
                content=b"",
            )

            # Verify regular response was created
            assert result.raw_response is not None
            assert result.raw_response.status_code == 200
            assert result.raw_response.streaming_iterator is None
            assert result.raw_response.body == b'{"models": []}'
            assert result.raw_response.content == '{"models": []}'
