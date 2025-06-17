from luthien_control.api.openai_chat_completions.datatypes import Message
from luthien_control.api.openai_chat_completions.request import (
    OpenAIChatCompletionsRequest,
)
from psygnal.containers import EventedList


def test_openai_chat_completions_request_instantiation():
    """Test that OpenAIChatCompletionsRequest can be instantiated."""
    instance = OpenAIChatCompletionsRequest(
        model="gpt-4",
        messages=EventedList([Message(role="user", content="Hello, world!")]),
    )
    assert isinstance(instance, OpenAIChatCompletionsRequest)
    assert instance.model == "gpt-4"
    assert len(instance.messages) == 1
    assert instance.messages[0].role == "user"
    assert instance.messages[0].content == "Hello, world!"
