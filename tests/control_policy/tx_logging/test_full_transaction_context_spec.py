import datetime
import json
from typing import Any, Dict, cast

import httpx
import pytest
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.control_policy.tx_logging.full_transaction_context_spec import (
    FullTransactionContextSpec,
    _serialize_content_bytes,
    _serialize_httpx_request,
    _serialize_httpx_response,
)
from luthien_control.control_policy.tx_logging.logging_utils import REDACTED_PLACEHOLDER
from luthien_control.control_policy.tx_logging.tx_logging_spec import LuthienLogData
from luthien_control.core.transaction_context import TransactionContext


# --- Tests for _serialize_content_bytes --- #
@pytest.mark.parametrize(
    "content_bytes, content_type, expected_partial_output",
    [
        (
            b'{"key": "value", "secret": "shh"}',
            "application/json",
            {"content_type": "application/json", "content": {"key": "value", "secret": REDACTED_PLACEHOLDER}},
        ),
        (
            b"Hello World",
            "text/plain; charset=utf-8",
            {"content_type": "text/plain; charset=utf-8", "content": "Hello World"},
        ),
        (
            b"\xde\xad\xbe\xef",
            "application/octet-stream",
            {"content_type": "application/octet-stream", "content": "deadbeef"},
        ),
        (b"\xde\xad\xbe\xef", None, {"content_type": "", "content": "deadbeef"}),  # No content type
        (
            b'{"malformed" "json"}',
            "application/json",
            {
                "content_type": "application/json",
                "error": "json_error: JSONDecodeError - Expecting ':' delimiter: line 1 column 14 (char 13)",
            },
        ),
        (
            b"\xff\xfeinvalid unicode",
            "text/plain",
            {
                "content_type": "text/plain",
                "error": "text_decode_error: UnicodeDecodeError - 'utf-8' codec can't decode byte 0xff in position 0: "
                "invalid start byte",
            },
        ),
        (None, "application/json", {"content": None}),
        (b"", "text/plain", {"content": None}),
    ],
)
def test_serialize_content_bytes(content_bytes, content_type, expected_partial_output):
    serialized = _serialize_content_bytes(content_bytes, content_type)

    # Check content only if expected
    if "content" in expected_partial_output:
        assert serialized["content"] == expected_partial_output["content"]

    if "content_type" in expected_partial_output:
        assert serialized["content_type"] == expected_partial_output["content_type"]

    if (
        "error" in expected_partial_output and expected_partial_output["error"] is True
    ):  # check for generic error presence
        assert "error" in serialized
    elif "error" in expected_partial_output:  # check for specific error message
        assert "error" in serialized
        assert serialized["error"] == expected_partial_output["error"]
    else:
        assert "error" not in serialized  # Ensure no error if not expected


# --- Tests for _serialize_httpx_request --- #
def test_serialize_httpx_request():
    headers = {"Authorization": "token", "Content-Type": "application/json"}
    body = {"message": "hello", "password": "secret123"}
    content_bytes = json.dumps(body).encode("utf-8")
    request = httpx.Request("POST", "http://example.com/api", content=content_bytes, headers=headers)

    serialized = _serialize_httpx_request(request)

    assert serialized["method"] == "POST"
    assert serialized["url"] == "http://example.com/api"
    assert serialized["headers"]["authorization"] == REDACTED_PLACEHOLDER
    assert serialized["headers"]["content-type"] == "application/json"  # Preserves case from input for non-sensitive
    assert serialized["content_type"] == "application/json"
    assert serialized["content"] == {"message": "hello", "password": REDACTED_PLACEHOLDER}


# --- Tests for _serialize_httpx_response --- #
def test_serialize_httpx_response():
    # Create a request first (required for httpx.Response)
    request = httpx.Request("GET", "http://example.com")

    headers = {"Set-Cookie": "session=secret", "Content-Type": "application/json; charset=UTF-8"}
    body = {"data": "response data", "token": "resp_token"}
    content_bytes = json.dumps(body).encode("utf-8")

    # Create response with the required parameters
    response = httpx.Response(
        status_code=200,
        headers=headers,
        content=content_bytes,
        request=request,
        extensions={
            "reason_phrase": b"All Good",
            "http_version": b"HTTP/1.1",
        },
    )
    response.elapsed = datetime.timedelta(milliseconds=50)

    serialized = _serialize_httpx_response(response)
    assert serialized["status_code"] == 200
    assert serialized["headers"]["set-cookie"] == REDACTED_PLACEHOLDER
    assert serialized["headers"]["content-type"] == "application/json; charset=UTF-8"
    assert serialized["reason_phrase"] == "All Good"
    assert serialized["elapsed_ms"] == 50.0
    assert serialized["content_type"] == "application/json; charset=utf-8"  # Normalized by _serialize_httpx_response
    assert serialized["content"] == {"data": "response data", "token": REDACTED_PLACEHOLDER}


