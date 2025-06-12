"""Defines the FullTransactionContextSpec for TxLoggingPolicy."""

import json
import logging
from typing import Any, Dict, Optional, Union

import httpx

from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.control_policy.tx_logging.logging_utils import (
    _sanitize_headers,
    _sanitize_json_payload,
)
from luthien_control.control_policy.tx_logging.tx_logging_spec import (
    LuthienLogData,
    TxLoggingSpec,
)
from luthien_control.core.tracked_context import TrackedContext

logger = logging.getLogger(__name__)


def _serialize_content_bytes(
    content_bytes: Optional[bytes],
    content_type: Optional[str],
) -> Dict[str, Union[str, dict, None]]:
    """Serializes content bytes based on content type, handling truncation and errors.

    Modifies target_dict in place to add error keys like 'content_parse_error'
    or 'content_decode_error' if they occur.

    Args:
        content_bytes: The raw bytes of the content. Can be None or empty.
        content_type: The raw value of the 'Content-Type' header (e.g.,
                             "application/json; charset=utf-8", or None if missing).

    Returns:
        The serialized content representation, or None if content_bytes is None or empty.
    """
    if not content_bytes:
        return {"content": None}

    result = {}

    normalized_content_type = content_type.lower() if content_type else ""
    result["content_type"] = normalized_content_type

    if "application/json" in normalized_content_type:
        try:
            json_body = json.loads(content_bytes.decode("utf-8"))
            result["content"] = _sanitize_json_payload(json_body)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error(f"Error parsing JSON content: {e}")
            result["error"] = f"json_error: {type(e).__name__} - {str(e)}"
            return result
    elif normalized_content_type.startswith("text/"):
        try:
            result["content"] = content_bytes.decode("utf-8")
        except UnicodeDecodeError as e:
            logger.error(f"Error decoding text content: {e}")
            result["error"] = f"text_decode_error: {type(e).__name__} - {str(e)}"
            return result
    else:
        result["content"] = f"{content_bytes.hex()}"

    return result


def _serialize_request(request) -> Dict[str, Any]:
    """Serializes a request object (TrackedRequest or httpx.Request) for logging.

    Args:
        request: The request object to serialize.

    Returns:
        A dictionary representing the serialized request.
    """
    # Handle both TrackedRequest and httpx.Request
    if hasattr(request, "get_headers"):
        # TrackedRequest
        headers = _sanitize_headers(request.get_headers())
        headers = {k.lower(): v for k, v in headers.items()}
        serialized_request = {
            "method": request.method,
            "url": request.url,
            "headers": headers,
        }
        content_bytes = request.content
        content_type = headers.get("content-type")
    else:
        # httpx.Request (legacy compatibility)
        headers = _sanitize_headers(request.headers)
        headers = {k.lower(): v for k, v in headers.items()}
        serialized_request = {
            "method": request.method,
            "url": str(request.url),
            "headers": headers,
        }
        content_bytes = request.content
        content_type = headers.get("content-type")

    serialized_request.update(_serialize_content_bytes(content_bytes, content_type))
    return serialized_request


def _serialize_httpx_request(request: httpx.Request) -> Dict[str, Any]:
    """Legacy compatibility wrapper for httpx.Request objects."""
    return _serialize_request(request)


def _serialize_response(response) -> Dict[str, Any]:
    """Serializes a response object (TrackedResponse or httpx.Response) for logging.

    Args:
        response: The response object to serialize.

    Returns:
        A dictionary representing the serialized response.
    """
    # Handle both TrackedResponse and httpx.Response
    if hasattr(response, "get_headers"):
        # TrackedResponse
        headers = _sanitize_headers(response.get_headers())
        headers = {k.lower(): v for k, v in headers.items()}
        content_type = headers.get("content-type")

        serialized_response = {
            "status_code": response.status_code,
            "headers": headers,
            "content_type": content_type,
        }
        content_bytes = response.content
    else:
        # httpx.Response (legacy compatibility)
        headers = _sanitize_headers(response.headers)
        headers = {k.lower(): v for k, v in headers.items()}
        content_type = headers.get("content-type")

        serialized_response = {
            "status_code": response.status_code,
            "headers": headers,
            "content_type": content_type,
        }
        # Only add optional fields if they exist
        if hasattr(response, "_elapsed"):
            serialized_response["elapsed_ms"] = response.elapsed.total_seconds() * 1000
        if hasattr(response, "reason_phrase") and response.reason_phrase:
            serialized_response["reason_phrase"] = response.reason_phrase
        if hasattr(response, "http_version") and response.http_version:
            serialized_response["http_version"] = response.http_version
        content_bytes = response.content

    serialized_response.update(_serialize_content_bytes(content_bytes, content_type))
    return serialized_response


def _serialize_httpx_response(response: httpx.Response) -> Dict[str, Any]:
    """Legacy compatibility wrapper for httpx.Response objects."""
    return _serialize_response(response)


class FullTransactionContextSpec(TxLoggingSpec):
    TYPE_NAME = "FullTransactionContextSpec"

    def generate_log_data(self, context: "TrackedContext", notes: Optional[SerializableDict] = None) -> LuthienLogData:
        """
        Generates a LuthienLogData object containing the full transaction context.

        Args:
            context: The TransactionContext object containing the request, response, and data.
            notes: Optional notes to include in the log data.

        Returns:
            A LuthienLogData object containing the full transaction context.
        """
        log_payload: dict[str, Any] = {}
        if context.request:
            log_payload["request"] = _serialize_request(context.request)
        if context.response:
            log_payload["response"] = _serialize_response(context.response)
        # Get data from TrackedContext
        context_data = context.get_all_data()
        log_payload["context_data"] = context_data
        return LuthienLogData(datatype="full_transaction_context", data=log_payload, notes=notes)

    def serialize(self) -> SerializableDict:
        return SerializableDict(
            {
                "type": self.TYPE_NAME,
            }
        )

    @classmethod
    def _from_serialized_impl(cls, config: SerializableDict) -> "FullTransactionContextSpec":
        return cls()
