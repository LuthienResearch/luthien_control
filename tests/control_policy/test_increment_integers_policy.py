"""Tests for the IncrementIntegersPolicy."""

from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from luthien_control.api.openai_chat_completions.datatypes import Choice, Message, Usage
from luthien_control.api.openai_chat_completions.request import OpenAIChatCompletionsRequest
from luthien_control.api.openai_chat_completions.response import OpenAIChatCompletionsResponse
from luthien_control.control_policy.increment_integers_policy import IncrementIntegersPolicy
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.raw_request import RawRequest
from luthien_control.core.raw_response import RawResponse
from luthien_control.core.request import Request
from luthien_control.core.response import Response
from luthien_control.core.streaming_response import ChunkedTextIterator
from luthien_control.core.transaction import Transaction
from psygnal.containers import EventedList
from pydantic import BaseModel


# Shared fixtures
@pytest.fixture
def policy() -> IncrementIntegersPolicy:
    """Provides an IncrementIntegersPolicy instance."""
    return IncrementIntegersPolicy()


@pytest.fixture
def mock_container() -> MagicMock:
    """Provides a mock dependency container."""
    return MagicMock()


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Provides a mock database session."""
    return AsyncMock()


@pytest.fixture
def openai_request() -> Request:
    """Provides a standard OpenAI request."""
    return Request(
        payload=OpenAIChatCompletionsRequest(
            model="gpt-4",
            messages=EventedList([Message(role="user", content="Test message")]),
        ),
        api_endpoint="https://api.openai.com/v1/chat/completions",
        api_key="test_key",
    )


@pytest.fixture
def openai_transaction(openai_request: Request) -> Transaction:
    """Provides a transaction with OpenAI request."""
    return Transaction(openai_request=openai_request)


@pytest.fixture
def openai_response_transaction(openai_request: Request) -> Transaction:
    """Provides a transaction with OpenAI request and response."""
    response = Response(
        payload=OpenAIChatCompletionsResponse(
            id="chatcmpl-123",
            object="chat.completion",
            created=1677652288,
            model="gpt-4",
            choices=EventedList(
                [
                    Choice(
                        index=0,
                        message=Message(role="assistant", content="Here are the numbers: 1, 2, 3, 4, 5"),
                        finish_reason="stop",
                    )
                ]
            ),
            usage=Usage(prompt_tokens=10, completion_tokens=15, total_tokens=25),
        )
    )
    return Transaction(openai_request=openai_request, openai_response=response)


class TestStringProcessing:
    """Test the core string processing functionality."""

    @pytest.mark.parametrize(
        "input_text,expected",
        [
            # Basic cases
            ("I have 5 apples", "I have 6 apples"),
            ("The year 2024 was great", "The year 2025 was great"),
            ("42", "43"),
            # Multiple integers
            ("I have 5 apples and 3 oranges, total 8 fruits", "I have 6 apples and 4 oranges, total 9 fruits"),
            # Negative integers
            ("Temperature is -5 degrees", "Temperature is -4 degrees"),
            ("Deficit of -100 dollars", "Deficit of -99 dollars"),
            # Zero
            ("Zero is 0", "Zero is 1"),
            # No integers
            ("Hello world", "Hello world"),
            ("No numbers here!", "No numbers here!"),
            # Decimals (note: individual parts get incremented)
            ("Price is 5.99 with tax of 10 percent", "Price is 6.100 with tax of 11 percent"),
            # Empty
            ("", ""),
        ],
    )
    def test_increment_integers_in_string(self, policy: IncrementIntegersPolicy, input_text: str, expected: str):
        """Test string processing with various inputs."""
        assert policy._increment_integers_in_string(input_text) == expected

    def test_increment_integers_in_string_none(self, policy: IncrementIntegersPolicy):
        """Test None input."""
        assert policy._increment_integers_in_string(None) is None


class TestNonStreamingResponses:
    """Test policy application with non-streaming responses."""

    @pytest.mark.asyncio
    async def test_openai_response_single_choice(
        self,
        policy: IncrementIntegersPolicy,
        openai_response_transaction: Transaction,
        mock_container: MagicMock,
        mock_db_session: AsyncMock,
    ):
        """Test that integers in OpenAI response content are incremented."""
        result = await policy.apply(openai_response_transaction, mock_container, mock_db_session)

        assert result.openai_response is not None
        assert result.openai_response.payload is not None
        choice = result.openai_response.payload.choices[0]
        assert choice.message.content == "Here are the numbers: 2, 3, 4, 5, 6"

    @pytest.mark.asyncio
    async def test_openai_response_multiple_choices(
        self,
        policy: IncrementIntegersPolicy,
        openai_request: Request,
        mock_container: MagicMock,
        mock_db_session: AsyncMock,
    ):
        """Test that integers in all OpenAI response choices are incremented."""
        response = Response(
            payload=OpenAIChatCompletionsResponse(
                id="chatcmpl-123",
                object="chat.completion",
                created=1677652288,
                model="gpt-4",
                choices=EventedList(
                    [
                        Choice(
                            index=0,
                            message=Message(role="assistant", content="Option 1: Buy 10 items"),
                            finish_reason="stop",
                        ),
                        Choice(
                            index=1,
                            message=Message(role="assistant", content="Option 2: Save 50 dollars"),
                            finish_reason="stop",
                        ),
                    ]
                ),
                usage=Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
            )
        )
        transaction = Transaction(openai_request=openai_request, openai_response=response)

        result = await policy.apply(transaction, mock_container, mock_db_session)

        assert result.openai_response is not None
        assert result.openai_response.payload is not None
        assert len(result.openai_response.payload.choices) == 2

        assert result.openai_response.payload.choices[0].message.content == "Option 2: Buy 11 items"
        assert result.openai_response.payload.choices[1].message.content == "Option 3: Save 51 dollars"


class TestStreamingResponses:
    """Test policy application with streaming responses."""

    @pytest.mark.asyncio
    async def test_streaming_wrapper_applied(
        self,
        policy: IncrementIntegersPolicy,
        openai_request: Request,
        mock_container: MagicMock,
        mock_db_session: AsyncMock,
    ):
        """Test that streaming responses are wrapped with processing iterator."""
        original_iterator = ChunkedTextIterator("Count: 1, 2, 3 items", chunk_size=5)
        response = Response(streaming_iterator=original_iterator)
        transaction = Transaction(openai_request=openai_request, openai_response=response)

        result = await policy.apply(transaction, mock_container, mock_db_session)

        assert result.openai_response is not None
        assert result.openai_response.streaming_iterator is not original_iterator
        assert hasattr(result.openai_response.streaming_iterator, "iterator")

    @pytest.mark.asyncio
    async def test_streaming_end_to_end(
        self,
        policy: IncrementIntegersPolicy,
        openai_request: Request,
        mock_container: MagicMock,
        mock_db_session: AsyncMock,
    ):
        """Test that streaming chunks are processed correctly end-to-end."""
        original_iterator = ChunkedTextIterator("Count 5 items and 10 more", chunk_size=8)
        response = Response(streaming_iterator=original_iterator)
        transaction = Transaction(openai_request=openai_request, openai_response=response)

        result = await policy.apply(transaction, mock_container, mock_db_session)

        # Collect all processed chunks
        chunks = []
        assert result.openai_response is not None
        assert result.openai_response.streaming_iterator is not None
        async for chunk in result.openai_response.streaming_iterator:
            chunks.append(chunk)

        processed_text = "".join(chunks)
        assert processed_text == "Count 6 items and 11 more"


class TestChunkProcessing:
    """Test individual chunk processing functionality."""

    @pytest.mark.parametrize(
        "chunk,expected",
        [
            # String chunks
            ("I have 5 apples", "I have 6 apples"),
            ("Buy 2 apples and 3 oranges", "Buy 3 apples and 4 oranges"),
            # Dictionary chunks
            (
                {"content": "I have 5 apples", "other": "unchanged"},
                {"content": "I have 6 apples", "other": "unchanged"},
            ),
            # OpenAI streaming format
            (
                {"choices": [{"delta": {"content": "Count to 5"}, "index": 0}]},
                {"choices": [{"delta": {"content": "Count to 6"}, "index": 0}]},
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_process_chunk_types(
        self,
        policy: IncrementIntegersPolicy,
        openai_transaction: Transaction,
        mock_container: MagicMock,
        mock_db_session: AsyncMock,
        chunk,
        expected,
    ):
        """Test processing of different chunk types."""
        result = await policy.process_chunk(chunk, openai_transaction, mock_container, mock_db_session)
        assert result == expected

    @pytest.mark.asyncio
    async def test_process_chunk_pydantic_model(
        self,
        policy: IncrementIntegersPolicy,
        openai_transaction: Transaction,
        mock_container: MagicMock,
        mock_db_session: AsyncMock,
    ):
        """Test processing of Pydantic model chunks."""

        class TestChunk(BaseModel):
            content: str
            metadata: str = "test"

        chunk = TestChunk(content="I have 7 items", metadata="unchanged")
        result = await policy.process_chunk(chunk, openai_transaction, mock_container, mock_db_session)

        assert isinstance(result, TestChunk)
        assert result.content == "I have 8 items"
        assert result.metadata == "unchanged"

    @pytest.mark.asyncio
    async def test_process_chunk_unknown_type(
        self,
        policy: IncrementIntegersPolicy,
        openai_transaction: Transaction,
        mock_container: MagicMock,
        mock_db_session: AsyncMock,
    ):
        """Test processing of unknown chunk types."""

        class CustomChunk:
            def __str__(self):
                return "Custom chunk with 9 items"

        chunk = CustomChunk()
        result = await policy.process_chunk(chunk, openai_transaction, mock_container, mock_db_session)
        assert result == "Custom chunk with 10 items"


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_raw_request_ignored(
        self, policy: IncrementIntegersPolicy, mock_container: MagicMock, mock_db_session: AsyncMock
    ):
        """Test that policy ignores raw requests."""
        request = RawRequest(
            method="POST",
            path="/endpoint",
            headers={"Content-Type": "application/json"},
            body=b'{"query": "count 5 items"}',
            api_key="test_key",
        )
        response = RawResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
            content="The count is 42 and the limit is 100",
        )
        transaction = Transaction(raw_request=request, raw_response=response)

        result = await policy.apply(transaction, mock_container, mock_db_session)

        assert result is transaction
        assert result.raw_response is not None
        assert result.raw_response.content == "The count is 42 and the limit is 100"  # Unchanged

    @pytest.mark.asyncio
    async def test_no_response(
        self,
        policy: IncrementIntegersPolicy,
        openai_transaction: Transaction,
        mock_container: MagicMock,
        mock_db_session: AsyncMock,
    ):
        """Test policy behavior when transaction has no response."""
        result = await policy.apply(openai_transaction, mock_container, mock_db_session)
        assert result is openai_transaction

    @pytest.mark.asyncio
    async def test_empty_content(
        self,
        policy: IncrementIntegersPolicy,
        openai_request: Request,
        mock_container: MagicMock,
        mock_db_session: AsyncMock,
    ):
        """Test policy behavior with empty response content."""
        response = Response(
            payload=OpenAIChatCompletionsResponse(
                id="chatcmpl-123",
                object="chat.completion",
                created=1677652288,
                model="gpt-4",
                choices=EventedList(
                    [Choice(index=0, message=Message(role="assistant", content=""), finish_reason="stop")]
                ),
                usage=Usage(prompt_tokens=10, completion_tokens=0, total_tokens=10),
            )
        )
        transaction = Transaction(openai_request=openai_request, openai_response=response)

        result = await policy.apply(transaction, mock_container, mock_db_session)

        assert result.openai_response is not None
        assert result.openai_response.payload is not None
        assert result.openai_response.payload.choices[0].message.content == ""


class TestSerialization:
    """Test policy serialization and deserialization."""

    def test_initialization_default_name(self):
        """Test policy initialization with default name."""
        policy = IncrementIntegersPolicy()
        assert policy.name == "IncrementIntegersPolicy"

    def test_initialization_custom_name(self):
        """Test policy initialization with custom name."""
        custom_name = "MyIncrementPolicy"
        policy = IncrementIntegersPolicy(name=custom_name)
        assert policy.name == custom_name

    def test_serialization(self):
        """Test policy serialization."""
        policy = IncrementIntegersPolicy()
        serialized = policy.serialize()
        assert serialized["type"] == "IncrementIntegers"
        assert serialized["name"] == "IncrementIntegersPolicy"

    def test_from_serialized(self):
        """Test policy deserialization."""
        config = cast(SerializableDict, {"name": "DeserializedIncrementPolicy", "type": "IncrementIntegers"})
        policy = IncrementIntegersPolicy.from_serialized(config)
        assert isinstance(policy, IncrementIntegersPolicy)
        assert policy.name == "DeserializedIncrementPolicy"

    def test_round_trip_serialization(self):
        """Test complete serialization round trip."""
        original_policy = IncrementIntegersPolicy(name="RoundTripIncrementPolicy")

        serialized = original_policy.serialize()
        restored_policy = IncrementIntegersPolicy.from_serialized(serialized)

        assert restored_policy.name == original_policy.name
        assert restored_policy.serialize() == original_policy.serialize()
