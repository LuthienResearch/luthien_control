"""Tests for OpenAI streaming response models."""

from luthien_control.api.openai_chat_completions.datatypes import FunctionCall, ToolCall, Usage
from luthien_control.api.openai_chat_completions.streaming_response_models import (
    Delta,
    OpenAIStreamChunk,
    OpenAIStreamEvent,
    StreamingChoice,
)


class TestOpenAIStreamEvent:
    """Test OpenAIStreamEvent parsing and properties."""

    def test_parse_done_event(self):
        """Test parsing of [DONE] termination event."""
        event = OpenAIStreamEvent.from_sse_data("[DONE]")
        assert event.is_done
        assert not event.is_error
        assert not event.is_chunk
        assert event.raw_data == "[DONE]"

    def test_parse_error_event(self):
        """Test parsing of error event."""
        error_data = '{"error": {"message": "Test error", "type": "test_type", "code": "test_code"}}'
        event = OpenAIStreamEvent.from_sse_data(error_data)
        assert event.is_error
        assert not event.is_done
        assert not event.is_chunk
        assert event.error is not None
        assert event.error.message == "Test error"
        assert event.error.type == "test_type"
        assert event.error.code == "test_code"

    def test_parse_chunk_event(self):
        """Test parsing of a basic chunk event."""
        chunk_data = """{
            "id": "chatcmpl-123",
            "object": "chat.completion.chunk",
            "created": 1677652288,
            "model": "gpt-3.5-turbo",
            "choices": [{
                "index": 0,
                "delta": {"content": "Hello"},
                "finish_reason": null
            }]
        }"""
        event = OpenAIStreamEvent.from_sse_data(chunk_data)
        assert event.is_chunk
        assert not event.is_done
        assert not event.is_error
        assert event.chunk is not None
        assert event.chunk.id == "chatcmpl-123"
        assert event.chunk.object == "chat.completion.chunk"
        assert len(event.chunk.choices) == 1
        assert event.chunk.choices[0].delta.content == "Hello"

    def test_parse_invalid_json(self):
        """Test parsing of invalid JSON returns raw data."""
        invalid_data = "not valid json"
        event = OpenAIStreamEvent.from_sse_data(invalid_data)
        assert not event.is_chunk
        assert not event.is_done
        assert not event.is_error
        assert event.raw_data == "not valid json"


class TestOpenAIStreamChunk:
    """Test OpenAIStreamChunk model."""

    def test_basic_chunk_creation(self):
        """Test creating a basic stream chunk."""
        chunk = OpenAIStreamChunk(
            id="chatcmpl-123",
            object="chat.completion.chunk",
            created=1677652288,
            model="gpt-3.5-turbo",
            choices=[
                StreamingChoice(
                    index=0,
                    delta=Delta(content="Hello"),
                    finish_reason=None,
                )
            ],
        )
        assert chunk.id == "chatcmpl-123"
        assert chunk.model == "gpt-3.5-turbo"
        assert len(chunk.choices) == 1
        assert chunk.choices[0].delta.content == "Hello"

    def test_chunk_with_tool_calls(self):
        """Test chunk with tool calls."""
        chunk = OpenAIStreamChunk(
            id="chatcmpl-123",
            object="chat.completion.chunk",
            created=1677652288,
            model="gpt-3.5-turbo",
            choices=[
                StreamingChoice(
                    index=0,
                    delta=Delta(
                        tool_calls=[
                            ToolCall(
                                index=0,
                                id="call_abc123",
                                type="function",
                                function=FunctionCall(name="get_weather", arguments='{"location":'),
                            )
                        ]
                    ),
                    finish_reason=None,
                )
            ],
        )
        assert chunk.choices[0].delta.tool_calls is not None
        assert len(chunk.choices[0].delta.tool_calls) == 1
        assert chunk.choices[0].delta.tool_calls[0].id == "call_abc123"
        assert chunk.choices[0].delta.tool_calls[0].function is not None
        assert chunk.choices[0].delta.tool_calls[0].function.name == "get_weather"

    def test_chunk_with_usage(self):
        """Test final chunk with usage information."""
        chunk = OpenAIStreamChunk(
            id="chatcmpl-123",
            object="chat.completion.chunk",
            created=1677652288,
            model="gpt-3.5-turbo",
            choices=[],
            usage=Usage(
                prompt_tokens=10,
                completion_tokens=20,
                total_tokens=30,
            ),
        )
        assert chunk.usage is not None
        assert chunk.usage.prompt_tokens == 10
        assert chunk.usage.completion_tokens == 20
        assert chunk.usage.total_tokens == 30


class TestDelta:
    """Test Delta model."""

    def test_role_delta(self):
        """Test delta with role (first chunk)."""
        delta = Delta(role="assistant", content="")
        assert delta.role == "assistant"
        assert delta.content == ""

    def test_content_delta(self):
        """Test delta with content."""
        delta = Delta(content="Hello world")
        assert delta.content == "Hello world"
        assert delta.role is None

    def test_deprecated_function_call(self):
        """Test delta with deprecated function_call."""
        delta = Delta(
            function_call=FunctionCall(
                name="get_weather",
                arguments='{"location": "San Francisco"}',
            )
        )
        assert delta.function_call is not None
        assert delta.function_call.name == "get_weather"
        assert delta.function_call.arguments == '{"location": "San Francisco"}'
