from typing import Any, AsyncIterator
from unittest.mock import patch

from fastapi.responses import StreamingResponse
from luthien_control.api.openai_chat_completions.streaming_response import (
    openai_streaming_iterator_to_sse,
    openai_streaming_response_to_fastapi_response,
)
from luthien_control.core.streaming_response import StreamingResponseIterator
from pydantic import Field


class MockStreamingIterator(StreamingResponseIterator):
    """Mock streaming iterator for testing."""

    iterator: Any = Field(description="The async iterator to wrap")
    exhausted: bool = Field(default=False, exclude=True)

    def __init__(self, iterator, **kwargs):
        kwargs["iterator"] = iterator
        super().__init__(**kwargs)

    def __aiter__(self) -> AsyncIterator[Any]:
        return self

    async def __anext__(self) -> Any:
        if self.exhausted:
            raise StopAsyncIteration
        try:
            return await self.iterator.__anext__()
        except StopAsyncIteration:
            self.exhausted = True
            raise


class TestOpenAIStreamingIteratorToSSE:
    """Tests for openai_streaming_iterator_to_sse function."""

    async def test_openai_streaming_iterator_to_sse_basic(self):
        """Test basic streaming conversion to SSE format."""

        # Mock iterator with chunks
        async def mock_iterator():
            yield {"id": "chunk-1", "content": "Hello"}
            yield {"id": "chunk-2", "content": "World"}

        iterator = MockStreamingIterator(mock_iterator())

        chunks = []
        async for chunk in openai_streaming_iterator_to_sse(iterator):
            chunks.append(chunk)

        # Should have data chunks plus final done event
        assert len(chunks) == 3
        assert 'data: {"id":"chunk-1","content":"Hello"}\n\n' == chunks[0]
        assert 'data: {"id":"chunk-2","content":"World"}\n\n' == chunks[1]
        assert "event: done\ndata: [DONE]\n\n" == chunks[2]

    async def test_openai_streaming_iterator_to_sse_empty_stream(self):
        """Test SSE conversion with empty stream."""

        async def empty_iterator():
            return
            yield  # unreachable

        iterator = MockStreamingIterator(empty_iterator())

        chunks = []
        async for chunk in openai_streaming_iterator_to_sse(iterator):
            chunks.append(chunk)

        # Should only have the final done event
        assert len(chunks) == 1
        assert "event: done\ndata: [DONE]\n\n" == chunks[0]

    async def test_openai_streaming_iterator_to_sse_with_transaction_id(self):
        """Test SSE conversion includes transaction ID in errors."""

        async def failing_iterator():
            yield {"id": "chunk-1"}
            raise ValueError("Stream failed")

        iterator = MockStreamingIterator(failing_iterator())
        transaction_id = "txn-123"

        chunks = []
        with patch("luthien_control.api.openai_chat_completions.streaming_response.logger") as mock_logger:
            async for chunk in openai_streaming_iterator_to_sse(iterator, transaction_id):
                chunks.append(chunk)

        # Should have one data chunk, error chunk, and done event
        assert len(chunks) == 3
        assert 'data: {"id":"chunk-1"}\n\n' == chunks[0]

        # Error chunk should include transaction ID
        error_chunk = chunks[1]
        assert "event: error" in error_chunk
        assert '"transaction_id":"txn-123"' in error_chunk

        assert "event: done\ndata: [DONE]\n\n" == chunks[2]

        # Should log the error
        mock_logger.error.assert_called_once_with("Error during streaming", exc_info=True)

    async def test_openai_streaming_iterator_to_sse_exception_handling(self):
        """Test exception handling in streaming iterator."""

        async def failing_iterator():
            yield {"content": "partial"}
            raise RuntimeError("Connection lost")

        iterator = MockStreamingIterator(failing_iterator())

        chunks = []
        with patch("luthien_control.api.openai_chat_completions.streaming_response.logger"):
            async for chunk in openai_streaming_iterator_to_sse(iterator):
                chunks.append(chunk)

        # Should have data chunk, error chunk, and done event
        assert len(chunks) == 3
        assert 'data: {"content":"partial"}\n\n' == chunks[0]

        # Error chunk should be formatted properly
        error_chunk = chunks[1]
        assert "event: error" in error_chunk
        assert "Connection lost" in error_chunk

        assert "event: done\ndata: [DONE]\n\n" == chunks[2]

    @patch("luthien_control.api.openai_chat_completions.streaming_response.format_streaming_error")
    async def test_openai_streaming_iterator_to_sse_error_formatting(self, mock_format_error):
        """Test that errors are properly formatted using format_streaming_error."""
        mock_format_error.return_value = "formatted error"

        async def failing_iterator():
            raise ValueError("Test error")

        iterator = MockStreamingIterator(failing_iterator())
        transaction_id = "txn-456"

        chunks = []
        with patch("luthien_control.api.openai_chat_completions.streaming_response.logger"):
            async for chunk in openai_streaming_iterator_to_sse(iterator, transaction_id):
                chunks.append(chunk)

        # Should call format_streaming_error with correct parameters
        mock_format_error.assert_called_once()
        call_args = mock_format_error.call_args
        assert len(call_args[0]) == 2  # Two positional arguments
        # First arg should be an exception (could be ValueError or AttributeError)
        assert isinstance(call_args[0][0], Exception)
        assert call_args[0][1] == transaction_id  # Second arg should be transaction_id

        # Should include formatted error and done event
        assert len(chunks) == 2
        assert chunks[0] == "formatted error"
        assert "event: done\ndata: [DONE]\n\n" == chunks[1]

    async def test_openai_streaming_iterator_to_sse_multiple_chunks(self):
        """Test SSE conversion with multiple diverse chunks."""

        async def multi_chunk_iterator():
            yield {"id": "1", "choices": [{"delta": {"content": "Hello"}}]}
            yield {"id": "2", "choices": [{"delta": {"content": " there"}}]}
            yield {"id": "3", "choices": [{"delta": {"content": "!"}}]}
            yield {"id": "4", "choices": [{"finish_reason": "stop"}]}

        iterator = MockStreamingIterator(multi_chunk_iterator())

        chunks = []
        async for chunk in openai_streaming_iterator_to_sse(iterator):
            chunks.append(chunk)

        # Should have 4 data chunks plus done event
        assert len(chunks) == 5

        # Verify each chunk is properly formatted
        for i in range(4):
            assert chunks[i].startswith("data: ")
            assert chunks[i].endswith("\n\n")

        # Final chunk should be done event
        assert "event: done\ndata: [DONE]\n\n" == chunks[4]


