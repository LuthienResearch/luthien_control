import json
import logging

import httpx
import pytest
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.control_policy.tx_logging.logging_utils import REDACTED_PLACEHOLDER
from luthien_control.control_policy.tx_logging.openai_request_spec import (
    OPENAI_CHAT_REQUEST_FIELDS,
    OpenAIRequestSpec,
    serialize_openai_chat_request,
)
from luthien_control.control_policy.tx_logging.tx_logging_spec import LuthienLogData
from luthien_control.core.transaction_context import TransactionContext

# --- Tests for serialize_openai_chat_request ---#


@pytest.mark.parametrize(
    "body_dict, expected_content_keys",
    [
        ({"model": "gpt-4", "messages": [{"role": "user", "content": "Hello"}]}, ["model", "messages"]),
        ({"model": "gpt-3.5-turbo", "temperature": 0.7, "extra_field": "ignore"}, ["model", "temperature"]),
        ({}, []),  # Empty body
    ],
)
def test_serialize_openai_chat_request_valid_body(body_dict, expected_content_keys):
    """Test with valid JSON body containing OpenAI fields."""
    content_bytes = json.dumps(body_dict).encode("utf-8")
    headers = {"Authorization": "Bearer sk-secret", "Content-Type": "application/json"}
    request = httpx.Request(
        "POST", "https://api.openai.com/v1/chat/completions", content=content_bytes, headers=headers
    )

    serialized = serialize_openai_chat_request(request)

    assert serialized["method"] == "POST"
    assert serialized["url"] == "https://api.openai.com/v1/chat/completions"
    assert serialized["headers"]["Authorization"] == REDACTED_PLACEHOLDER  # Headers preserve original case
    assert serialized["headers"]["Content-Type"] == "application/json"

    assert isinstance(serialized["content"], dict)
    for key in expected_content_keys:
        assert key in serialized["content"]
        assert serialized["content"][key] == body_dict[key]

    # Ensure only expected OpenAI fields are present (and no extra_field)
    for key in serialized["content"]:
        assert key in OPENAI_CHAT_REQUEST_FIELDS or key == "error"  # Only allow known fields or error


def test_serialize_openai_chat_request_malformed_json(caplog):
    """Test with malformed JSON content."""
    content_bytes = b"{ 'model': 'gpt-4' "
    request = httpx.Request("POST", "url", content=content_bytes, headers={"Content-Type": "application/json"})

    with caplog.at_level(logging.ERROR):
        serialized = serialize_openai_chat_request(request)

    assert "Error parsing OpenAI request" in caplog.text
    assert "content" in serialized
    assert "error" in serialized["content"]
    assert "JSONDecodeError" in serialized["content"]["error"]


def test_serialize_openai_chat_request_non_utf8_content(caplog):
    """Test with content that is not UTF-8 decodable."""
    content_bytes = b"\xff\xfe"  # Invalid UTF-8 sequence
    request = httpx.Request("POST", "url", content=content_bytes, headers={"Content-Type": "application/json"})

    with caplog.at_level(logging.ERROR):
        serialized = serialize_openai_chat_request(request)

    assert "Error parsing OpenAI request" in caplog.text
    assert "content" in serialized
    assert "error" in serialized["content"]
    assert "UnicodeDecodeError" in serialized["content"]["error"]


def test_serialize_openai_chat_request_no_content(caplog):
    """Test with a request that has no content (content is None)."""
    request = httpx.Request("POST", "url", content=None, headers={"Content-Type": "application/json"})

    with caplog.at_level(logging.ERROR):
        serialized = serialize_openai_chat_request(request)

    # httpx.Request().content is an empty bytestring `b''` if content is None at init.
    # json.loads(b'') will raise JSONDecodeError
    assert "Error parsing OpenAI request" in caplog.text
    assert "content" in serialized
    assert "error" in serialized["content"]
    assert "JSONDecodeError" in serialized["content"]["error"]  # Expecting JSONDecodeError for empty string


