"""Tests for streaming response infrastructure."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from luthien_control.core.streaming_response import (
    ChunkedTextIterator,
    OpenAIStreamingIterator,
    RawStreamingIterator,
)


class TestStreamingIterators:
    """Test streaming iterator implementations."""

    @pytest.mark.asyncio
    async def test_chunked_text_iterator(self):
        """Test ChunkedTextIterator functionality."""
        text = "Hello world! This is a test of chunked text streaming."
        iterator = ChunkedTextIterator(text, chunk_size=10)

        chunks = []
        async for chunk in iterator:
            chunks.append(chunk)

        # Verify all text was returned
        assert "".join(chunks) == text

        # Verify chunking worked correctly
        # 54 chars total, chunk size 10 = 6 chunks
        assert len(chunks) == 6
        assert chunks[0] == "Hello worl"
        assert chunks[-1] == "ing."  # Last chunk has only 4 chars

    @pytest.mark.asyncio
    async def test_openai_streaming_iterator(self):
        """Test OpenAIStreamingIterator wrapping."""
        # Mock an OpenAI stream
        mock_stream = AsyncMock()
        mock_stream.__anext__ = AsyncMock()

        # Set up mock to return chunks then stop
        chunks = ["chunk1", "chunk2", "chunk3"]
        mock_stream.__anext__.side_effect = chunks + [StopAsyncIteration]

        iterator = OpenAIStreamingIterator(mock_stream)

        received_chunks = []
        async for chunk in iterator:
            received_chunks.append(chunk)

        assert received_chunks == chunks
        assert iterator.exhausted is True

        # Verify exhausted iterator raises StopAsyncIteration
        with pytest.raises(StopAsyncIteration):
            await iterator.__anext__()

    @pytest.mark.asyncio
    async def test_raw_streaming_iterator_with_httpx_response(self):
        """Test RawStreamingIterator with httpx-like response."""
        # Mock an httpx response with aiter_bytes
        mock_response = MagicMock()

        # Create an async iterator factory for aiter_bytes
        class MockAsyncIterator:
            def __init__(self, chunk_size):
                self.chunks = [b"chunk1", b"chunk2"]
                self.index = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.index >= len(self.chunks):
                    raise StopAsyncIteration
                chunk = self.chunks[self.index]
                self.index += 1
                return chunk

        mock_response.aiter_bytes = lambda chunk_size: MockAsyncIterator(chunk_size)

        iterator = RawStreamingIterator(mock_response, chunk_size=8192)

        chunks = []
        async for chunk in iterator:
            chunks.append(chunk)

        assert chunks == [b"chunk1", b"chunk2"]
        assert iterator.exhausted is True

    @pytest.mark.asyncio
    async def test_raw_streaming_iterator_fallback_read(self):
        """Test RawStreamingIterator fallback for responses without aiter_bytes."""

        # Create a mock response without aiter_bytes method
        class MockResponseWithoutAiterBytes:
            def __init__(self):
                self.chunks = [b"chunk1", b"chunk2", b""]
                self.index = 0

            async def read(self, chunk_size):
                if self.index < len(self.chunks):
                    chunk = self.chunks[self.index]
                    self.index += 1
                    return chunk
                return b""

        mock_response = MockResponseWithoutAiterBytes()
        iterator = RawStreamingIterator(mock_response, chunk_size=1024)

        received_chunks = []
        async for chunk in iterator:
            received_chunks.append(chunk)

        # Should receive the non-empty chunks
        assert received_chunks == [b"chunk1", b"chunk2"]
        assert iterator.exhausted is True

        # Verify exhausted iterator raises StopAsyncIteration
        with pytest.raises(StopAsyncIteration):
            await iterator.__anext__()

    @pytest.mark.asyncio
    async def test_raw_streaming_iterator_exception_handling(self):
        """Test RawStreamingIterator exception handling during iteration."""
        mock_response = MagicMock()

        class MockAsyncIterator:
            def __init__(self, chunk_size):
                self.count = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.count == 0:
                    self.count += 1
                    return b"chunk1"
                raise StopAsyncIteration

        mock_response.aiter_bytes = lambda chunk_size: MockAsyncIterator(chunk_size)

        iterator = RawStreamingIterator(mock_response)

        # Should get one chunk then stop
        chunk = await iterator.__anext__()
        assert chunk == b"chunk1"

        # Next call should raise StopAsyncIteration and set exhausted
        with pytest.raises(StopAsyncIteration):
            await iterator.__anext__()

        assert iterator.exhausted is True

    @pytest.mark.asyncio
    async def test_chunked_text_iterator_empty_text(self):
        """Test ChunkedTextIterator with empty text."""
        iterator = ChunkedTextIterator("", chunk_size=10)

        chunks = []
        async for chunk in iterator:
            chunks.append(chunk)

        assert chunks == []

    @pytest.mark.asyncio
    async def test_chunked_text_iterator_single_chunk(self):
        """Test ChunkedTextIterator with text smaller than chunk size."""
        text = "short"
        iterator = ChunkedTextIterator(text, chunk_size=10)

        chunks = []
        async for chunk in iterator:
            chunks.append(chunk)

        assert chunks == ["short"]

    @pytest.mark.asyncio
    async def test_chunked_text_iterator_exact_chunk_size(self):
        """Test ChunkedTextIterator with text exactly matching chunk size."""
        text = "exactly10c"  # Exactly 10 characters
        iterator = ChunkedTextIterator(text, chunk_size=10)

        chunks = []
        async for chunk in iterator:
            chunks.append(chunk)

        assert chunks == ["exactly10c"]
        assert "".join(chunks) == text


class TestStreamingResponseModels:
    """Test Response and RawResponse streaming support."""

    def test_response_is_streaming_property(self):
        """Test Response.is_streaming property."""
        from luthien_control.core.response import Response

        # Non-streaming response
        response = Response()
        assert response.is_streaming is False

        # Streaming response - use a real iterator instance
        text_iterator = ChunkedTextIterator("test")
        response = Response(streaming_iterator=text_iterator)
        assert response.is_streaming is True

    def test_raw_response_is_streaming_property(self):
        """Test RawResponse.is_streaming property."""
        from luthien_control.core.raw_response import RawResponse

        # Non-streaming response
        response = RawResponse(status_code=200)
        assert response.is_streaming is False

        # Streaming response - use a real iterator instance
        text_iterator = ChunkedTextIterator("test")
        response = RawResponse(status_code=200, streaming_iterator=text_iterator)
        assert response.is_streaming is True

    def test_transaction_is_streaming_property(self):
        """Test Transaction.is_streaming property."""
        from luthien_control.api.openai_chat_completions.request import OpenAIChatCompletionsRequest
        from luthien_control.core.request import Request
        from luthien_control.core.response import Response
        from luthien_control.core.transaction import Transaction
        from psygnal.containers import EventedList

        # Create a transaction with non-streaming response
        request = Request(
            payload=OpenAIChatCompletionsRequest(model="gpt-4", messages=EventedList()),
            api_endpoint="test",
            api_key="test",
        )
        transaction = Transaction(openai_request=request)
        assert transaction.is_streaming is False

        # Add non-streaming response
        transaction.openai_response = Response()
        assert transaction.is_streaming is False

        # Add streaming response - use a real iterator instance
        text_iterator = ChunkedTextIterator("test")
        transaction.openai_response = Response(streaming_iterator=text_iterator)
        assert transaction.is_streaming is True
