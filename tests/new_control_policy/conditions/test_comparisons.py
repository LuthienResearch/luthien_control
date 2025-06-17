from typing import Any

import pytest
from luthien_control.api.openai_chat_completions.datatypes import (
    Choice,
    FunctionDefinition,
    Message,
    ToolDefinition,
    Usage,
)
from luthien_control.api.openai_chat_completions.request import OpenAIChatCompletionsRequest
from luthien_control.api.openai_chat_completions.response import OpenAIChatCompletionsResponse
from luthien_control.core.request import Request
from luthien_control.core.response import Response
from luthien_control.core.transaction import Transaction
from luthien_control.new_control_policy.conditions.comparators import (
    COMPARATOR_TO_NAME,
)
from luthien_control.new_control_policy.conditions.comparisons import (
    ContainsCondition,
    EqualsCondition,
    GreaterThanCondition,
    GreaterThanOrEqualCondition,
    LessThanCondition,
    LessThanOrEqualCondition,
    NotEqualsCondition,
    RegexMatchCondition,
)
from psygnal.containers import EventedDict, EventedList


@pytest.fixture
def sample_transaction() -> Transaction:
    """Provides a Transaction populated with sample request, response, and data."""

    # Create request with OpenAI chat completions data
    request = Request(
        payload=OpenAIChatCompletionsRequest(
            model="gpt-4o",
            messages=EventedList([Message(role="user", content="Hello")]),
            tools=EventedList(
                [
                    ToolDefinition(function=FunctionDefinition(name="tool_a")),
                    ToolDefinition(function=FunctionDefinition(name="tool_b")),
                ]
            ),
        ),
        api_endpoint="https://api.openai.com/v1/chat/completions",
        api_key="Bearer testkey",
    )

    # Create response with OpenAI chat completions data
    response = Response(
        payload=OpenAIChatCompletionsResponse(
            id="chatcmpl-xxxxxxxx",
            object="chat.completion",
            created=1678886400,
            model="gpt-4o",
            choices=EventedList(
                [
                    Choice(
                        index=0,
                        message=Message(role="assistant", content="World"),
                        finish_reason="stop",
                    )
                ]
            ),
            usage=Usage(prompt_tokens=10, completion_tokens=50, total_tokens=60),
        )
    )

    # Create transaction with test data
    transaction_data = EventedDict(
        {
            "arbitrarykey": "arbitraryvalue",
            "count": 10,
            "user_permissions": ["read", "write"],
        }
    )

    transaction = Transaction(
        request=request,
        response=response,
        data=transaction_data,
    )

    return transaction


@pytest.mark.parametrize(
    "condition_class, key, value, expected_result",
    [
        # EqualsCondition
        (EqualsCondition, "request.payload.model", "gpt-4o", True),
        (EqualsCondition, "request.payload.model", "gpt-3.5-turbo", False),
        (EqualsCondition, "data.count", 10, True),
        (EqualsCondition, "data.count", 11, False),
        # NotEqualsCondition
        (NotEqualsCondition, "request.payload.model", "gpt-3.5-turbo", True),
        (NotEqualsCondition, "request.payload.model", "gpt-4o", False),
        # ContainsCondition - testing on lists
        (ContainsCondition, "data.user_permissions", "read", True),
        (ContainsCondition, "data.user_permissions", "admin", False),
        (ContainsCondition, "data.arbitrarykey", "value", True),
        # LessThanCondition
        (LessThanCondition, "response.payload.created", 1678886401, True),
        (LessThanCondition, "response.payload.usage.completion_tokens", 50, False),
        # LessThanOrEqualCondition
        (LessThanOrEqualCondition, "response.payload.created", 1678886400, True),
        (LessThanOrEqualCondition, "response.payload.usage.completion_tokens", 49, False),
        # GreaterThanCondition
        (GreaterThanCondition, "response.payload.created", 1678886399, True),
        (GreaterThanCondition, "response.payload.usage.completion_tokens", 50, False),
        # GreaterThanOrEqualCondition
        (GreaterThanOrEqualCondition, "response.payload.created", 1678886400, True),
        (GreaterThanOrEqualCondition, "response.payload.usage.completion_tokens", 51, False),
        # RegexMatchCondition
        (RegexMatchCondition, "request.payload.model", "^gpt-4o$", True),
        (RegexMatchCondition, "request.payload.model", "^gpt-3.*", False),
        (RegexMatchCondition, "data.arbitrarykey", ".*value$", True),
    ],
)
def test_condition_evaluation(
    condition_class, key: str, value: Any, expected_result: bool, sample_transaction: Transaction
) -> None:
    """Tests the evaluation logic for various comparison conditions."""
    condition = condition_class(key=key, value=value)
    assert condition.evaluate(sample_transaction) is expected_result


@pytest.mark.parametrize(
    "condition_class, key, value",
    [
        (EqualsCondition, "request.payload.model", "gpt-4o"),
        (NotEqualsCondition, "data.count", 10),
        (ContainsCondition, "data.user_permissions", "read"),
        (LessThanCondition, "response.payload.created", 1678886401),
        (LessThanOrEqualCondition, "response.payload.usage.completion_tokens", 50),
        (GreaterThanCondition, "data.arbitrarykey", "some_value"),
        (GreaterThanOrEqualCondition, "response.payload.created", 1678886400),
        (RegexMatchCondition, "request.payload.model", "^gpt-4.*$"),
    ],
)
def test_condition_serialization_deserialization(
    condition_class,
    key: str,
    value: Any,
) -> None:
    """Tests serialization and deserialization round-trip for comparison conditions."""
    original_condition = condition_class(key=key, value=value)

    # Test serialization
    serialized_data = original_condition.serialize()

    expected_serialization = {
        "type": original_condition.type,
        "key": key,
        "comparator": COMPARATOR_TO_NAME[original_condition.comparator],
        "value": value,
    }
    assert serialized_data == expected_serialization

    # Test deserialization
    from_serializedd_condition = condition_class.from_serialized(serialized_data)

    # Ensure the from_serializedd object is equivalent to the original for core attributes
    assert isinstance(from_serializedd_condition, condition_class)
    assert from_serializedd_condition.type == original_condition.type
    assert from_serializedd_condition.key == original_condition.key
    assert from_serializedd_condition.value == original_condition.value
    assert from_serializedd_condition.comparator == original_condition.comparator
    assert type(from_serializedd_condition) is type(original_condition)  # Check same class type


def test_condition_from_serialized_nonstring_key():
    """Test that deserialization fails with invalid type."""
    with pytest.raises(TypeError):
        EqualsCondition.from_serialized({"type": "equals", "key": 123, "value": "value"})
