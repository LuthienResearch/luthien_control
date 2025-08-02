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

    def _increment_integers_in_string(self, text: Optional[str]) -> Optional[str]:
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

        Args:
            chunk: The streaming chunk (could be string, dict, or OpenAI chunk object)
            transaction: The current transaction
            container: Dependency container
            session: Database session

        Returns:
            The processed chunk with integers incremented
        """
        # Handle different chunk types that might contain text content
        if isinstance(chunk, str):
            # Simple string chunk - process directly
            return self._increment_integers_in_string(chunk)
        elif isinstance(chunk, dict):
            # Dictionary chunk - look for content fields and process them
            processed_chunk = chunk.copy()
            if "content" in processed_chunk and isinstance(processed_chunk["content"], str):
                processed_chunk["content"] = self._increment_integers_in_string(processed_chunk["content"])
            # Also check for OpenAI streaming format
            if "choices" in processed_chunk and isinstance(processed_chunk["choices"], list):
                for choice in processed_chunk["choices"]:
                    if isinstance(choice, dict) and "delta" in choice:
                        delta = choice["delta"]
                        if isinstance(delta, dict) and "content" in delta and isinstance(delta["content"], str):
                            delta["content"] = self._increment_integers_in_string(delta["content"])
            return processed_chunk
        elif hasattr(chunk, "model_dump"):
            # Pydantic model - convert to dict, process, and return modified version
            chunk_dict = chunk.model_dump()
            processed_dict = await self.process_chunk(chunk_dict, transaction, container, session)
            # Try to reconstruct the original object type with processed data
            try:
                return chunk.__class__(**processed_dict)
            except Exception:
                # If reconstruction fails, return the processed dict
                return processed_dict
        else:
            # Unknown chunk type - try to convert to string and process
            chunk_str = str(chunk)
            processed_str = self._increment_integers_in_string(chunk_str)
            # If processing changed the string, log it and return the processed version
            if processed_str != chunk_str:
                self.logger.debug(f"Processed unknown chunk type {type(chunk).__name__}: {chunk_str[:50]}...")
                return processed_str
            return chunk
