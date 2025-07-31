from unittest.mock import Mock

import pytest
from luthien_control.utils.streaming import (
    StreamingBuffer,
    buffer_streaming_response,
    format_openai_streaming_chunk,
    format_sse_chunk,
    format_streaming_error,
)


class TestFormatSSEChunk:
    """Tests for the format_sse_chunk function."""

    async def test_format_sse_chunk_basic_data(self):
        """Test formatting basic data without event type."""
        data = {"message": "hello", "id": 123}
        result = await format_sse_chunk(data)

        expected = 'data: {"message":"hello","id":123}\n\n'
        assert result == expected

    async def test_format_sse_chunk_with_event_type(self):
        """Test formatting data with event type."""
        data = {"status": "complete"}
        result = await format_sse_chunk(data, event="completion")

        expected = 'event: completion\ndata: {"status":"complete"}\n\n'
        assert result == expected

    async def test_format_sse_chunk_empty_data(self):
        """Test formatting empty data."""
        data = {}
        result = await format_sse_chunk(data)

        expected = "data: {}\n\n"
        assert result == expected

    async def test_format_sse_chunk_nested_data(self):
        """Test formatting nested data structures."""
        data = {"user": {"id": 1, "name": "test"}, "items": [1, 2, 3]}
        result = await format_sse_chunk(data)

        # Should produce compact JSON
        assert 'data: {"user":{"id":1,"name":"test"},"items":[1,2,3]}\n\n' == result

    async def test_format_sse_chunk_special_characters(self):
        """Test formatting data with special characters."""
        data = {"message": 'Hello\nWorld\t"quoted"'}
        result = await format_sse_chunk(data)

        # JSON should properly escape special characters
        assert '"Hello\\nWorld\\t\\"quoted\\""' in result
        assert result.endswith("\n\n")


class TestFormatOpenAIStreamingChunk:
    """Tests for the format_openai_streaming_chunk function."""

    async def test_format_openai_streaming_chunk_pydantic_model(self):
        """Test formatting chunk with model_dump method."""
        mock_chunk = Mock()
        mock_chunk.model_dump.return_value = {"id": "chunk-1", "content": "test"}

        result = await format_openai_streaming_chunk(mock_chunk)

        mock_chunk.model_dump.assert_called_once()
        expected = 'data: {"id":"chunk-1","content":"test"}\n\n'
        assert result == expected

    async def test_format_openai_streaming_chunk_to_dict_method(self):
        """Test formatting chunk with to_dict method."""
        mock_chunk = Mock()
        # Remove model_dump to test to_dict path
        del mock_chunk.model_dump
        mock_chunk.to_dict.return_value = {"type": "delta", "text": "hello"}

        result = await format_openai_streaming_chunk(mock_chunk)

        mock_chunk.to_dict.assert_called_once()
        expected = 'data: {"type":"delta","text":"hello"}\n\n'
        assert result == expected

    async def test_format_openai_streaming_chunk_dict_input(self):
        """Test formatting chunk that's already a dict."""
        chunk = {"choices": [{"delta": {"content": "test"}}]}

        result = await format_openai_streaming_chunk(chunk)

        expected = 'data: {"choices":[{"delta":{"content":"test"}}]}\n\n'
        assert result == expected

    async def test_format_openai_streaming_chunk_string_fallback(self):
        """Test formatting chunk that can't be converted to dict."""
        chunk = "plain string chunk"

        result = await format_openai_streaming_chunk(chunk)

        expected = 'data: {"content":"plain string chunk"}\n\n'
        assert result == expected

    async def test_format_openai_streaming_chunk_complex_object(self):
        """Test formatting complex object without model_dump or to_dict."""

        class CustomObject:
            def __str__(self):
                return "custom object representation"

        chunk = CustomObject()
        result = await format_openai_streaming_chunk(chunk)

        expected = 'data: {"content":"custom object representation"}\n\n'
        assert result == expected


