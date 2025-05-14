import uuid
from dataclasses import dataclass  # Added field for default_factory
from typing import Any, Dict, Optional

import httpx
import pytest
from luthien_control.core.transaction_context import TransactionContext, get_tx_value


# Mock httpx.Request and httpx.Response for testing
@dataclass
class MockRequest:
    method: str
    url: httpx.URL
    headers: Dict[str, str]
    content: Optional[bytes] = None


@dataclass
class MockResponse:
    status_code: int
    headers: Dict[str, str]
    content: Optional[bytes] = None


def test_get_tx_value_simple_attribute():
    """Test getting a simple top-level attribute raises ValueError."""
    tx_id = uuid.uuid4()
    context = TransactionContext(transaction_id=tx_id)
    with pytest.raises(ValueError):
        get_tx_value(context, "transaction_id")


def test_get_tx_value_nested_request_attribute():
    """Test getting a nested attribute from the request object."""
    request = MockRequest(method="GET", url="http://example.com", headers={"user-agent": "test-agent"})
    context = TransactionContext(request=request)
    assert get_tx_value(context, "request.headers.user-agent") == "test-agent"
    assert get_tx_value(context, "request.method") == "GET"


def test_get_tx_value_data_dictionary():
    """Test getting a value from the data dictionary."""
    context = TransactionContext(data={"user_id": 123, "session_id": "abc"})
    assert get_tx_value(context, "data.user_id") == 123
    assert get_tx_value(context, "data.session_id") == "abc"


def test_get_tx_value_response_attribute():
    """Test getting an attribute from the response object."""
    response = MockResponse(status_code=200, headers={"content-type": "application/json"})
    context = TransactionContext(response=response)
    assert get_tx_value(context, "response.status_code") == 200


def test_get_tx_value_response_json_content():
    """Test getting JSON content from the response."""
    response_content = b'{"key": "value"}'
    response = MockResponse(status_code=200, headers={"content-type": "application/json"}, content=response_content)
    context = TransactionContext(response=response)
    assert get_tx_value(context, "response.content.key") == "value"


def test_get_tx_value_request_json_content():
    """Test getting JSON content from the request."""
    request_content = b'{"key_req": "value_req"}'
    request = MockRequest(method="POST", url="http://example.com", headers={}, content=request_content)
    context = TransactionContext(request=request)
    assert get_tx_value(context, "request.content.key_req") == "value_req"


def test_get_tx_value_invalid_path_too_short():
    """Test ValueError for a path with less than two components."""
    context = TransactionContext()
    with pytest.raises(ValueError, match="Path must contain at least two components"):
        get_tx_value(context, "request")  # Path with only one component
    with pytest.raises(ValueError, match="Path must contain at least two components"):
        get_tx_value(context, "data")  # Path with only one component


def test_get_tx_value_attribute_error_on_object():
    """Test AttributeError for a non-existent attribute on an object (not dict)."""
    request = MockRequest(method="GET", url="http://example.com", headers={})
    context = TransactionContext(request=request)
    with pytest.raises(AttributeError):
        get_tx_value(context, "request.non_existent_attr")
    # Also test on TransactionContext itself for a non-request/response/data field
    with pytest.raises(AttributeError):  # e.g. context.non_existent_top_level.some_value
        get_tx_value(context, "non_existent_top_level.some_value")


def test_get_tx_value_key_error_on_data_dict():
    """Test KeyError for a non-existent key in the data dictionary."""
    context = TransactionContext(data={"existing_key": "value"})
    with pytest.raises(KeyError):
        get_tx_value(context, "data.non_existent_key")


def test_get_tx_value_key_error_on_json_content():
    """Test KeyError for a non-existent key in JSON content."""
    response_content = b'{"key": "value"}'
    response = MockResponse(status_code=200, headers={"content-type": "application/json"}, content=response_content)
    context = TransactionContext(response=response)
    with pytest.raises(KeyError):
        get_tx_value(context, "response.content.non_existent_key")


def test_get_tx_value_key_error_on_headers_dict():
    """Test KeyError for a non-existent key in headers dictionary."""
    response = MockResponse(status_code=200, headers={"content-type": "application/json"})
    context = TransactionContext(response=response)
    assert get_tx_value(context, "response.headers.content-type") == "application/json"
    with pytest.raises(KeyError):
        get_tx_value(context, "response.headers.non_existent_header")


def test_get_tx_value_path_traverses_object_then_dict():
    """Test a path that first accesses an object attribute, then a dict key."""

    @dataclass
    class NestedObject:
        details: Dict[str, Any]

    nested_obj = NestedObject(details={"item_id": 789, "status": "active"})
    context = TransactionContext(data={"complex_obj": nested_obj})

    assert get_tx_value(context, "data.complex_obj.details.item_id") == 789
    assert get_tx_value(context, "data.complex_obj.details.status") == "active"

    with pytest.raises(AttributeError):  # complex_obj.non_existent_attr
        get_tx_value(context, "data.complex_obj.non_existent_attr.item_id")

    with pytest.raises(KeyError):  # complex_obj.details['wrong_key']
        get_tx_value(context, "data.complex_obj.details.wrong_key")


def test_get_tx_value_empty_context_access_fails_gracefully():
    """Test accessing attributes on a completely empty TransactionContext."""
    context = TransactionContext(request=None, response=None)
    with pytest.raises(AttributeError):  # request is None
        get_tx_value(context, "request.method")
    with pytest.raises(AttributeError):  # response is None
        get_tx_value(context, "response.status_code")
    with pytest.raises(KeyError):  # data is empty dict
        get_tx_value(context, "data.some_key")


def test_get_tx_value_non_byte_content():
    """Test that content that is not bytes and not dict is handled by getattr."""

    @dataclass
    class CustomContent:
        payload: str

    request = MockRequest(method="GET", url="/", headers={}, content=CustomContent(payload="test"))
    context = TransactionContext(request=request)
    # Path tries to access request.content.payload
    # request.content is CustomContent, not bytes, so json.loads is skipped.
    # Then it tries getattr(CustomContent, "payload")
    assert get_tx_value(context, "request.content.payload") == "test"

    with pytest.raises(AttributeError):
        get_tx_value(context, "request.content.non_existent")
