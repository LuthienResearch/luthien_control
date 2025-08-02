"""Base classes for streaming-aware control policies.

OpenAI Streaming Format:
    Streaming chunks from OpenAI are Pydantic models that can be converted to dict via model_dump().
    The typical structure follows the OpenAI chat completion streaming format:

    {
        "id": "chatcmpl-123",
        "object": "chat.completion.chunk",
        "created": 1677652288,
        "model": "gpt-4",
        "choices": [
            {
                "index": 0,
                "delta": {
                    "content": "text chunk here"
                },
                "finish_reason": null
            }
        ]
    }

    Policies should expect Pydantic models with model_dump() capability rather than
    raw strings or plain dictionaries.
"""

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Callable, Union

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.streaming_response import StreamingResponseIterator
from luthien_control.core.transaction import Transaction
from luthien_control.utils.streaming import StreamingBuffer

# Type alias for OpenAI streaming chunks
OpenAIStreamingChunk = Union[BaseModel, Any]  # Pydantic models with model_dump() method


class StreamingControlPolicy(ControlPolicy, ABC):
    """Base class for policies that need to process streaming responses.

    This class provides utilities for policies that need to:
    - Process streaming chunks as they arrive
    - Buffer streaming data for analysis
    - Modify or filter streaming responses

    Implementation Notes:
        - Streaming chunks are OpenAI Pydantic models with a 'choices' attribute
        - Use hasattr(chunk, "choices") to identify proper chunks
        - Content is typically found in chunk.choices[0]["delta"]["content"]
        - Policies can modify Pydantic objects in-place without serialization/deserialization
        - Use the process_openai_chunk_content() helper for safe content processing
    """

    async def apply(
        self, transaction: Transaction, container: DependencyContainer, session: AsyncSession
    ) -> Transaction:
        """Apply the policy to the transaction.

        For streaming transactions, this will handle the streaming logic appropriately.
        For non-streaming transactions, falls back to normal processing.
        """
        if transaction.is_streaming:
            return await self.apply_streaming(transaction, container, session)
        else:
            return await self.apply_non_streaming(transaction, container, session)

    @abstractmethod
    async def apply_streaming(
        self, transaction: Transaction, container: DependencyContainer, session: AsyncSession
    ) -> Transaction:
        """Apply the policy to a streaming transaction.

        This method should handle streaming responses appropriately.
        The default implementation wraps the existing iterator with processing logic.
        """
        raise NotImplementedError

    @abstractmethod
    async def apply_non_streaming(
        self, transaction: Transaction, container: DependencyContainer, session: AsyncSession
    ) -> Transaction:
        """Apply the policy to a non-streaming transaction.

        This should contain the normal policy logic for complete responses.
        """
        raise NotImplementedError

    def wrap_streaming_iterator(
        self,
        iterator: StreamingResponseIterator,
        transaction: Transaction,
        container: DependencyContainer,
        session: AsyncSession,
    ) -> StreamingResponseIterator:
        """Wrap a streaming iterator with policy-specific processing.

        This creates a new iterator that applies policy logic to each chunk.
        Subclasses can override this to implement chunk-level processing.
        """
        return PolicyWrappedIterator(iterator, self, transaction, container, session)

    async def process_chunk(
        self,
        chunk: OpenAIStreamingChunk,
        transaction: Transaction,
        container: DependencyContainer,
        session: AsyncSession,
    ) -> OpenAIStreamingChunk:
        """Process a single streaming chunk.

        Override this method to implement chunk-level processing logic.
        By default, chunks are passed through unchanged.

        OpenAI Chunk Format:
            Chunks are expected to be Pydantic models with model_dump() capability.
            When converted to dict, they typically have this structure:

            {
                "choices": [
                    {
                        "delta": {
                            "content": "actual text content to process"
                        }
                    }
                ]
            }

            Policies should check for hasattr(chunk, "model_dump") to identify
            proper OpenAI chunks vs. unexpected types.

        Args:
            chunk: The streaming chunk (typically a Pydantic model from OpenAI)
            transaction: The current transaction
            container: Dependency container
            session: Database session

        Returns:
            The processed chunk (can be modified, filtered, etc.)
        """
        return chunk

    def create_streaming_buffer(self, iterator: Any) -> StreamingBuffer:
        """Create a streaming buffer for policies that need to peek at data.

        Args:
            iterator: The async iterator to wrap

        Returns:
            A StreamingBuffer instance
        """
        return StreamingBuffer(iterator)

    def process_openai_chunk_content(
        self, chunk: OpenAIStreamingChunk, content_processor: Callable[[str], str]
    ) -> OpenAIStreamingChunk:
        """Helper method to safely process OpenAI chunk content in-place.

        This method handles the common pattern of processing content in OpenAI streaming chunks
        by directly modifying the Pydantic object without serialization/deserialization.

        Args:
            chunk: The OpenAI streaming chunk (Pydantic model)
            content_processor: Function that takes a string and returns processed string

        Returns:
            The same chunk object with modified content (modified in-place)

        Example:
            def my_processor(text: str) -> str:
                return text.upper()

            processed_chunk = self.process_openai_chunk_content(chunk, my_processor)
        """
        # Check if this is a Pydantic model with choices attribute
        if not hasattr(chunk, "choices"):
            self.logger.warning(
                f"Unexpected chunk type {type(chunk).__name__}, expected chunk with 'choices' attribute"
            )
            return chunk

        # Process OpenAI streaming format: chunk.choices = [{"delta": {"content": "text"}}]
        choices = getattr(chunk, "choices", None)
        if choices is not None and isinstance(choices, list):
            for choice in choices:
                if isinstance(choice, dict) and "delta" in choice:
                    delta = choice["delta"]
                    if isinstance(delta, dict) and "content" in delta and isinstance(delta["content"], str):
                        delta["content"] = content_processor(delta["content"])

        return chunk


