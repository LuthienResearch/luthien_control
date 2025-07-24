from unittest.mock import Mock

import pytest
from luthien_control.api.openai_chat_completions.datatypes import Choice, Message, Usage
from luthien_control.api.openai_chat_completions.response import (
    OpenAIChatCompletionsResponse,
)
from psygnal.containers import EventedList


@pytest.fixture
def minimal_response():
    """A response with only the required fields."""
    return OpenAIChatCompletionsResponse(
        id="chatcmpl-123",
        object="chat.completion",
        created=1677652288,
        model="gpt-3.5-turbo-0125",
    )


def test_openai_chat_completions_response_instantiation(minimal_response):
    """Test that OpenAIChatCompletionsResponse can be instantiated."""
    assert isinstance(minimal_response, OpenAIChatCompletionsResponse)
    assert minimal_response.id == "chatcmpl-123"


def test_response_default_factories():
    """Test the default factories for 'choices' and 'usage'."""
    response = OpenAIChatCompletionsResponse(id="id", object="obj", created=1, model="mod")
    assert isinstance(response.choices, EventedList)
    assert len(response.choices) == 0
    assert isinstance(response.usage, Usage)
    assert response.usage.prompt_tokens == 0
    assert response.usage.completion_tokens == 0
    assert response.usage.total_tokens == 0


def test_response_evented_list_modification(minimal_response):
    """Test that modifying the 'choices' list emits a 'changed' signal."""
    mock_callback = Mock()
    minimal_response.changed.connect(mock_callback)

    new_choice = Choice(index=0, message=Message(role="assistant", content="Hello"), finish_reason="stop")
    minimal_response.choices.append(new_choice)

    assert len(minimal_response.choices) == 1
    assert minimal_response.choices[0] == new_choice
    mock_callback.assert_called()


def test_response_nested_model_modification(minimal_response):
    """Test that modifying the 'usage' model emits a 'changed' signal."""
    mock_callback = Mock()
    minimal_response.changed.connect(mock_callback)

    minimal_response.usage.prompt_tokens = 50
    assert minimal_response.usage.prompt_tokens == 50
    mock_callback.assert_called_once()
    mock_callback.reset_mock()

    minimal_response.usage.completion_tokens = 100
    assert minimal_response.usage.completion_tokens == 100
    mock_callback.assert_called_once()
    mock_callback.reset_mock()

    minimal_response.usage.total_tokens = 150
    assert minimal_response.usage.total_tokens == 150
    mock_callback.assert_called_once()


def test_response_set_optional_fields(minimal_response):
    """Test setting optional fields on the response."""
    mock_callback = Mock()
    minimal_response.changed.connect(mock_callback)

    minimal_response.service_tier = "premium"
    assert minimal_response.service_tier == "premium"
    mock_callback.assert_called_once()
    mock_callback.reset_mock()

    minimal_response.system_fingerprint = "fp_abc123"
    assert minimal_response.system_fingerprint == "fp_abc123"
    mock_callback.assert_called_once()
