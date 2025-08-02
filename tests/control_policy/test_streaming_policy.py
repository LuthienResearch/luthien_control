"""Tests for streaming control policy base classes."""

from unittest.mock import MagicMock

import pytest
from luthien_control.api.openai_chat_completions.datatypes import Message
from luthien_control.api.openai_chat_completions.request import OpenAIChatCompletionsRequest
from luthien_control.control_policy.streaming_policy import (
    OpenAIStreamingChunk,
    PassthroughStreamingPolicy,
    StreamingControlPolicy,
)
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.request import Request
from luthien_control.core.response import Response
from luthien_control.core.streaming_response import ChunkedTextIterator
from luthien_control.core.transaction import Transaction
from psygnal.containers import EventedList
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession


class MockStreamingPolicy(StreamingControlPolicy):
    """Concrete implementation for testing."""

    chunks_processed: list = Field(default_factory=list, exclude=True)

    def __init__(self, name: str = "test_streaming_policy", **kwargs):
        super().__init__(name=name, **kwargs)

    @classmethod
    def get_policy_type_name(cls) -> str:
        """Override to provide a custom type name."""
        return "mock_streaming"

    async def apply_streaming(
        self, transaction: Transaction, container: DependencyContainer, session: AsyncSession
    ) -> Transaction:
        """Test implementation that wraps the iterator."""
        if transaction.openai_response and transaction.openai_response.streaming_iterator:
            wrapped_iterator = self.wrap_streaming_iterator(
                transaction.openai_response.streaming_iterator, transaction, container, session
            )
            transaction.openai_response.streaming_iterator = wrapped_iterator
        return transaction

    async def apply_non_streaming(
        self, transaction: Transaction, container: DependencyContainer, session: AsyncSession
    ) -> Transaction:
        """Test implementation for non-streaming."""
        return transaction


class MockStreamingPolicyWithProcessChunk(MockStreamingPolicy):
    """Concrete implementation for testing with process_chunk."""

    async def process_chunk(
        self,
        chunk: OpenAIStreamingChunk,
        transaction: Transaction,
        container: DependencyContainer,
        session: AsyncSession,
    ) -> OpenAIStreamingChunk:
        """Test chunk processing that logs chunks and adds a prefix."""
        self.chunks_processed.append(chunk)
        return f"[PROCESSED] {chunk}"