# --- Tests for OpenAIRequestSpec --- #


def test_openai_request_spec_generate_log_data_with_request():
    """Test generate_log_data with a valid request."""
    body = {"model": "gpt-4", "messages": [{"role": "user", "content": "Test"}]}
    request = httpx.Request("POST", "url", content=json.dumps(body).encode("utf-8"), headers={"X-Test": "value"})
    context = TransactionContext(request=request)
    spec = OpenAIRequestSpec()
    notes_dict: SerializableDict = {"note1": "val1"}

    log_data_obj = spec.generate_log_data(context, notes=notes_dict)

    assert isinstance(log_data_obj, LuthienLogData)
    assert log_data_obj.datatype == "openai_chat_request"
    assert log_data_obj.notes == notes_dict
    assert log_data_obj.data is not None
    assert isinstance(log_data_obj.data, dict)
    assert log_data_obj.data["method"] == "POST"
    assert isinstance(log_data_obj.data["headers"], dict)
    assert log_data_obj.data["headers"]["X-Test"] == "value"  # Headers preserve original case
    assert isinstance(log_data_obj.data["content"], dict)
    assert log_data_obj.data["content"]["model"] == "gpt-4"


def test_openai_request_spec_generate_log_data_no_request(caplog):
    """Test generate_log_data when no request is in the context."""
    context = TransactionContext()
    spec = OpenAIRequestSpec()

    with caplog.at_level(logging.WARNING):
        log_data_obj = spec.generate_log_data(context)

    assert log_data_obj is not None
    assert log_data_obj.datatype == "openai_chat_request"
    assert log_data_obj.data is None
    assert log_data_obj.notes is None
    assert (
        f"OpenAIRequestSpec: No request found in OpenAIRequestSpec for transaction {context.transaction_id}"
        in caplog.text
    )


def test_openai_request_spec_generate_log_data_serialization_error(caplog):
    """Test that generate_log_data handles errors in serialize_openai_chat_request."""

    # Create a request with content that will cause JSON parsing errors
    content_bytes = b"\xff\xfe"  # Invalid UTF-8 content that will cause UnicodeDecodeError
    request = httpx.Request(
        "POST",
        "https://api.openai.com/v1/chat/completions",
        content=content_bytes,
        headers={"Content-Type": "application/json"},
    )
    context = TransactionContext(request=request)
    spec = OpenAIRequestSpec()

    with caplog.at_level(logging.ERROR):
        log_data_obj = spec.generate_log_data(context)

    assert log_data_obj is not None
    assert log_data_obj.datatype == "openai_chat_request"
    assert log_data_obj.data is not None
    assert isinstance(log_data_obj.data, dict)
    assert "content" in log_data_obj.data
    content = log_data_obj.data["content"]
    assert isinstance(content, dict)
    assert "error" in content
    assert "UnicodeDecodeError" in content["error"]

    # Check that error was logged
    assert "Error parsing OpenAI request" in caplog.text
    assert "can't decode byte" in caplog.text


def test_openai_request_spec_serialize():
    """Test the serialization of OpenAIRequestSpec."""
    spec = OpenAIRequestSpec()
    serialized_data = spec.serialize()
    expected_data: SerializableDict = {"type": "OpenAIRequestSpec"}
    assert serialized_data == expected_data


def test_openai_request_spec_from_serialized_impl():
    """Test the deserialization of OpenAIRequestSpec."""
    config: SerializableDict = {"type": "OpenAIRequestSpec"}
    spec = OpenAIRequestSpec._from_serialized_impl(config)
    assert isinstance(spec, OpenAIRequestSpec)

    config_extra: SerializableDict = {"type": "OpenAIRequestSpec", "other_field": "value"}
    spec_extra = OpenAIRequestSpec._from_serialized_impl(config_extra)
    assert isinstance(spec_extra, OpenAIRequestSpec)