class TestFormatStreamingError:
    """Tests for the format_streaming_error function."""

    async def test_format_streaming_error_basic(self):
        """Test formatting basic error without transaction ID."""
        error = ValueError("Something went wrong")

        result = await format_streaming_error(error)

        assert "event: error" in result

    async def test_format_streaming_error_with_transaction_id(self):
        """Test formatting error with transaction ID."""
        error = RuntimeError("Connection failed")
        transaction_id = "txn-123"

        result = await format_streaming_error(error, transaction_id)

        # Should include transaction_id in the data
        assert "event: error" in result

    async def test_format_streaming_error_custom_exception(self):
        """Test formatting custom exception type."""

        class CustomError(Exception):
            pass

        error = CustomError("Custom error message")

        result = await format_streaming_error(error)

        assert "event: error" in result

    async def test_format_streaming_error_empty_message(self):
        """Test formatting error with empty message."""
        error = Exception("")

        result = await format_streaming_error(error)

        assert "event: error" in result


class TestBufferStreamingResponse:
    """Tests for the buffer_streaming_response function."""

    async def test_buffer_streaming_response_basic(self):
        """Test buffering a simple async iterator."""

        async def mock_iterator():
            for i in range(3):
                yield f"chunk-{i}"

        result = await buffer_streaming_response(mock_iterator())

        assert result == ["chunk-0", "chunk-1", "chunk-2"]

    async def test_buffer_streaming_response_empty_iterator(self):
        """Test buffering an empty async iterator."""

        async def empty_iterator():
            return
            yield  # unreachable

        result = await buffer_streaming_response(empty_iterator())

        assert result == []

    async def test_buffer_streaming_response_with_max_chunks(self):
        """Test buffering with max_chunks limit."""

        async def mock_iterator():
            for i in range(10):
                yield f"chunk-{i}"

        result = await buffer_streaming_response(mock_iterator(), max_chunks=3)

        assert result == ["chunk-0", "chunk-1", "chunk-2"]
        assert len(result) == 3

    async def test_buffer_streaming_response_max_chunks_larger_than_stream(self):
        """Test buffering with max_chunks larger than available chunks."""

        async def mock_iterator():
            for i in range(2):
                yield f"chunk-{i}"

        result = await buffer_streaming_response(mock_iterator(), max_chunks=10)

        assert result == ["chunk-0", "chunk-1"]

    async def test_buffer_streaming_response_different_types(self):
        """Test buffering iterator with different chunk types."""

        async def mixed_iterator():
            yield {"type": "dict"}
            yield "string"
            yield 42
            yield ["list", "item"]

        result = await buffer_streaming_response(mixed_iterator())

        expected = [{"type": "dict"}, "string", 42, ["list", "item"]]
        assert result == expected