class PolicyWrappedIterator(StreamingResponseIterator):
    """Iterator that applies policy processing to streaming chunks."""

    iterator: StreamingResponseIterator = Field(description="The wrapped iterator")
    policy: Any = Field(description="The policy instance")
    transaction: Any = Field(description="The transaction")
    container: Any = Field(description="The dependency container")
    session: Any = Field(description="The database session")

    def __init__(
        self,
        iterator: StreamingResponseIterator,
        policy: StreamingControlPolicy,
        transaction: Transaction,
        container: DependencyContainer,
        session: AsyncSession,
        **kwargs,
    ):
        kwargs.update(
            {
                "iterator": iterator,
                "policy": policy,
                "transaction": transaction,
                "container": container,
                "session": session,
            }
        )
        super().__init__(**kwargs)

    def __aiter__(self) -> AsyncIterator[Any]:
        return self

    async def __anext__(self) -> Any:
        import logging

        logger = logging.getLogger(__name__)

        # Get next chunk from wrapped iterator
        chunk = await self.iterator.__anext__()

        # Debug log chunk before policy processing
        logger.debug(
            "Chunk before policy processing",
            extra={
                "transaction_id": str(self.transaction.transaction_id),
                "policy_name": getattr(self.policy, "name", self.policy.__class__.__name__),
                "chunk_type": type(chunk).__name__,
                "chunk_preview": str(chunk)[:100] + "..." if len(str(chunk)) > 100 else str(chunk),
            },
        )

        # Apply policy processing
        processed_chunk = await self.policy.process_chunk(chunk, self.transaction, self.container, self.session)

        # Debug log chunk after policy processing
        logger.debug(
            "Chunk after policy processing",
            extra={
                "transaction_id": str(self.transaction.transaction_id),
                "policy_name": getattr(self.policy, "name", self.policy.__class__.__name__),
                "chunk_modified": processed_chunk != chunk,
                "processed_chunk_type": type(processed_chunk).__name__,
                "processed_chunk_preview": str(processed_chunk)[:100] + "..."
                if len(str(processed_chunk)) > 100
                else str(processed_chunk),
            },
        )

        return processed_chunk


class PassthroughStreamingPolicy(StreamingControlPolicy):
    """A streaming policy that passes through streaming responses unchanged.

    This is useful as a base class for policies that don't need to modify
    streaming data but want to be streaming-aware.
    """

    @classmethod
    def get_policy_type_name(cls) -> str:
        """Override to provide a custom type name."""
        return "passthrough_streaming"

    async def apply_streaming(
        self, transaction: Transaction, container: DependencyContainer, session: AsyncSession
    ) -> Transaction:
        """Pass through streaming responses unchanged."""
        # For passthrough, we don't need to wrap the iterator
        return transaction

    async def apply_non_streaming(
        self, transaction: Transaction, container: DependencyContainer, session: AsyncSession
    ) -> Transaction:
        """Pass through non-streaming responses unchanged."""
        return transaction