class TestStreamingControlPolicy:
    """Test the StreamingControlPolicy base class."""

    @pytest.fixture
    def streaming_transaction(self):
        """Create a transaction with streaming response."""
        request = Request(
            payload=OpenAIChatCompletionsRequest(
                model="gpt-4",
                messages=EventedList([Message(role="user", content="Test message")]),
                stream=True,
            ),
            api_endpoint="test",
            api_key="test_key",
        )
        transaction = Transaction(openai_request=request)

        # Add streaming response
        iterator = ChunkedTextIterator("Hello world test", chunk_size=5)
        transaction.openai_response = Response(streaming_iterator=iterator)

        return transaction

    @pytest.fixture
    def non_streaming_transaction(self):
        """Create a transaction with non-streaming response."""
        from luthien_control.api.openai_chat_completions.datatypes import Choice, Usage
        from luthien_control.api.openai_chat_completions.response import OpenAIChatCompletionsResponse

        request = Request(
            payload=OpenAIChatCompletionsRequest(
                model="gpt-4",
                messages=EventedList([Message(role="user", content="Test message")]),
                stream=False,
            ),
            api_endpoint="test",
            api_key="test_key",
        )
        transaction = Transaction(openai_request=request)

        # Add non-streaming response with proper structure
        response_payload = OpenAIChatCompletionsResponse(
            id="test-id",
            model="gpt-4",
            created=1234567890,
            choices=EventedList(
                [Choice(index=0, message=Message(role="assistant", content="Test response"), finish_reason="stop")]
            ),
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )
        transaction.openai_response = Response(payload=response_payload)

        return transaction

    @pytest.fixture
    def mock_container(self):
        """Create mock dependency container."""
        return MagicMock(spec=DependencyContainer)

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        return MagicMock(spec=AsyncSession)

    @pytest.mark.asyncio
    async def test_streaming_policy_routes_to_streaming_method(
        self, streaming_transaction, mock_container, mock_session
    ):
        """Test that streaming transactions are routed to apply_streaming."""
        policy = MockStreamingPolicyWithProcessChunk()

        result = await policy.apply(streaming_transaction, mock_container, mock_session)

        assert result is streaming_transaction
        assert result.openai_response is not None
        assert result.openai_response.is_streaming

        # Verify the iterator was wrapped by consuming it
        chunks = []
        assert result.openai_response.streaming_iterator is not None
        async for chunk in result.openai_response.streaming_iterator:
            chunks.append(chunk)

        # Should have processed chunks with the test prefix
        expected_chunks = ["[PROCESSED] Hello", "[PROCESSED]  worl", "[PROCESSED] d tes", "[PROCESSED] t"]
        assert chunks == expected_chunks

        # Verify chunks were logged in the policy
        assert policy.chunks_processed == ["Hello", " worl", "d tes", "t"]

    @pytest.mark.asyncio
    async def test_streaming_policy_routes_to_non_streaming_method(
        self, non_streaming_transaction, mock_container, mock_session
    ):
        """Test that non-streaming transactions are routed to apply_non_streaming."""
        policy = MockStreamingPolicy()

        result = await policy.apply(non_streaming_transaction, mock_container, mock_session)

        assert result is non_streaming_transaction
        assert result.openai_response is not None
        assert not result.openai_response.is_streaming

        # Should not have processed any chunks
        assert policy.chunks_processed == []

    @pytest.mark.asyncio
    async def test_streaming_buffer_creation(self):
        """Test streaming buffer creation."""
        policy = MockStreamingPolicy()
        iterator = ChunkedTextIterator("test")

        buffer = policy.create_streaming_buffer(iterator)

        assert buffer.iterator is iterator
        assert buffer.exhausted is False

    def test_passthrough_streaming_policy(self):
        """Test PassthroughStreamingPolicy implementation."""
        policy = PassthroughStreamingPolicy()

        # Should be a StreamingControlPolicy
        assert isinstance(policy, StreamingControlPolicy)

    @pytest.mark.asyncio
    async def test_passthrough_policy_streaming(self, streaming_transaction, mock_container, mock_session):
        """Test PassthroughStreamingPolicy with streaming transaction."""
        policy = PassthroughStreamingPolicy()

        assert streaming_transaction.openai_response is not None
        original_iterator = streaming_transaction.openai_response.streaming_iterator
        result = await policy.apply_streaming(streaming_transaction, mock_container, mock_session)

        # Should pass through unchanged
        assert result is streaming_transaction
        assert result.openai_response is not None
        assert result.openai_response.streaming_iterator is original_iterator

    @pytest.mark.asyncio
    async def test_passthrough_policy_non_streaming(self, non_streaming_transaction, mock_container, mock_session):
        """Test PassthroughStreamingPolicy with non-streaming transaction."""
        policy = PassthroughStreamingPolicy()

        result = await policy.apply_non_streaming(non_streaming_transaction, mock_container, mock_session)

        # Should pass through unchanged
        assert result is non_streaming_transaction

    def test_passthrough_policy_type_name(self):
        """Test PassthroughStreamingPolicy type name."""
        assert PassthroughStreamingPolicy.get_policy_type_name() == "passthrough_streaming"

    @pytest.mark.asyncio
    async def test_process_chunk(self, streaming_transaction, mock_container, mock_session):
        """Test base process_chunk method."""
        policy = MockStreamingPolicy()
        chunk = "test"
        result = await policy.process_chunk(chunk, streaming_transaction, mock_container, mock_session)
        assert result == chunk
