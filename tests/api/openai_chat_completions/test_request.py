from unittest.mock import Mock

import pytest
from luthien_control.api.openai_chat_completions.datatypes import (
    FunctionDefinition,
    Message,
    RequestFunctionCall,
)
from luthien_control.api.openai_chat_completions.request import (
    OpenAIChatCompletionsRequest,
)
from psygnal.containers import EventedDict, EventedList


@pytest.fixture
def minimal_request():
    """A request with only the required fields."""
    return OpenAIChatCompletionsRequest(
        model="gpt-4",
        messages=EventedList([Message(role="user", content="Hello, world!")]),
    )


def test_openai_chat_completions_request_instantiation(minimal_request):
    """Test that OpenAIChatCompletionsRequest can be instantiated."""
    instance = minimal_request
    assert isinstance(instance, OpenAIChatCompletionsRequest)
    assert instance.model == "gpt-4"
    assert len(instance.messages) == 1
    assert instance.messages[0].role == "user"
    assert instance.messages[0].content == "Hello, world!"


def test_request_optional_fields_default_to_none(minimal_request):
    """Test that optional fields are None by default."""
    assert minimal_request.frequency_penalty is None
    assert minimal_request.logit_bias is None
    assert minimal_request.max_tokens is None
    assert minimal_request.n is None
    assert minimal_request.presence_penalty is None
    assert minimal_request.seed is None
    assert minimal_request.stream is None
    assert minimal_request.temperature is None
    assert minimal_request.top_p is None
    assert minimal_request.user is None


def test_request_set_optional_fields(minimal_request):
    """Test setting optional fields on the request."""
    mock_callback = Mock()
    minimal_request.changed.connect(mock_callback)

    minimal_request.temperature = 0.8
    assert minimal_request.temperature == 0.8
    mock_callback.assert_called_once()
    mock_callback.reset_mock()

    minimal_request.stream = True
    assert minimal_request.stream is True
    mock_callback.assert_called_once()
    mock_callback.reset_mock()

    minimal_request.user = "test-user"
    assert minimal_request.user == "test-user"
    mock_callback.assert_called_once()


def test_request_evented_list_modification(minimal_request):
    """Test that modifying an EventedList emits a 'changed' signal."""
    mock_callback = Mock()
    minimal_request.changed.connect(mock_callback)

    minimal_request.messages.append(Message(role="assistant", content="Hi!"))
    assert len(minimal_request.messages) == 2
    mock_callback.assert_called()


def test_request_evented_dict_modification(minimal_request):
    """Test that modifying an EventedDict emits a 'changed' signal."""
    mock_callback = Mock()
    minimal_request.changed.connect(mock_callback)

    minimal_request.logit_bias = EventedDict({"123": -1.0})
    assert minimal_request.logit_bias["123"] == -1.0
    mock_callback.assert_called_once()
    mock_callback.reset_mock()

    minimal_request.logit_bias["456"] = 1.0
    assert minimal_request.logit_bias["456"] == 1.0
    mock_callback.assert_called()


def test_deprecated_fields():
    """Test the deprecated fields for completeness."""
    # This test primarily serves to ensure these fields still exist and can be used,
    # even if deprecated.
    instance = OpenAIChatCompletionsRequest(
        model="gpt-4",
        messages=EventedList([]),
        function_call="auto",
        functions=EventedList([FunctionDefinition(name="test", description="test", parameters=EventedDict({}))]),
        max_tokens=100,
    )
    assert instance.function_call == "auto"
    assert instance.functions is not None
    assert len(instance.functions) == 1
    assert instance.max_tokens == 100

    instance.function_call = RequestFunctionCall(name="my_func")
    assert isinstance(instance.function_call, RequestFunctionCall)
    assert instance.function_call.name == "my_func"
