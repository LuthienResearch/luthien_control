"""Defines the OpenAIResponseSpec for TxLoggingPolicy."""

import json
import logging
from typing import Any, Dict, List, Optional

import httpx

from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.control_policy.tx_logging.logging_utils import (
    _sanitize_headers,
)
from luthien_control.control_policy.tx_logging.tx_logging_spec import (
    LuthienLogData,
    TxLoggingSpec,
)
from luthien_control.core.tracked_context import TrackedContext

logger = logging.getLogger(__name__)

OPENAI_CHAT_RESPONSE_FIELDS: List[str] = [
    "id",
    "object",
    "created",
    "model",
    "choices",
    "usage",
    "system_fingerprint",
]


def serialize_openai_chat_response(response) -> Dict[str, Any]:
    """Serializes a TrackedResponse from OpenAI Chat Completions.

    Extracts relevant fields from the JSON body and includes sanitized headers
    and status code.

    Args:
        response: The TrackedResponse object from OpenAI Chat Completions.

    Returns:
        A dictionary representing the serialized OpenAI chat response.
    """
    # Handle both httpx.Response and TrackedResponse
    if hasattr(response, "get_headers"):
        # TrackedResponse
        serialized_data = {
            "status_code": response.status_code,
            "headers": _sanitize_headers(response.get_headers()),
        }
        openai_payload = {}
        try:
            response_body = response.get_json()
            for field in OPENAI_CHAT_RESPONSE_FIELDS:
                if field in response_body:
                    openai_payload[field] = response_body[field]
        except (json.JSONDecodeError, UnicodeDecodeError, AttributeError) as e:
            logger.error(f"Error parsing OpenAI response: {e}")
            openai_payload["error"] = f"{type(e).__name__}: {str(e)}"
    else:
        # httpx.Response (legacy compatibility)
        serialized_data = {
            "status_code": response.status_code,
            "headers": _sanitize_headers(response.headers),  # General header sanitization
            "elapsed_ms": response.elapsed.total_seconds() * 1000,
            "reason_phrase": response.reason_phrase,
            "http_version": response.http_version,
        }
        openai_payload = {}
        try:
            # Ensure content is read. httpx.Response.json() handles decoding.
            response_body = response.json()
            for field in OPENAI_CHAT_RESPONSE_FIELDS:
                if field in response_body:
                    openai_payload[field] = response_body[field]

        except (json.JSONDecodeError, httpx.ResponseNotRead, UnicodeDecodeError, AttributeError) as e:
            logger.error(f"Error parsing OpenAI response: {e}")
            openai_payload["error"] = f"{type(e).__name__}: {str(e)}"

    serialized_data["content"] = openai_payload
    return serialized_data


class OpenAIResponseSpec(TxLoggingSpec):
    TYPE_NAME = "OpenAIResponseSpec"

    def __init__(self):
        pass

    def generate_log_data(self, context: "TrackedContext", notes: Optional[SerializableDict] = None) -> LuthienLogData:
        if not context.response:
            logger.warning(
                f"OpenAIResponseSpec: No response found in {self.TYPE_NAME} for transaction {context.transaction_id}"
            )
            return LuthienLogData(datatype="openai_chat_response", data=None, notes=notes)
        serialized_data = serialize_openai_chat_response(context.response)
        return LuthienLogData(datatype="openai_chat_response", data=serialized_data, notes=notes)

    def serialize(self) -> SerializableDict:
        return SerializableDict({"type": self.TYPE_NAME})

    @classmethod
    def _from_serialized_impl(cls, config: SerializableDict) -> "OpenAIResponseSpec":
        return cls()
