import uuid

import httpx
from luthien_control.core.transaction_context import TransactionContext


def test_transaction_context_instantiation_defaults():
    """Verify TransactionContext instantiation with default values."""
    context = TransactionContext()

    assert isinstance(context.transaction_id, uuid.UUID)
    assert context.request is None
    assert context.response is None
    assert context.data == {}


def test_transaction_context_with_values():
    """Verify TransactionContext instantiation and field assignment."""
    # Create dummy request/response objects for testing
    # In a real scenario, these would come from httpx
    dummy_request = httpx.Request("GET", "http://example.com")
    dummy_response = httpx.Response(200, request=dummy_request, content=b"OK")
    test_data = {"key1": "value1", "key2": 123}
    test_id = uuid.uuid4()

    context = TransactionContext(
        transaction_id=test_id,
        request=dummy_request,
        response=dummy_response,
        data=test_data.copy(),  # Pass a copy to ensure it's not the same object
    )

    assert context.transaction_id == test_id
    assert context.request == dummy_request
    assert context.response == dummy_response
    assert context.data == test_data


def test_transaction_context_data_modification():
    """Verify the data dictionary can be modified after instantiation."""
    context = TransactionContext()
    assert context.data == {}

    context.data["new_key"] = "new_value"
    context.data["another_key"] = 456

    assert context.data == {"new_key": "new_value", "another_key": 456}
