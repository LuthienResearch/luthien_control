from typing import cast
from unittest.mock import Mock

import pytest
from luthien_control.api.openai_chat_completions.datatypes import Choice, Message, Usage
from luthien_control.api.openai_chat_completions.request import OpenAIChatCompletionsRequest
from luthien_control.api.openai_chat_completions.response import OpenAIChatCompletionsResponse
from luthien_control.core.request import Request
from luthien_control.core.response import Response
from luthien_control.core.transaction import Transaction
from psygnal.containers import EventedDict, EventedList


@pytest.fixture
def sample_request():
    """Returns a sample Request object for testing."""
    return Request(
        payload=OpenAIChatCompletionsRequest(
            model="gpt-4",
            messages=EventedList([Message(role="user", content="Hello")]),
        ),
        api_endpoint="https://api.openai.com/v1/chat/completions",
        api_key="test_key",
    )


@pytest.fixture
def sample_response():
    """Returns a sample Response object for testing."""
    return Response(
        payload=OpenAIChatCompletionsResponse(
            id="chatcmpl-123",
            object="chat.completion",
            created=1677652288,
            model="gpt-4",
            choices=EventedList(
                [
                    Choice(
                        index=0,
                        message=Message(role="assistant", content="Hi there!"),
                        finish_reason="stop",
                    )
                ]
            ),
            usage=Usage(prompt_tokens=1, completion_tokens=2, total_tokens=3),
        )
    )


def test_transaction_instantiation(sample_request, sample_response):
    """Test that a Transaction can be instantiated correctly."""
    transaction = Transaction(openai_request=sample_request, openai_response=sample_response)
    assert isinstance(transaction, Transaction)
    assert transaction.openai_request == sample_request
    assert transaction.openai_response == sample_response
    assert isinstance(transaction.data, EventedDict)
    assert len(transaction.data) == 0


def test_transaction_event_emission_on_attribute_change(sample_request, sample_response):
    """Test that the 'changed' signal is emitted on direct attribute changes."""
    transaction = Transaction(openai_request=sample_request, openai_response=sample_response)
    mock_callback = Mock()
    transaction.changed.connect(mock_callback)

    # Change a direct attribute
    new_response = Response(
        payload=OpenAIChatCompletionsResponse(id="new", created=1, model="gpt-4", object="chat.completion")
    )
    transaction.openai_response = new_response

    mock_callback.assert_called_once()
    assert transaction.openai_response == new_response


def test_transaction_event_emission_on_nested_attribute_change(sample_request, sample_response):
    """Test that the 'changed' signal is emitted on nested attribute changes."""
    transaction = Transaction(openai_request=sample_request, openai_response=sample_response)
    mock_callback = Mock()
    transaction.changed.connect(mock_callback)

    # Change a nested attribute
    assert transaction.openai_request is not None
    transaction.openai_request.payload.model = "gpt-4-turbo"

    mock_callback.assert_called_once()
    assert transaction.openai_request.payload.model == "gpt-4-turbo"

    mock_callback.reset_mock()

    # Change an item in a nested list
    assert transaction.openai_request is not None
    transaction.openai_request.payload.messages.append(Message(role="assistant", content="How can I help?"))
    mock_callback.assert_called()
    assert len(transaction.openai_request.payload.messages) == 2

    mock_callback.reset_mock()
    assert transaction.openai_response is not None
    cast(OpenAIChatCompletionsResponse, transaction.openai_response.payload).choices[0].message.content = "New content"
    mock_callback.assert_called_once()
    assert transaction.openai_response.payload is not None
    assert transaction.openai_response.payload.choices[0].message.content == "New content"
