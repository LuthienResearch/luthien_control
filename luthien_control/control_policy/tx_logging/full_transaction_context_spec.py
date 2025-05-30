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
from luthien_control.core.transaction_context import TransactionContext

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


def _serialize_httpx_request(request: httpx.Request) -> Dict[str, Any]:
    """Serializes an httpx.Request object for logging.

    Args:
        request: The httpx.Request object.

    Returns:
        A dictionary representing the serialized request.
    """
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


def _serialize_httpx_response(response: httpx.Response) -> Dict[str, Any]:
    """Serializes an httpx.Response object for logging.

    Args:
        response: The httpx.Response object.

    Returns:
        A dictionary representing the serialized response.
    """
    headers = _sanitize_headers(response.headers)
    headers = {k.lower(): v for k, v in headers.items()}
    content_type = headers.get("content-type")

    serialized_response = {
        "status_code": response.status_code,
        "headers": headers,
        "http_version": response.http_version,
        "elapsed_ms": response.elapsed.total_seconds() * 1000,
        "reason_phrase": response.reason_phrase,
        "content_type": content_type,
    }

    content_bytes: Optional[bytes] = None
    content_bytes = response.content

    serialized_response.update(_serialize_content_bytes(content_bytes, content_type))

    return serialized_response


class FullTransactionContextSpec(TxLoggingSpec):
    TYPE_NAME = "FullTransactionContextSpec"

    def generate_log_data(
        self, context: "TransactionContext", notes: Optional[SerializableDict] = None
    ) -> LuthienLogData:
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
            log_payload["request"] = _serialize_httpx_request(context.request)
        if context.response:
            log_payload["response"] = _serialize_httpx_response(context.response)
        if context.data:
            log_payload["context_data"] = context.data
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
