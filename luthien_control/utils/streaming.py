"""Utilities for handling streaming responses."""

import json
import logging
from typing import Any, AsyncIterator, Dict, Optional

logger = logging.getLogger(__name__)


async def format_sse_chunk(data: Dict[str, Any], event: Optional[str] = None) -> str:
    """Format a data chunk as Server-Sent Events (SSE) format.

    Args:
        data: The data to send as a JSON object
        event: Optional event type

    Returns:
        SSE-formatted string
    """
    lines = []

    if event:
        lines.append(f"event: {event}")

    # Format data as JSON and prefix each line with "data: "
    json_str = json.dumps(data, separators=(",", ":"))
    lines.append(f"data: {json_str}")

    # SSE requires double newline after data
    return "\n".join(lines) + "\n\n"


async def format_openai_streaming_chunk(chunk: Any) -> str:
    """Format an OpenAI streaming chunk for SSE transmission.

    Args:
        chunk: OpenAI streaming chunk object

    Returns:
        SSE-formatted string
    """
    # Handle different chunk types
    if hasattr(chunk, "model_dump"):
        # It's a Pydantic model, convert to dict
        chunk_data = chunk.model_dump()
    elif hasattr(chunk, "to_dict"):
        # Some objects have to_dict method
        chunk_data = chunk.to_dict()
    elif isinstance(chunk, dict):
        # Already a dict
        chunk_data = chunk
    else:
        # Try to convert to dict representation
        chunk_data = {"content": str(chunk)}

    return await format_sse_chunk(chunk_data)


async def format_streaming_error(error: Exception, transaction_id: Optional[str] = None) -> str:
    """Format an error for streaming response.

    Args:
        error: The exception that occurred
        transaction_id: Optional transaction ID for debugging

    Returns:
        SSE-formatted error string
    """
    error_data: Dict[str, Any] = {"error": {"type": error.__class__.__name__, "message": str(error)}}

    if transaction_id:
        error_data["transaction_id"] = transaction_id
    logger.error(f"Streaming error: {error_data}")

    return await format_sse_chunk({"error": error.__class__.__name__}, event="error")


async def buffer_streaming_response(iterator: AsyncIterator[Any], max_chunks: Optional[int] = None) -> list[Any]:
    """Buffer a streaming response into a list of chunks.

    This is useful for policies that need to examine the complete response
    before allowing it to proceed.

    Args:
        iterator: The async iterator to buffer
        max_chunks: Maximum number of chunks to buffer (None for unlimited)

    Returns:
        List of buffered chunks
    """
    chunks = []
    count = 0

    async for chunk in iterator:
        chunks.append(chunk)
        count += 1

        if max_chunks and count >= max_chunks:
            break

    return chunks


class StreamingBuffer:
    """A buffer that can replay streaming chunks.

    This is useful for policies that need to examine streaming data
    but still allow it to be streamed to the client.
    """

    def __init__(self, iterator: AsyncIterator[Any]):
        """Initialize with an async iterator."""
        self.iterator = iterator
        self.buffer: list[Any] = []
        self.exhausted = False
        self.replay_position = 0

    async def peek(self, n: int = 1) -> list[Any]:
        """Peek at the next n chunks without consuming them.

        Args:
            n: Number of chunks to peek at

        Returns:
            List of chunks (may be shorter than n if stream ends)
        """
        # Ensure we have enough chunks buffered
        while len(self.buffer) < n and not self.exhausted:
            try:
                chunk = await self.iterator.__anext__()
                self.buffer.append(chunk)
            except StopAsyncIteration:
                self.exhausted = True
                break

        return self.buffer[:n]

    def __aiter__(self) -> AsyncIterator[Any]:
        """Return self as async iterator."""
        return self

    async def __anext__(self) -> Any:
        """Get next chunk, either from buffer or iterator."""
        # If we're replaying from buffer
        if self.replay_position < len(self.buffer):
            chunk = self.buffer[self.replay_position]
            self.replay_position += 1
            return chunk

        # If we've exhausted the iterator
        if self.exhausted:
            raise StopAsyncIteration

        # Get new chunk from iterator
        try:
            chunk = await self.iterator.__anext__()
            self.buffer.append(chunk)
            self.replay_position += 1
            return chunk
        except StopAsyncIteration:
            self.exhausted = True
            raise
