"""Integration tests for streaming response flows."""

import json
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from luthien_control.api.openai_chat_completions.datatypes import Message
from luthien_control.api.openai_chat_completions.request import OpenAIChatCompletionsRequest
from luthien_control.control_policy.send_backend_request import SendBackendRequestPolicy
from luthien_control.control_policy.streaming_policy import PassthroughStreamingPolicy
from luthien_control.control_policy.transaction_context_logging_policy import TransactionContextLoggingPolicy
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.request import Request
from luthien_control.core.streaming_response import ChunkedTextIterator
from luthien_control.core.transaction import Transaction
from psygnal.containers import EventedList
from sqlalchemy.ext.asyncio import AsyncSession


class MockAsyncStream:
    """Mock OpenAI async stream for testing."""

    def __init__(self, chunks):
        self.chunks = chunks
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self.chunks):
            raise StopAsyncIteration
        chunk = self.chunks[self.index]
        self.index += 1
        return chunk


class TestStreamingIntegration:
    """Integration tests for streaming response handling across policies."""

    @pytest.fixture
    def streaming_transaction(self):
        """Create a streaming transaction."""
        request = Request(
            payload=OpenAIChatCompletionsRequest(
                model="gpt-4",
                messages=EventedList([Message(role="user", content="Test streaming")]),
                stream=True,
            ),
            api_endpoint="https://api.openai.com/v1/chat/completions",
            api_key="sk-test123456789",
        )
        return Transaction(openai_request=request)

    @pytest.fixture
    def mock_container(self):
        """Create mock dependency container with OpenAI client."""
        container = MagicMock(spec=DependencyContainer)

        # Mock OpenAI client
        mock_client = MagicMock()
        mock_chunks = [
            {"choices": [{"delta": {"content": "Hello"}}]},
            {"choices": [{"delta": {"content": " world"}}]},
            {"choices": [{"delta": {"content": "!"}}]},
        ]
        mock_client.chat.completions.create = AsyncMock(return_value=MockAsyncStream(mock_chunks))
        container.create_openai_client.return_value = mock_client

        return container

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        return MagicMock(spec=AsyncSession)

    @pytest.mark.asyncio
    async def test_streaming_policy_chain(self, streaming_transaction, mock_container, mock_session, caplog):
        """Test that streaming responses work through a policy chain."""
        # Create policy chain: logging -> backend -> passthrough
        logging_policy = TransactionContextLoggingPolicy(name="StreamingLogger")
        backend_policy = SendBackendRequestPolicy()
        passthrough_policy = PassthroughStreamingPolicy()

        with caplog.at_level(logging.INFO):
            # Apply policies in sequence
            result1 = await logging_policy.apply(streaming_transaction, mock_container, mock_session)
            result2 = await backend_policy.apply(result1, mock_container, mock_session)
            final_result = await passthrough_policy.apply(result2, mock_container, mock_session)

        # Verify transaction is streaming
        assert final_result.is_streaming
        assert final_result.openai_response is not None
        assert final_result.openai_response.is_streaming
        assert final_result.openai_response.streaming_iterator is not None

        # Verify we can consume the stream
        chunks = []
        async for chunk in final_result.openai_response.streaming_iterator:
            chunks.append(chunk)

        assert len(chunks) == 3
        assert chunks[0]["choices"][0]["delta"]["content"] == "Hello"
        assert chunks[1]["choices"][0]["delta"]["content"] == " world"
        assert chunks[2]["choices"][0]["delta"]["content"] == "!"

        # Verify logging captured the request (response not yet created when logging runs first)
        log_messages = [record.message for record in caplog.records]
        streaming_log = next((msg for msg in log_messages if "Transaction Context JSON:" in msg), None)
        assert streaming_log is not None

        # Parse the JSON from the log to verify request info was captured
        json_start = streaming_log.find("{\n")
        if json_start != -1:
            json_str = streaming_log[json_start:]
            context = json.loads(json_str)
            assert "openai_request" in context
            assert context["openai_request"]["payload"]["stream"] is True
            # Note: The response won't be logged since logging policy runs before backend policy

    @pytest.mark.asyncio
    async def test_non_streaming_to_streaming_conversion(self, mock_container, mock_session):
        """Test converting a non-streaming response to streaming for consistent handling."""
        # Create non-streaming transaction
        request = Request(
            payload=OpenAIChatCompletionsRequest(
                model="gpt-4",
                messages=EventedList([Message(role="user", content="Test")]),
                stream=False,
            ),
            api_endpoint="test",
            api_key="test_key",
        )
        transaction = Transaction(openai_request=request)

        # Manually add a streaming iterator to simulate conversion
        text_iterator = ChunkedTextIterator("This is a test response", chunk_size=10)
        transaction.openai_response = transaction.openai_response or MagicMock()
        transaction.openai_response.streaming_iterator = text_iterator

        # Apply passthrough policy
        passthrough_policy = PassthroughStreamingPolicy()
        result = await passthrough_policy.apply(transaction, mock_container, mock_session)

        # Should handle the "streaming" transaction appropriately
        assert result is transaction

    @pytest.mark.asyncio
    async def test_logging_policy_with_streaming_response(self, mock_container, mock_session, caplog):
        """Test that logging policy properly handles streaming responses."""
        # Create transaction with streaming response
        request = Request(
            payload=OpenAIChatCompletionsRequest(
                model="gpt-4",
                messages=EventedList([Message(role="user", content="Stream test")]),
                stream=True,
            ),
            api_endpoint="test",
            api_key="sk-test123",
        )
        transaction = Transaction(openai_request=request)

        # Add streaming response
        from luthien_control.core.response import Response

        streaming_iterator = ChunkedTextIterator("Response content", chunk_size=8)
        transaction.openai_response = Response(streaming_iterator=streaming_iterator)

        # Apply logging policy
        logging_policy = TransactionContextLoggingPolicy(log_level="INFO")

        with caplog.at_level(logging.INFO):
            result = await logging_policy.apply(transaction, mock_container, mock_session)

        # Verify transaction unchanged
        assert result is transaction

        # Verify streaming info was logged
        assert len(caplog.records) == 1
        log_message = caplog.records[0].message
        assert "Transaction Context JSON:" in log_message

        # Parse and verify the logged JSON contains streaming info
        json_start = log_message.find("{\n")
        if json_start != -1:
            json_str = log_message[json_start:]
            context = json.loads(json_str)

            assert "openai_response" in context
            response_data = context["openai_response"]
            assert response_data["is_streaming"] is True
            assert "streaming_iterator" in response_data

            iterator_data = response_data["streaming_iterator"]
            assert iterator_data["_is_streaming_iterator"] is True
            assert iterator_data["_iterator_type"] == "ChunkedTextIterator"

    @pytest.mark.asyncio
    async def test_mixed_policy_chain_streaming_and_non_streaming(self, mock_container, mock_session):
        """Test policy chain with mix of streaming-aware and regular policies."""
        # Create streaming transaction
        request = Request(
            payload=OpenAIChatCompletionsRequest(
                model="gpt-4",
                messages=EventedList([Message(role="user", content="Mixed test")]),
                stream=True,
            ),
            api_endpoint="test",
            api_key="test_key",
        )
        transaction = Transaction(openai_request=request)

        # Add streaming response
        from luthien_control.core.response import Response

        streaming_iterator = ChunkedTextIterator("Mixed content", chunk_size=5)
        transaction.openai_response = Response(streaming_iterator=streaming_iterator)

        # Apply mixed policy chain
        logging_policy = TransactionContextLoggingPolicy()  # Regular policy
        passthrough_policy = PassthroughStreamingPolicy()  # Streaming-aware policy

        result1 = await logging_policy.apply(transaction, mock_container, mock_session)
        result2 = await passthrough_policy.apply(result1, mock_container, mock_session)

        # Should maintain streaming nature
        assert result2.is_streaming
        assert result2.openai_response is not None
        assert result2.openai_response.is_streaming

        # Should be able to consume stream
        chunks = []
        assert result2.openai_response.streaming_iterator is not None
        async for chunk in result2.openai_response.streaming_iterator:
            chunks.append(chunk)

        expected_chunks = ["Mixed", " cont", "ent"]
        assert chunks == expected_chunks