class TestStreamingBuffer:
    """Tests for the StreamingBuffer class."""

    async def test_streaming_buffer_basic_iteration(self):
        """Test basic iteration through StreamingBuffer."""

        async def mock_iterator():
            for i in range(3):
                yield f"chunk-{i}"

        buffer = StreamingBuffer(mock_iterator())
        chunks = []

        async for chunk in buffer:
            chunks.append(chunk)

        assert chunks == ["chunk-0", "chunk-1", "chunk-2"]

    async def test_streaming_buffer_peek_functionality(self):
        """Test peek functionality without consuming chunks."""

        async def mock_iterator():
            for i in range(5):
                yield f"chunk-{i}"

        buffer = StreamingBuffer(mock_iterator())

        # Peek at first 2 chunks
        peeked = await buffer.peek(2)
        assert peeked == ["chunk-0", "chunk-1"]

        # Peek again should return same chunks
        peeked_again = await buffer.peek(2)
        assert peeked_again == ["chunk-0", "chunk-1"]

        # Now iterate and should get all chunks including peeked ones
        chunks = []
        async for chunk in buffer:
            chunks.append(chunk)

        assert chunks == ["chunk-0", "chunk-1", "chunk-2", "chunk-3", "chunk-4"]

    async def test_streaming_buffer_peek_more_than_available(self):
        """Test peeking more chunks than available in stream."""

        async def short_iterator():
            yield "chunk-0"
            yield "chunk-1"

        buffer = StreamingBuffer(short_iterator())

        # Try to peek 5 chunks when only 2 available
        peeked = await buffer.peek(5)
        assert peeked == ["chunk-0", "chunk-1"]

        # Should still be able to iterate through all chunks
        chunks = []
        async for chunk in buffer:
            chunks.append(chunk)

        assert chunks == ["chunk-0", "chunk-1"]

    async def test_streaming_buffer_peek_zero(self):
        """Test peeking zero chunks."""

        async def mock_iterator():
            yield "chunk-0"

        buffer = StreamingBuffer(mock_iterator())

        peeked = await buffer.peek(0)
        assert peeked == []

    async def test_streaming_buffer_empty_iterator(self):
        """Test StreamingBuffer with empty iterator."""

        async def empty_iterator():
            return
            yield  # unreachable

        buffer = StreamingBuffer(empty_iterator())

        # Peek should return empty list
        peeked = await buffer.peek(1)
        assert peeked == []

        # Iteration should produce no chunks
        chunks = []
        async for chunk in buffer:
            chunks.append(chunk)

        assert chunks == []

    async def test_streaming_buffer_multiple_peeks_and_iteration(self):
        """Test multiple peeks followed by iteration."""

        async def mock_iterator():
            for i in range(4):
                yield f"chunk-{i}"

        buffer = StreamingBuffer(mock_iterator())

        # First peek
        peeked1 = await buffer.peek(1)
        assert peeked1 == ["chunk-0"]

        # Second peek with more chunks
        peeked2 = await buffer.peek(3)
        assert peeked2 == ["chunk-0", "chunk-1", "chunk-2"]

        # Now iterate through all
        chunks = []
        async for chunk in buffer:
            chunks.append(chunk)

        assert chunks == ["chunk-0", "chunk-1", "chunk-2", "chunk-3"]

    async def test_streaming_buffer_partial_iteration_then_peek(self):
        """Test partial iteration followed by peek."""

        async def mock_iterator():
            for i in range(5):
                yield f"chunk-{i}"

        buffer = StreamingBuffer(mock_iterator())

        # Consume first chunk
        first_chunk = await buffer.__anext__()
        assert first_chunk == "chunk-0"

        # Peek at next chunks
        peeked = await buffer.peek(2)
        assert peeked == ["chunk-0", "chunk-1"]  # Buffer includes already consumed chunk

        # Continue iteration
        remaining_chunks = []
        async for chunk in buffer:
            remaining_chunks.append(chunk)

        assert remaining_chunks == ["chunk-1", "chunk-2", "chunk-3", "chunk-4"]

    async def test_streaming_buffer_exception_in_iterator(self):
        """Test StreamingBuffer handling iterator exceptions."""

        async def failing_iterator():
            yield "chunk-0"
            raise ValueError("Iterator failed")

        buffer = StreamingBuffer(failing_iterator())

        # Should get first chunk
        first_chunk = await buffer.__anext__()
        assert first_chunk == "chunk-0"

        # Next call should raise the exception
        with pytest.raises(ValueError, match="Iterator failed"):
            await buffer.__anext__()

    async def test_streaming_buffer_state_management(self):
        """Test internal state management of StreamingBuffer."""

        async def mock_iterator():
            for i in range(3):
                yield f"chunk-{i}"

        buffer = StreamingBuffer(mock_iterator())

        # Initial state
        assert buffer.buffer == []
        assert buffer.exhausted is False
        assert buffer.replay_position == 0

        # After peeking
        await buffer.peek(2)
        assert len(buffer.buffer) == 2
        assert buffer.exhausted is False
        assert buffer.replay_position == 0

        # After consuming one chunk
        await buffer.__anext__()
        assert buffer.replay_position == 1

        # After exhausting iterator
        chunks = []
        async for chunk in buffer:
            chunks.append(chunk)

        assert buffer.exhausted is True
        assert len(buffer.buffer) == 3
        assert buffer.replay_position == 3