class TestOpenAIStreamingResponseToFastAPIResponse:
    """Tests for openai_streaming_response_to_fastapi_response function."""

    def test_openai_streaming_response_to_fastapi_response_basic(self):
        """Test conversion to FastAPI StreamingResponse."""

        async def mock_iterator():
            yield {"content": "test"}

        iterator = MockStreamingIterator(mock_iterator())

        response = openai_streaming_response_to_fastapi_response(iterator)

        # Should return StreamingResponse
        assert isinstance(response, StreamingResponse)

        # Should have correct media type
        assert response.media_type == "text/event-stream"

        # Should have appropriate headers
        expected_headers = {
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
            "X-Accel-Buffering": "no",
        }

        for key, value in expected_headers.items():
            assert response.headers[key] == value

    def test_openai_streaming_response_to_fastapi_response_with_transaction_id(self):
        """Test conversion includes transaction ID for error handling."""

        async def mock_iterator():
            yield {"test": "data"}

        iterator = MockStreamingIterator(mock_iterator())
        transaction_id = "txn-789"

        with patch(
            "luthien_control.api.openai_chat_completions.streaming_response.openai_streaming_iterator_to_sse"
        ) as mock_sse:
            mock_sse.return_value = iter(["test chunk"])

            response = openai_streaming_response_to_fastapi_response(iterator, transaction_id)

            # Should pass transaction_id to SSE converter
            mock_sse.assert_called_once_with(iterator, transaction_id)

        assert isinstance(response, StreamingResponse)

    async def test_openai_streaming_response_to_fastapi_response_integration(self):
        """Test end-to-end functionality of the response conversion."""

        async def mock_iterator():
            yield {"id": "test-1", "content": "Hello"}
            yield {"id": "test-2", "content": "World"}

        iterator = MockStreamingIterator(mock_iterator())

        response = openai_streaming_response_to_fastapi_response(iterator)

        # Collect all chunks from the response by accessing the iterator directly
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk)

        # Should have data chunks plus done event
        assert len(chunks) == 3

        # Verify chunk formatting
        assert 'data: {"id":"test-1","content":"Hello"}\n\n' == chunks[0]
        assert 'data: {"id":"test-2","content":"World"}\n\n' == chunks[1]
        assert "event: done\ndata: [DONE]\n\n" == chunks[2]

    def test_openai_streaming_response_headers_completeness(self):
        """Test that all required headers are set correctly."""

        async def mock_iterator():
            yield {"test": "data"}

        iterator = MockStreamingIterator(mock_iterator())

        response = openai_streaming_response_to_fastapi_response(iterator)

        # Check all headers individually
        assert response.headers["Cache-Control"] == "no-cache"
        assert response.headers["Connection"] == "keep-alive"
        assert response.headers["Content-Type"] == "text/event-stream"
        assert response.headers["X-Accel-Buffering"] == "no"

        # Verify media type
        assert response.media_type == "text/event-stream"

    def test_openai_streaming_response_error_handling_integration(self):
        """Test error handling in complete response flow."""

        async def failing_iterator():
            yield {"content": "start"}
            raise ConnectionError("Network failure")

        iterator = MockStreamingIterator(failing_iterator())
        transaction_id = "txn-error-test"

        response = openai_streaming_response_to_fastapi_response(iterator, transaction_id)

        # Response should still be created successfully
        assert isinstance(response, StreamingResponse)
        assert response.media_type == "text/event-stream"

        # Headers should be set correctly even with error iterator
        assert response.headers["Cache-Control"] == "no-cache"
