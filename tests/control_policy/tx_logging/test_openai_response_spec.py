import datetime
import json
import logging

import httpx
import pytest
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.control_policy.tx_logging.logging_utils import REDACTED_PLACEHOLDER
from luthien_control.control_policy.tx_logging.openai_response_spec import (
    OPENAI_CHAT_RESPONSE_FIELDS,
    OpenAIResponseSpec,
    serialize_openai_chat_response,
)
from luthien_control.control_policy.tx_logging.tx_logging_spec import LuthienLogData
from luthien_control.core.transaction_context import TransactionContext

# --- Tests for serialize_openai_chat_response --- #


@pytest.mark.parametrize(
    "body_dict, expected_content_keys",
    [
        (
            {
                "id": "chatcmpl-xxxx",
                "object": "chat.completion",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "Hi!"}}],
            },
            ["id", "object", "choices"],
        ),
        (
            {"id": "chatcmpl-yyyy", "model": "gpt-4", "usage": {"prompt_tokens": 10, "completion_tokens": 20}},
            ["id", "model", "usage"],
        ),
        ({}, []),  # Empty body
    ],
)
def test_serialize_openai_chat_response_valid_body(body_dict, expected_content_keys):
    """Test with valid JSON body containing OpenAI response fields."""
    content_bytes = json.dumps(body_dict).encode("utf-8")
    headers = {"X-Request-ID": "test-id", "Set-Cookie": "secret=cookie"}

    # Create request (required for httpx.Response)
    request = httpx.Request("GET", "http://example.com")
    response = httpx.Response(
        status_code=200,
        headers=headers,
        content=content_bytes,
        request=request,
        extensions={
            "reason_phrase": b"OK",
            "http_version": b"HTTP/1.1",
        },
    )
    response.elapsed = datetime.timedelta(milliseconds=123)

    serialized = serialize_openai_chat_response(response)

    assert serialized["status_code"] == 200
    assert serialized["headers"]["X-Request-ID"] == "test-id"
    assert serialized["headers"]["Set-Cookie"] == REDACTED_PLACEHOLDER
    assert serialized["reason_phrase"] == "OK"
    assert serialized["http_version"] == "HTTP/1.1"
    assert serialized["elapsed_ms"] == 123.0

    assert isinstance(serialized["content"], dict)
    for key in expected_content_keys:
        assert key in serialized["content"]
        assert serialized["content"][key] == body_dict[key]

    for key in serialized["content"]:
        assert key in OPENAI_CHAT_RESPONSE_FIELDS or key == "error"


def test_serialize_openai_chat_response_malformed_json(caplog):
    """Test with malformed JSON content."""
    content_bytes = b"{ 'id': '123' "

    request = httpx.Request("GET", "http://example.com")
    response = httpx.Response(
        status_code=200,
        content=content_bytes,
        request=request,
        extensions={
            "reason_phrase": b"OK",
            "http_version": b"HTTP/1.1",
        },
    )
    response.elapsed = datetime.timedelta(milliseconds=123)

    with caplog.at_level(logging.ERROR):
        serialized = serialize_openai_chat_response(response)

    assert "Error parsing OpenAI response" in caplog.text
    assert "content" in serialized
    assert "error" in serialized["content"]
    assert "JSONDecodeError" in serialized["content"]["error"]


def test_serialize_openai_chat_response_empty_content(caplog):
    """Test with empty content which is also invalid JSON."""
    request = httpx.Request("GET", "http://example.com")
    response = httpx.Response(
        status_code=204,
        content=b"",
        request=request,
        extensions={
            "reason_phrase": b"No Content",
            "http_version": b"HTTP/1.1",
        },
    )
    response.elapsed = datetime.timedelta(milliseconds=123)

    with caplog.at_level(logging.ERROR):
        serialized = serialize_openai_chat_response(response)

    assert "Error parsing OpenAI response" in caplog.text
    assert "content" in serialized
    assert "error" in serialized["content"]
    assert "JSONDecodeError" in serialized["content"]["error"]  # json.loads('') raises JSONDecodeError


