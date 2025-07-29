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
