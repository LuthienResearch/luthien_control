from typing import Any, Dict, cast

import httpx
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.control_policy.tx_logging.logging_utils import (
    REDACTED_PLACEHOLDER,
)
from luthien_control.control_policy.tx_logging.response_headers_spec import ResponseHeadersSpec
from luthien_control.core.tracked_context import TrackedContext


def test_generate_log_data_with_response():
    """Test generating log data when a response is present."""
    headers = {"X-Server-Header": "ServerValue", "Content-Type": "application/json"}

    request = httpx.Request("GET", "http://example.com")
    response = httpx.Response(
        status_code=200,
        headers=headers,
        request=request,
        extensions={
            "reason_phrase": b"OK",
            "http_version": b"HTTP/1.1",
        },
    )

    context = TrackedContext()
    context.update_response(status_code=response.status_code, headers=headers, content=response.content)
    spec = ResponseHeadersSpec()

    log_data_obj = spec.generate_log_data(context)

    assert log_data_obj is not None
    assert log_data_obj.datatype == "response_headers"
    assert log_data_obj.data is not None
    assert isinstance(log_data_obj.data, dict)
    data = cast(Dict[str, Any], log_data_obj.data)
    assert data["status_code"] == 200
    headers = cast(Dict[str, Any], data["headers"])
    assert headers["X-Server-Header"] == "ServerValue"
    assert headers["Content-Type"] == "application/json"
    assert log_data_obj.notes is None


def test_generate_log_data_with_notes():
    """Test generating log data with additional notes."""
    headers = {}
    request = httpx.Request("GET", "http://example.com")
    response = httpx.Response(
        status_code=201,
        headers=headers,
        request=request,
        extensions={
            "reason_phrase": b"Created",
            "http_version": b"HTTP/1.1",
        },
    )

    context = TrackedContext()
    context.update_response(status_code=response.status_code, headers=headers, content=response.content)
    spec = ResponseHeadersSpec()
    notes_dict: SerializableDict = {"custom_note": "resource created"}

    log_data_obj = spec.generate_log_data(context, notes=notes_dict)

    assert log_data_obj is not None
    assert log_data_obj.data is not None
    assert isinstance(log_data_obj.data, dict)
    assert log_data_obj.notes == notes_dict


def test_generate_log_data_no_response():
    """Test generating log data when no response is present in the context."""
    context = TrackedContext()  # No response
    spec = ResponseHeadersSpec()

    log_data_obj = spec.generate_log_data(context)
    assert log_data_obj is not None
    assert log_data_obj.datatype == "response_headers"
    assert log_data_obj.data is None
    assert log_data_obj.notes is None


def test_generate_log_data_header_sanitization():
    """Test that sensitive headers are sanitized."""
    headers = {
        "Set-Cookie": "sessionid=verysecret; HttpOnly",
        "Authorization": "Bearer secret",  # Use a known sensitive header
        "X-Normal-Header": "normal_value",
    }

    request = httpx.Request("GET", "http://example.com")
    response = httpx.Response(
        status_code=403,
        headers=headers,
        request=request,
        extensions={
            "reason_phrase": b"Forbidden",
            "http_version": b"HTTP/1.1",
        },
    )

    context = TrackedContext()
    context.update_response(status_code=response.status_code, headers=headers, content=response.content)
    spec = ResponseHeadersSpec()

    log_data_obj = spec.generate_log_data(context)

    assert log_data_obj is not None
    assert log_data_obj.data is not None
    assert isinstance(log_data_obj.data, dict)
    logged_headers = cast(Dict[str, Any], log_data_obj.data["headers"])

    # Check that sensitive headers are redacted
    assert logged_headers["Set-Cookie"] == REDACTED_PLACEHOLDER
    assert logged_headers["Authorization"] == REDACTED_PLACEHOLDER
    assert logged_headers["X-Normal-Header"] == "normal_value"


def test_generate_log_data_empty_headers():
    """Test generating log data with an empty headers object."""
    headers = {}
    request = httpx.Request("GET", "http://example.com")
    response = httpx.Response(
        status_code=500,
        headers=headers,
        request=request,
        extensions={
            "reason_phrase": b"Server Error",
            "http_version": b"HTTP/1.1",
        },
    )

    context = TrackedContext()
    context.update_response(status_code=response.status_code, headers=headers, content=response.content)
    spec = ResponseHeadersSpec()
    log_data_obj = spec.generate_log_data(context)
    assert log_data_obj is not None
    assert log_data_obj.data is not None
    assert isinstance(log_data_obj.data, dict)
    data = cast(Dict[str, Any], log_data_obj.data)
    headers = cast(Dict[str, Any], data["headers"])
    assert headers == {}


def test_generate_log_data_exception_handling(capsys):
    """Test that exceptions during log data generation bubble up."""

    class FaultyResponse:
        @property
        def headers(self):
            raise ValueError("Failed to get headers")

        status_code = 503
        reason_phrase = "Service Unavailable"

    context = TrackedContext()
    # Can't use set_response with FaultyResponse, so directly set the response
    context._response = FaultyResponse()  # type: ignore
    spec = ResponseHeadersSpec()

    # Expect the exception to bubble up rather than being caught
    import pytest

    with pytest.raises(ValueError, match="Failed to get headers"):
        spec.generate_log_data(context)


def test_serialize():
    """Test the serialization of ResponseHeadersSpec."""
    spec = ResponseHeadersSpec()
    serialized_data = spec.serialize()
    expected_data: SerializableDict = {"type": "ResponseHeadersSpec"}
    assert serialized_data == expected_data


def test_from_serialized_impl():
    """Test the deserialization of ResponseHeadersSpec."""
    config: SerializableDict = {"type": "ResponseHeadersSpec"}
    spec = ResponseHeadersSpec._from_serialized_impl(config)
    assert isinstance(spec, ResponseHeadersSpec)

    config_extra: SerializableDict = {"type": "ResponseHeadersSpec", "other_field": "value"}
    spec_extra = ResponseHeadersSpec._from_serialized_impl(config_extra)
    assert isinstance(spec_extra, ResponseHeadersSpec)
