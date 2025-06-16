"""Utility functions and constants for logging serialization."""

from typing import Any, Dict, List, Optional

import httpx

SENSITIVE_HEADER_KEYS: List[str] = [
    "authorization",
    "proxy-authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "api-key",
    "secret",
    "token",
]
REDACTED_PLACEHOLDER: str = "[REDACTED]"

MAX_CONTENT_BYTES_LOG: int = 1024 * 10  # Log up to 10KB of content


def _sanitize_headers(headers: httpx.Headers) -> Dict[str, str]:
    """Sanitizes sensitive information from HTTP headers.

    Args:
        headers: HTTP headers.

    Returns:
        A dictionary of headers with sensitive values redacted.
    """
    sanitized = {}

    for key_bytes, value_bytes in headers.raw:
        key = key_bytes.decode("ascii")
        value = value_bytes.decode("ascii")
        if key.lower() in SENSITIVE_HEADER_KEYS:
            sanitized[key] = REDACTED_PLACEHOLDER
        else:
            sanitized[key] = value

    return sanitized


def _sanitize_json_payload(payload: Any, sensitive_keys: Optional[List[str]] = None) -> Any:
    """Recursively sanitizes sensitive keys in a JSON-like structure (dicts and lists).

    Args:
        payload: The JSON-like data (dicts, lists, or other primitives).
        sensitive_keys: A list of keys (case-insensitive) to redact.
                        If None, defaults to a common list of sensitive keys.

    Returns:
        The sanitized payload.
    """
    if sensitive_keys is None:
        # A more comprehensive list might be needed based on actual data
        sensitive_keys = ["password", "secret", "apikey", "access_token", "client_secret", "token"]

    sensitive_keys_lower = [key.lower() for key in sensitive_keys]

    if isinstance(payload, dict):
        return {
            k: REDACTED_PLACEHOLDER if k.lower() in sensitive_keys_lower else _sanitize_json_payload(v, sensitive_keys)
            for k, v in payload.items()
        }
    elif isinstance(payload, list):
        return [_sanitize_json_payload(item, sensitive_keys) for item in payload]
    else:
        return payload