# --- Tests for FullTransactionContextSpec --- #
def test_full_transaction_context_spec_generate_log_data():
    # Create request
    req_body = {"req_key": "req_val"}
    req_content = json.dumps(req_body).encode("utf-8")
    request = httpx.Request(
        "PUT",
        "http://req.ex.com",
        content=req_content,
        headers={"X-Req": "ReqHeader", "Content-Type": "application/json"},
    )

    # Create response
    resp_body = {"resp_key": "resp_val"}
    resp_content = json.dumps(resp_body).encode("utf-8")
    response = httpx.Response(
        status_code=201,
        headers={"X-Resp": "RespHeader", "Content-Type": "application/json"},
        content=resp_content,
        request=request,
        extensions={
            "reason_phrase": b"Created",
            "http_version": b"HTTP/1.1",
        },
    )
    response.elapsed = datetime.timedelta(milliseconds=50)

    # Create transaction context
    context_data = {"custom_field": "custom_value", "sensitive_info": "super_secret"}
    context = TransactionContext(request=request, response=response, data=context_data)

    spec = FullTransactionContextSpec()
    notes: SerializableDict = {"operation": "full_log"}

    log_data_obj = spec.generate_log_data(context, notes=notes)

    assert isinstance(log_data_obj, LuthienLogData)
    assert log_data_obj.datatype == "full_transaction_context"
    assert log_data_obj.notes == notes

    data = log_data_obj.data
    assert data is not None
    assert isinstance(data, dict)  # Additional type assertion
    data = cast(Dict[str, Any], data)
    assert "request" in data
    request_data = cast(Dict[str, Any], data["request"])
    assert request_data["method"] == "PUT"
    assert request_data["url"] == "http://req.ex.com"
    headers_data = cast(Dict[str, Any], request_data["headers"])
    assert headers_data["x-req"] == "ReqHeader"
    content_data = cast(Dict[str, Any], request_data["content"])
    assert content_data == {"req_key": "req_val"}  # Sanitized by _sanitize_json_payload

    assert "response" in data
    response_data = cast(Dict[str, Any], data["response"])
    assert response_data["status_code"] == 201
    response_headers = cast(Dict[str, Any], response_data["headers"])
    assert response_headers["x-resp"] == "RespHeader"
    response_content = cast(Dict[str, Any], response_data["content"])
    assert response_content == {"resp_key": "resp_val"}  # Sanitized

    assert "context_data" in data
    # context.data is directly assigned
    assert data["context_data"] == context_data


def test_full_transaction_context_spec_generate_log_data_minimal():
    context = TransactionContext()  # No request, response, or data
    spec = FullTransactionContextSpec()

    log_data_obj = spec.generate_log_data(context)

    assert isinstance(log_data_obj, LuthienLogData)
    assert log_data_obj.datatype == "full_transaction_context"
    assert log_data_obj.notes is None
    data = log_data_obj.data
    assert data is not None
    assert isinstance(data, dict)  # Additional type assertion
    assert "request" not in data  # No request in context
    assert "response" not in data  # No response in context
    assert "context_data" not in data  # No data in context by default


def test_full_transaction_context_spec_context_data_serialization_error(caplog):
    """Tests behavior when context.data exists but might have serialization issues later in the pipeline."""
    # Note: The current implementation doesn't actually catch serialization errors
    # at this level - it just assigns context.data directly. This test verifies
    # that the data gets passed through as-is.

    class NonSerializable:
        def __str__(self) -> str:
            return "<NonSerializable object>"

    context_data = {"key": NonSerializable()}
    context = TransactionContext(data=context_data)
    spec = FullTransactionContextSpec()

    log_data_obj = spec.generate_log_data(context)

    assert isinstance(log_data_obj, LuthienLogData)
    assert log_data_obj.datatype == "full_transaction_context"
    data = log_data_obj.data
    assert data is not None
    assert isinstance(data, dict)  # Additional type assertion
    data = cast(Dict[str, Any], data)
    assert "context_data" in data
    # The data is assigned directly, so the NonSerializable object is preserved
    assert data["context_data"] == context_data
    context_data_dict = cast(Dict[str, Any], data["context_data"])
    assert isinstance(context_data_dict["key"], NonSerializable)


def test_full_transaction_context_spec_no_request_no_response():
    context = TransactionContext()
    spec = FullTransactionContextSpec()
    log_data_obj = spec.generate_log_data(context)
    assert isinstance(log_data_obj, LuthienLogData)
    assert log_data_obj.data is not None
    assert isinstance(log_data_obj.data, dict)  # Additional type assertion
    assert "request" not in log_data_obj.data  # Check for absence of key
    assert "response" not in log_data_obj.data  # Check for absence of key
    # When context.data is empty dict, context.data evaluates to False, so "context_data" key is not added
    assert "context_data" not in log_data_obj.data


def test_full_transaction_context_spec_serialize_from_serialized():
    spec = FullTransactionContextSpec()
    serialized = spec.serialize()
    assert serialized == {"type": "FullTransactionContextSpec"}
    deserialized_spec = FullTransactionContextSpec._from_serialized_impl(serialized)  # type: ignore
    assert isinstance(deserialized_spec, FullTransactionContextSpec)
