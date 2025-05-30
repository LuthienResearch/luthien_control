import httpx
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.control_policy.tx_logging.logging_utils import REDACTED_PLACEHOLDER
from luthien_control.control_policy.tx_logging.request_headers_spec import RequestHeadersSpec
from luthien_control.core.transaction_context import TransactionContext


def test_generate_log_data_with_request():
    """Test generating log data when a request is present."""
    headers = {"X-Test-Header": "TestValue", "Content-Type": "application/json"}
    request = httpx.Request(method="GET", url="http://example.com/test", headers=headers)
    context = TransactionContext(request=request)
    spec = RequestHeadersSpec()

    log_data_obj = spec.generate_log_data(context)

    assert log_data_obj is not None
    assert log_data_obj.datatype == "request_headers"
    assert log_data_obj.data is not None
    assert isinstance(log_data_obj.data, dict)
    assert log_data_obj.data["method"] == "GET"
    assert log_data_obj.data["url"] == "http://example.com/test"
    assert isinstance(log_data_obj.data["headers"], dict)
    assert log_data_obj.data["headers"]["X-Test-Header"] == "TestValue"
    assert log_data_obj.data["headers"]["Content-Type"] == "application/json"
    assert log_data_obj.notes is None


def test_generate_log_data_with_notes():
    """Test generating log data with additional notes."""
    request = httpx.Request(method="POST", url="http://example.com/submit")
    context = TransactionContext(request=request)
    spec = RequestHeadersSpec()
    notes_dict: SerializableDict = {"custom_note": "important info"}

    log_data_obj = spec.generate_log_data(context, notes=notes_dict)

    assert log_data_obj is not None
    assert log_data_obj.notes == notes_dict


def test_generate_log_data_no_request():
    """Test generating log data when no request is present in the context."""
    context = TransactionContext()  # No request
    spec = RequestHeadersSpec()

    log_data_obj = spec.generate_log_data(context)
    assert log_data_obj is not None
    assert log_data_obj.datatype == "request_headers"
    assert log_data_obj.data is None
    assert log_data_obj.notes is None


def test_generate_log_data_header_sanitization():
    """Test that sensitive headers are sanitized."""
    headers = {
        "Authorization": "Bearer secrettoken",
        "Cookie": "sessionid=verysecret;",
        "X-Api-Key": "anothersecretkey",
        "X-Normal-Header": "normal_value",
    }
    request = httpx.Request(method="GET", url="http://example.com/secure", headers=headers)
    context = TransactionContext(request=request)
    spec = RequestHeadersSpec()

    log_data_obj = spec.generate_log_data(context)

    assert log_data_obj is not None
    assert log_data_obj.data is not None
    assert isinstance(log_data_obj.data, dict)
    assert isinstance(log_data_obj.data["headers"], dict)
    logged_headers = log_data_obj.data["headers"]

    # Check that sensitive headers are redacted
    assert logged_headers["Authorization"] == REDACTED_PLACEHOLDER
    assert logged_headers["Cookie"] == REDACTED_PLACEHOLDER
    assert logged_headers["X-Api-Key"] == REDACTED_PLACEHOLDER
    assert logged_headers["X-Normal-Header"] == "normal_value"


def test_generate_log_data_empty_headers():
    """Test generating log data with an empty headers object."""
    request = httpx.Request(method="PUT", url="http://example.com/empty", headers={})
    context = TransactionContext(request=request)
    spec = RequestHeadersSpec()
    log_data_obj = spec.generate_log_data(context)
    assert log_data_obj is not None
    assert log_data_obj.data is not None
    assert isinstance(log_data_obj.data, dict)
    assert isinstance(log_data_obj.data["headers"], dict)
    assert "Host" in log_data_obj.data["headers"]
    assert "Content-Length" in log_data_obj.data["headers"]


def test_generate_log_data_exception_handling(capsys):
    """Test that exceptions during log data generation bubble up."""

    class FaultyRequest:  # Intentionally faulty request object
        @property
        def headers(self):
            raise ValueError("Failed to get headers")

        method = "GET"
        url = "http://faulty.com"

    context = TransactionContext(request=FaultyRequest())  # type: ignore
    spec = RequestHeadersSpec()

    # Expect the exception to bubble up rather than being caught
    import pytest

    with pytest.raises(ValueError, match="Failed to get headers"):
        spec.generate_log_data(context)


def test_serialize():
    """Test the serialization of RequestHeadersSpec."""
    spec = RequestHeadersSpec()
    serialized_data = spec.serialize()
    expected_data: SerializableDict = {"type": "RequestHeadersSpec"}
    assert serialized_data == expected_data


def test_from_serialized_impl():
    """Test the deserialization of RequestHeadersSpec."""
    config: SerializableDict = {"type": "RequestHeadersSpec"}  # config is not used by this spec's _from_serialized_impl
    spec = RequestHeadersSpec._from_serialized_impl(config)
    assert isinstance(spec, RequestHeadersSpec)

    # Test with extra fields in config, should still work
    config_extra: SerializableDict = {"type": "RequestHeadersSpec", "other_field": "value"}
    spec_extra = RequestHeadersSpec._from_serialized_impl(config_extra)
    assert isinstance(spec_extra, RequestHeadersSpec)
