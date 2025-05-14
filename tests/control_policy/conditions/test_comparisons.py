from typing import Any

import httpx
import pytest
from luthien_control.control_policy.conditions.comparators import (
    COMPARATOR_TO_NAME,
)
from luthien_control.control_policy.conditions.comparisons import (
    ContainsCondition,
    EqualsCondition,
    GreaterThanCondition,
    GreaterThanOrEqualCondition,
    LessThanCondition,
    LessThanOrEqualCondition,
    NotEqualsCondition,
    RegexMatchCondition,
)
from luthien_control.core.transaction_context import TransactionContext


@pytest.fixture
def sample_request() -> httpx.Request:
    """Provides a sample httpx.Request object."""
    return httpx.Request(
        method="POST",
        url="http://example.com/api/v1/chat/completions",
        headers={"Authorization": "Bearer testkey", "Content-Type": "application/json"},
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Hello"}], "tools": ["tool_a", "tool_b"]},
    )


@pytest.fixture
def sample_response() -> httpx.Response:
    """Provides a sample httpx.Response object."""
    return httpx.Response(
        status_code=200,
        headers={"Content-Type": "application/json"},
        json={
            "id": "chatcmpl-xxxxxxxx",
            "object": "chat.completion",
            "created": 1678886400,
            "model": "gpt-4o",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "World"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 50, "total_tokens": 60},
        },
    )


@pytest.fixture
def transaction_context(sample_request: httpx.Request, sample_response: httpx.Response) -> TransactionContext:
    """Provides a TransactionContext populated with sample request, response, and data."""
    return TransactionContext(
        request=sample_request,
        response=sample_response,
        data={"arbitrarykey": "arbitraryvalue", "count": 10, "user_permissions": ["read", "write"]},
    )


@pytest.mark.parametrize(
    "condition_class, key, value, expected_result",
    [
        # EqualsCondition
        (EqualsCondition, "request.content.model", "gpt-4o", True),
        (EqualsCondition, "request.content.model", "gpt-3.5-turbo", False),
        (EqualsCondition, "data.count", 10, True),
        (EqualsCondition, "data.count", 11, False),
        # NotEqualsCondition
        (NotEqualsCondition, "request.content.model", "gpt-3.5-turbo", True),
        (NotEqualsCondition, "request.content.model", "gpt-4o", False),
        # ContainsCondition
        (ContainsCondition, "request.content.tools", "tool_a", True),
        (ContainsCondition, "request.content.tools", "tool_c", False),
        (ContainsCondition, "data.arbitrarykey", "value", True),
        # LessThanCondition
        (LessThanCondition, "response.content.created", 1678886401, True),
        (LessThanCondition, "response.content.usage.completion_tokens", 50, False),
        # LessThanOrEqualCondition
        (LessThanOrEqualCondition, "response.content.created", 1678886400, True),
        (LessThanOrEqualCondition, "response.content.usage.completion_tokens", 49, False),
        # GreaterThanCondition
        (GreaterThanCondition, "response.content.created", 1678886399, True),
        (GreaterThanCondition, "response.content.usage.completion_tokens", 50, False),
        # GreaterThanOrEqualCondition
        (GreaterThanOrEqualCondition, "response.content.created", 1678886400, True),
        (GreaterThanOrEqualCondition, "response.content.usage.completion_tokens", 51, False),
        # RegexMatchCondition
        (RegexMatchCondition, "request.content.model", "^gpt-4o$", True),
        (RegexMatchCondition, "request.content.model", "^gpt-3.*", False),
        (RegexMatchCondition, "data.arbitrarykey", ".*value$", True),
    ],
)
def test_condition_evaluation(
    condition_class, key: str, value: Any, expected_result: bool, transaction_context: TransactionContext
) -> None:
    """Tests the evaluation logic for various comparison conditions."""
    condition = condition_class(key=key, value=value)
    assert condition.evaluate(transaction_context) is expected_result


@pytest.mark.parametrize(
    "condition_class, key, value",
    [
        (EqualsCondition, "request.content.model", "gpt-4o"),
        (NotEqualsCondition, "data.count", 10),
        (ContainsCondition, "request.content.tools", "tool_a"),
        (LessThanCondition, "response.content.created", 1678886401),
        (LessThanOrEqualCondition, "response.content.usage.completion_tokens", 50),
        (GreaterThanCondition, "data.arbitrarykey", "some_value"),
        (GreaterThanOrEqualCondition, "response.content.created", 1678886400),
        (RegexMatchCondition, "request.content.model", "^gpt-4.*$"),
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
    deserialized_condition = condition_class.deserialize(serialized_data)

    # Ensure the deserialized object is equivalent to the original for core attributes
    assert isinstance(deserialized_condition, condition_class)
    assert deserialized_condition.type == original_condition.type
    assert deserialized_condition.key == original_condition.key
    assert deserialized_condition.value == original_condition.value
    assert deserialized_condition.comparator == original_condition.comparator
    assert type(deserialized_condition) is type(original_condition)  # Check same class type
