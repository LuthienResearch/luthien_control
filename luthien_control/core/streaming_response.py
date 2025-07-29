"""Streaming response types for handling async iterators in the framework."""

import abc
from typing import Any, AsyncIterator, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class StreamingResponseIterator(BaseModel, abc.ABC):
    """Base class for streaming response iterators.

    This class wraps async iterators to provide a consistent interface
    for streaming responses throughout the framework.
    """

    model_config = {"arbitrary_types_allowed": True}

    @abc.abstractmethod
    def __aiter__(self) -> AsyncIterator[Any]:
        """Return the async iterator for streaming data."""
        raise NotImplementedError

    @abc.abstractmethod
    async def __anext__(self) -> Any:
        """Get the next chunk from the stream."""
        raise NotImplementedError


class OpenAIStreamingIterator(StreamingResponseIterator):
    """Wrapper for OpenAI async streaming responses.

    This class wraps the OpenAI SDK's AsyncStream objects to provide
    a consistent interface for processing streaming chat completions.
    """

    stream: Any = Field(description="The OpenAI AsyncStream object")
    exhausted: bool = Field(default=False, exclude=True)

    def __init__(self, stream: Any, **kwargs):
        """Initialize with an OpenAI AsyncStream object."""
        kwargs["stream"] = stream
        super().__init__(**kwargs)

    def __aiter__(self) -> AsyncIterator[Any]:
        """Return self as the async iterator."""
        return self

    async def __anext__(self) -> Any:
        """Get the next chunk from the OpenAI stream."""
        if self.exhausted:
            raise StopAsyncIteration

        try:
            # The OpenAI AsyncStream should handle its own iteration
            return await self.stream.__anext__()
        except StopAsyncIteration:
            self.exhausted = True
            raise


class RawStreamingIterator(StreamingResponseIterator):
    """Wrapper for raw HTTP streaming responses.

    This class wraps raw HTTP response streams (e.g., from httpx)
    to provide a consistent interface for processing streaming data.
    """

    response: Any = Field(description="The HTTP response object with streaming capability")
    chunk_size: int = Field(default=8192, description="Size of chunks to read from the stream")
    exhausted: bool = Field(default=False, exclude=True)
    iter_cache: Any = Field(default=None, exclude=True)

    def __init__(self, response: Any, chunk_size: int = 8192, **kwargs):
        """Initialize with an HTTP response object."""
        kwargs["response"] = response
        kwargs["chunk_size"] = chunk_size
        super().__init__(**kwargs)

    def __aiter__(self) -> AsyncIterator[bytes]:
        """Return self as the async iterator."""
        return self

    async def __anext__(self) -> bytes:
        """Get the next chunk from the HTTP stream."""
        if self.exhausted:
            raise StopAsyncIteration

        try:
            # For httpx responses, use aiter_bytes()
            if hasattr(self.response, "aiter_bytes"):
                # We need to store the iterator to avoid recreating it
                if self.iter_cache is None:
                    self.iter_cache = self.response.aiter_bytes(self.chunk_size)
                return await self.iter_cache.__anext__()
            else:
                # Fallback for other response types
                chunk = await self.response.read(self.chunk_size)
                if not chunk:
                    self.exhausted = True
                    raise StopAsyncIteration
                return chunk
        except StopAsyncIteration:
            self.exhausted = True
            raise


class ChunkedTextIterator(StreamingResponseIterator):
    """Iterator for text that needs to be chunked for streaming.

    This is useful for converting non-streaming responses into
    streaming format for consistent handling.
    """

    text: str = Field(description="The text to be chunked")
    chunk_size: int = Field(default=1024, description="Size of text chunks")
    position: int = Field(default=0, exclude=True)

    def __init__(self, text: str, chunk_size: int = 1024, **kwargs):
        """Initialize with text to be chunked."""
        kwargs["text"] = text
        kwargs["chunk_size"] = chunk_size
        super().__init__(**kwargs)

    def __aiter__(self) -> AsyncIterator[str]:
        """Return self as the async iterator."""
        return self

    async def __anext__(self) -> str:
        """Get the next chunk of text."""
        if self.position >= len(self.text):
            raise StopAsyncIteration

        chunk = self.text[self.position : self.position + self.chunk_size]
        self.position += self.chunk_size
        return chunk
