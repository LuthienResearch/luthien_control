from typing import Any, Dict, List, Optional

import httpx
import pytest
from luthien_control.control_policy.tx_logging.logging_utils import (
    REDACTED_PLACEHOLDER,
    SENSITIVE_HEADER_KEYS,
    _sanitize_headers,
    _sanitize_json_payload,
)

# TODO: Add tests for logging_utils

# --- Tests for _sanitize_headers --- #


@pytest.mark.parametrize(
    "input_headers, expected_headers",
    [
        # Basic case with httpx.Headers
        (
            httpx.Headers({"Authorization": "secret", "Content-Type": "application/json"}),
            {"Authorization": REDACTED_PLACEHOLDER, "Content-Type": "application/json"},
        ),
        # Case-insensitivity for sensitive keys
        (
            httpx.Headers({"authorization": "secret", "coNteNt-tYpE": "text/plain"}),
            {"authorization": REDACTED_PLACEHOLDER, "coNteNt-tYpE": "text/plain"},
        ),
        # Multiple sensitive headers
        (
            httpx.Headers({"Authorization": "secret1", "X-Api-Key": "secret2", "User-Agent": "pytest"}),
            {"Authorization": REDACTED_PLACEHOLDER, "X-Api-Key": REDACTED_PLACEHOLDER, "User-Agent": "pytest"},
        ),
        # No sensitive headers
        (
            httpx.Headers({"Content-Type": "application/xml", "Accept": "*/*"}),
            {"Content-Type": "application/xml", "Accept": "*/*"},
        ),
        # Empty headers
        (httpx.Headers(), {}),
        # All known sensitive keys
        (
            httpx.Headers({key: "value" for key in SENSITIVE_HEADER_KEYS}),
            {key: REDACTED_PLACEHOLDER for key in SENSITIVE_HEADER_KEYS},
        ),
        (
            httpx.Headers({key.upper(): "value" for key in SENSITIVE_HEADER_KEYS}),
            {key.upper(): REDACTED_PLACEHOLDER for key in SENSITIVE_HEADER_KEYS},
        ),
    ],
)
def test_sanitize_headers(input_headers: httpx.Headers, expected_headers: Dict[str, str]):
    """Test header sanitization for various cases."""
    sanitized = _sanitize_headers(input_headers)
    assert sanitized == expected_headers


def test_sanitize_headers_plain_dict():
    """Ensure dictionary headers path (non-httpx.Headers) is sanitized."""
    raw = {"Authorization": "s3cr3t", "Content-Type": "application/json", "Cookie": "abc"}
    sanitized = _sanitize_headers(raw)
    assert sanitized["Authorization"] == REDACTED_PLACEHOLDER
    assert sanitized["Cookie"] == REDACTED_PLACEHOLDER
    assert sanitized["Content-Type"] == "application/json"


# --- Tests for _sanitize_json_payload --- #

DEFAULT_SENSITIVE_PAYLOAD_KEYS = ["password", "secret", "apikey", "access_token", "client_secret", "token"]


@pytest.mark.parametrize(
    "payload, custom_sensitive_keys, expected",
    [
        # Basic dictionary with default sensitive key
        ({"user": "test", "password": "s3cr3t"}, None, {"user": "test", "password": REDACTED_PLACEHOLDER}),
        # Nested dictionary
        ({"data": {"token": "xyz", "value": 123}}, None, {"data": {"token": REDACTED_PLACEHOLDER, "value": 123}}),
        # List of dictionaries
        (
            [{"id": 1, "secret": "abc"}, {"id": 2, "value": "safe"}],
            None,
            [{"id": 1, "secret": REDACTED_PLACEHOLDER}, {"id": 2, "value": "safe"}],
        ),
        # Mixed list
        (
            [{"secret": "s1"}, "string", 123, {"password": "p1"}],
            None,
            [{"secret": REDACTED_PLACEHOLDER}, "string", 123, {"password": REDACTED_PLACEHOLDER}],
        ),
        # Case-insensitivity for default keys
        ({"USER": "test", "PassWord": "s3cr3t"}, None, {"USER": "test", "PassWord": REDACTED_PLACEHOLDER}),
        # Custom sensitive keys
        (
            {"apiKey": "customkey", "session_id": "sess123"},
            ["session_id"],
            {"apiKey": "customkey", "session_id": REDACTED_PLACEHOLDER},
        ),
        # Custom sensitive keys (case-insensitive for custom keys too)
        (
            {"apiKey": "customkey", "SESSION_ID": "sess123"},
            ["session_id"],
            {"apiKey": "customkey", "SESSION_ID": REDACTED_PLACEHOLDER},
        ),
        # No sensitive keys in payload
        ({"user": "name", "id": "id1"}, None, {"user": "name", "id": "id1"}),
        # Empty dictionary
        ({}, None, {}),
        # Empty list
        ([], None, []),
        # Primitive type (should return as is)
        ("a_string", None, "a_string"),
        (12345, None, 12345),
        (None, None, None),
        (True, None, True),
        # Payload with a sensitive key not in default list, using custom list
        (
            {"credentials": {"user_token": "tok123"}},
            ["user_token"],
            {"credentials": {"user_token": REDACTED_PLACEHOLDER}},
        ),
        # Payload with sensitive key in default list, but custom list overrides (does not include it)
        (
            {"password": "abc", "custom_field": "xyz"},
            ["custom_field"],
            {"password": "abc", "custom_field": REDACTED_PLACEHOLDER},
        ),
    ],
)
def test_sanitize_json_payload(payload: Any, custom_sensitive_keys: Optional[List[str]], expected: Any):
    """Test JSON payload sanitization for various cases."""
    sanitized = _sanitize_json_payload(payload, sensitive_keys=custom_sensitive_keys)
    assert sanitized == expected


def test_sanitize_json_payload_uses_default_keys():
    """Verify that default sensitive keys are used when sensitive_keys is None."""
    payload = {key: "value" for key in DEFAULT_SENSITIVE_PAYLOAD_KEYS}
    payload["normal_key"] = "normal_value"

    expected = {key: REDACTED_PLACEHOLDER for key in DEFAULT_SENSITIVE_PAYLOAD_KEYS}
    expected["normal_key"] = "normal_value"

    sanitized = _sanitize_json_payload(payload)  # sensitive_keys=None by default
    assert sanitized == expected