# --- Tests for OpenAIResponseSpec --- #


def test_openai_response_spec_generate_log_data_with_response():
    """Test generate_log_data with a valid response."""
    body = {"id": "res-123", "choices": [{"message": {"content": "Hello there"}}]}

    request = httpx.Request("GET", "http://example.com")
    response = httpx.Response(
        status_code=200,
        headers={"X-My-Header": "res-val"},
        content=json.dumps(body).encode("utf-8"),
        request=request,
        extensions={
            "reason_phrase": b"OK",
            "http_version": b"HTTP/1.1",
        },
    )
    response.elapsed = datetime.timedelta(milliseconds=123)

    context = TransactionContext(response=response)
    spec = OpenAIResponseSpec()
    notes_dict: SerializableDict = {"res_note": "res_val"}

    log_data_obj = spec.generate_log_data(context, notes=notes_dict)

    assert isinstance(log_data_obj, LuthienLogData)
    assert log_data_obj.datatype == "openai_chat_response"
    assert log_data_obj.notes == notes_dict
    assert log_data_obj.data is not None
    assert isinstance(log_data_obj.data, dict)
    assert log_data_obj.data["status_code"] == 200
    assert isinstance(log_data_obj.data["headers"], dict)
    assert log_data_obj.data["headers"]["X-My-Header"] == "res-val"
    assert isinstance(log_data_obj.data["content"], dict)
    assert log_data_obj.data["content"]["id"] == "res-123"


def test_openai_response_spec_generate_log_data_no_response():
    """Test generate_log_data when no response is in the context."""
    context = TransactionContext()
    spec = OpenAIResponseSpec()

    log_data_obj = spec.generate_log_data(context)
    assert log_data_obj is not None
    assert log_data_obj.datatype == "openai_chat_response"
    assert log_data_obj.data is None
    assert log_data_obj.notes is None


def test_openai_response_spec_generate_log_data_serialization_error(caplog):
    """Test generate_log_data when serialize_openai_chat_response has an unhandled error."""

    # Create a response with content that will cause JSON parsing errors
    content_bytes = b"\xff\xfe"  # Invalid UTF-8 content that will cause UnicodeDecodeError
    request = httpx.Request("GET", "http://example.com")
    response = httpx.Response(
        status_code=200,
        content=content_bytes,
        request=request,
        extensions={
            "reason_phrase": b"OK",
            "http_version": b"HTTP/1.1",
        },
    )
    response.elapsed = datetime.timedelta(milliseconds=123)

    context = TransactionContext(response=response)
    spec = OpenAIResponseSpec()

    with caplog.at_level(logging.ERROR):
        log_data_obj = spec.generate_log_data(context)

    assert log_data_obj is not None
    assert log_data_obj.datatype == "openai_chat_response"
    assert log_data_obj.data is not None
    assert isinstance(log_data_obj.data, dict)
    assert "content" in log_data_obj.data
    content = log_data_obj.data["content"]
    assert isinstance(content, dict)
    assert "error" in content
    assert "JSONDecodeError" in content["error"]

    # Check that error was logged
    assert "Error parsing OpenAI response" in caplog.text


def test_openai_response_spec_serialize():
    """Test the serialization of OpenAIResponseSpec."""
    spec = OpenAIResponseSpec()
    serialized_data = spec.serialize()
    expected_data: SerializableDict = {"type": "OpenAIResponseSpec"}
    assert serialized_data == expected_data


def test_openai_response_spec_from_serialized_impl():
    """Test the deserialization of OpenAIResponseSpec."""
    config: SerializableDict = {"type": "OpenAIResponseSpec"}
    spec = OpenAIResponseSpec._from_serialized_impl(config)
    assert isinstance(spec, OpenAIResponseSpec)

    config_extra: SerializableDict = {"type": "OpenAIResponseSpec", "other_field": "value"}
    spec_extra = OpenAIResponseSpec._from_serialized_impl(config_extra)
    assert isinstance(spec_extra, OpenAIResponseSpec)
