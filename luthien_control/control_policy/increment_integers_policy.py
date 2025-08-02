import re
from typing import Any, Optional

from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.control_policy.streaming_policy import StreamingControlPolicy
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.request_type import RequestType
from luthien_control.core.transaction import Transaction


class IncrementIntegersPolicy(StreamingControlPolicy):
    """A policy that adds 1 to any integer found in OpenAI response continuation text.

    Toy policy to demonstrate acting on OpenAI responses.
    Increments all integers by 1.
    """

    name: Optional[str] = Field(default="IncrementIntegersPolicy")

    def _increment_integers_in_string(self, text: str) -> str:
        """Replace all integers in a string with their value + 1."""
        if not text:
            return text

        def increment_match(match):
            integer_value = int(match.group())
            return str(integer_value + 1)

        # Match integers (including negative numbers)
        # Pattern explanation: -?\d+ matches optional minus sign followed by one or more digits
        return re.sub(r"-?\d+", increment_match, text)

    async def apply_streaming(
        self, transaction: Transaction, container: DependencyContainer, session: AsyncSession
    ) -> Transaction:
        """Apply the policy to a streaming OpenAI transaction.

        For streaming responses, wrap the iterator to process chunks as they arrive.
        """
        # Only handle OpenAI chat completion responses
        if transaction.request_type == RequestType.OPENAI_CHAT and transaction.openai_response:
            response = transaction.openai_response

            if response.streaming_iterator:
                # Wrap the streaming iterator to process chunks
                wrapped_iterator = self.wrap_streaming_iterator(
                    response.streaming_iterator, transaction, container, session
                )
                response.streaming_iterator = wrapped_iterator
                self.logger.info("Streaming OpenAI response wrapped for integer incrementation")

        return transaction

    async def apply_non_streaming(
        self, transaction: Transaction, container: DependencyContainer, session: AsyncSession
    ) -> Transaction:
        """Apply the policy to a non-streaming OpenAI transaction.

        For non-streaming responses, process the complete message content.
        """
        # Only handle OpenAI chat completion responses
        if transaction.request_type == RequestType.OPENAI_CHAT and transaction.openai_response:
            response = transaction.openai_response

            # Handle non-streaming responses
            if response.payload and response.payload.choices:
                for choice in response.payload.choices:
                    if choice.message and choice.message.content:
                        choice.message.content = self._increment_integers_in_string(choice.message.content)

        return transaction

    async def process_chunk(
        self, chunk: Any, transaction: Transaction, container: DependencyContainer, session: AsyncSession
    ) -> Any:
        """Process a single streaming chunk to increment integers.

        Uses the StreamingControlPolicy helper method to safely process OpenAI chunk content.
        This demonstrates the recommended pattern for processing streaming chunks.

        Args:
            chunk: The OpenAI streaming chunk (Pydantic model)
            transaction: The current transaction
            container: Dependency container
            session: Database session

        Returns:
            The processed chunk with integers incremented
        """

        # Use the helper method to process OpenAI chunk content
        # Create a wrapper that handles the Optional[str] -> Optional[str] signature
        def increment_wrapper(text: str) -> str:
            result = self._increment_integers_in_string(text)
            return result if result is not None else text

        return self.process_openai_chunk_content(chunk, increment_wrapper)
