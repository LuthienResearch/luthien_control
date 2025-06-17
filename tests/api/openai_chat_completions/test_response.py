from luthien_control.api.openai_chat_completions.datatypes import Choice, Usage
from luthien_control.api.openai_chat_completions.response import (
    OpenAIChatCompletionsResponse,
)
from psygnal.containers import EventedList


def test_openai_chat_completions_response_instantiation():
    """Test that OpenAIChatCompletionsResponse can be instantiated."""
    instance = OpenAIChatCompletionsResponse(
        id="chatcmpl-123",
        object="chat.completion",
        created=1677652288,
        model="gpt-3.5-turbo-0125",
        choices=EventedList[Choice](),
        usage=Usage(prompt_tokens=56, completion_tokens=31, total_tokens=87),
    )
    assert isinstance(instance, OpenAIChatCompletionsResponse)
