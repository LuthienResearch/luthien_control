"""Base classes for streaming-aware control policies."""

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.streaming_response import StreamingResponseIterator
from luthien_control.core.transaction import Transaction
from luthien_control.utils.streaming import StreamingBuffer


class StreamingControlPolicy(ControlPolicy, ABC):
    """Base class for policies that need to process streaming responses.

    This class provides utilities for policies that need to:
    - Process streaming chunks as they arrive
    - Buffer streaming data for analysis
    - Modify or filter streaming responses
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
        self, chunk: Any, transaction: Transaction, container: DependencyContainer, session: AsyncSession
    ) -> Any:
        """Process a single streaming chunk.

        Override this method to implement chunk-level processing logic.
        By default, chunks are passed through unchanged.

        Args:
            chunk: The streaming chunk to process
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
        # Get next chunk from wrapped iterator
        chunk = await self.iterator.__anext__()

        # Apply policy processing
        processed_chunk = await self.policy.process_chunk(chunk, self.transaction, self.container, self.session)

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
