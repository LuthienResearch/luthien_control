"""Tests for enhanced OpenAI streaming iterator with semantic structure."""

import asyncio
import json

import pytest
from luthien_control.api.openai_chat_completions.streaming_response_models import OpenAIStreamEvent
from luthien_control.core.streaming_response import OpenAIStreamingIterator


class MockPydanticChunk:
    """Mock pydantic-like chunk with model_dump_json method."""

    def __init__(self, data: dict):
        self.data = data

    def model_dump_json(self) -> str:
        return json.dumps(self.data)


class MockOpenAIStream:
    """Mock OpenAI stream for testing."""

    def __init__(self, chunks: list[dict]):
        self.chunks = [MockPydanticChunk(chunk) for chunk in chunks]
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self.chunks):
            raise StopAsyncIteration
        chunk = self.chunks[self.index]
        self.index += 1
        # Simulate a small delay
        await asyncio.sleep(0.01)
        return chunk


class TestEnhancedOpenAIStreamingIterator:
    """Test enhanced OpenAI streaming iterator functionality."""

    @pytest.mark.asyncio
    async def test_parse_basic_chunks(self):
        """Test parsing basic content chunks."""
        chunks = [
            {
                "id": "chatcmpl-123",
                "object": "chat.completion.chunk",
                "created": 1677652288,
                "model": "gpt-3.5-turbo",
                "choices": [{"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}],
            },
            {
                "id": "chatcmpl-123",
                "object": "chat.completion.chunk",
                "created": 1677652288,
                "model": "gpt-3.5-turbo",
                "choices": [{"index": 0, "delta": {"content": "Hello"}, "finish_reason": None}],
            },
            {
                "id": "chatcmpl-123",
                "object": "chat.completion.chunk",
                "created": 1677652288,
                "model": "gpt-3.5-turbo",
                "choices": [{"index": 0, "delta": {"content": " world"}, "finish_reason": None}],
            },
            {
                "id": "chatcmpl-123",
                "object": "chat.completion.chunk",
                "created": 1677652288,
                "model": "gpt-3.5-turbo",
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            },
        ]

        stream = MockOpenAIStream(chunks)
        iterator = OpenAIStreamingIterator(stream=stream)

        events = []
        async for event in iterator:
            events.append(event)

        assert len(events) == 4
        assert all(isinstance(event, OpenAIStreamEvent) for event in events)
        assert all(event.is_chunk for event in events)

        # Check first chunk has role
        assert events[0].chunk.choices[0].delta.role == "assistant"
        assert events[0].chunk.choices[0].delta.content == ""

        # Check content chunks
        assert events[1].chunk.choices[0].delta.content == "Hello"
        assert events[2].chunk.choices[0].delta.content == " world"

        # Check final chunk
        assert events[3].chunk.choices[0].finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_parse_tool_call_chunks(self):
        """Test parsing chunks with tool calls."""
        chunks = [
            {
                "id": "chatcmpl-123",
                "object": "chat.completion.chunk",
                "created": 1677652288,
                "model": "gpt-3.5-turbo",
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call_abc123",
                                    "type": "function",
                                    "function": {"name": "get_weather", "arguments": ""},
                                }
                            ]
                        },
                        "finish_reason": None,
                    }
                ],
            },
            {
                "id": "chatcmpl-123",
                "object": "chat.completion.chunk",
                "created": 1677652288,
                "model": "gpt-3.5-turbo",
                "choices": [
                    {
                        "index": 0,
                        "delta": {"tool_calls": [{"index": 0, "function": {"arguments": '{"location":'}}]},
                        "finish_reason": None,
                    }
                ],
            },
            {
                "id": "chatcmpl-123",
                "object": "chat.completion.chunk",
                "created": 1677652288,
                "model": "gpt-3.5-turbo",
                "choices": [
                    {
                        "index": 0,
                        "delta": {"tool_calls": [{"index": 0, "function": {"arguments": ' "San Francisco"}'}}]},
                        "finish_reason": None,
                    }
                ],
            },
        ]

        stream = MockOpenAIStream(chunks)
        iterator = OpenAIStreamingIterator(stream=stream)

        events = []
        async for event in iterator:
            events.append(event)

        assert len(events) == 3
        assert events[0].chunk.choices[0].delta.tool_calls[0].id == "call_abc123"
        assert events[0].chunk.choices[0].delta.tool_calls[0].function.name == "get_weather"
        assert events[1].chunk.choices[0].delta.tool_calls[0].function.arguments == '{"location":'
        assert events[2].chunk.choices[0].delta.tool_calls[0].function.arguments == ' "San Francisco"}'

    @pytest.mark.asyncio
    async def test_exhausted_state(self):
        """Test that iterator properly tracks exhausted state."""
        chunks = [{"id": "test", "content": "single chunk"}]

        stream = MockOpenAIStream(chunks)
        iterator = OpenAIStreamingIterator(stream=stream)

        # Consume the single chunk (should be parsed into OpenAIStreamEvent)
        event = await iterator.__anext__()
        assert hasattr(event, "raw_data")  # Should be parsed as raw_data since it's not valid JSON

        # Should raise StopAsyncIteration
        with pytest.raises(StopAsyncIteration):
            await iterator.__anext__()

        # Should still raise on subsequent calls
        with pytest.raises(StopAsyncIteration):
            await iterator.__anext__()


class TestChunkParsing:
    """Test chunk format parsing."""

    def test_parse_pydantic_chunk(self):
        """Test parsing pydantic chunk from OpenAI SDK."""
        chunk_data = {
            "id": "chatcmpl-123",
            "object": "chat.completion.chunk",
            "created": 1677652288,
            "model": "gpt-3.5-turbo",
            "choices": [],
        }
        chunk = MockPydanticChunk(chunk_data)

        iterator = OpenAIStreamingIterator(stream=None)
        event = iterator._parse_chunk(chunk)

        assert event.is_chunk
        assert event.chunk is not None
        assert event.chunk.id == "chatcmpl-123"

    def test_parse_invalid_chunk_fails_fast(self):
        """Test that invalid chunks fail fast with AttributeError."""
        invalid_chunk = {"id": "not_pydantic"}

        iterator = OpenAIStreamingIterator(stream=None)

        with pytest.raises(AttributeError):
            iterator._parse_chunk(invalid_chunk)
