"""Defines the OpenAIResponseSpec for TxLoggingPolicy."""

import json
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import httpx

from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.control_policy.tx_logging.logging_utils import (
    _sanitize_headers,
)
from luthien_control.control_policy.tx_logging.tx_logging_spec import (
    LuthienLogData,
    TxLoggingSpec,
)

if TYPE_CHECKING:
    from luthien_control.core.transaction_context import TransactionContext

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


def serialize_openai_chat_response(response: httpx.Response) -> Dict[str, Any]:
    """Serializes an httpx.Response known to be from OpenAI Chat Completions.

    Extracts relevant fields from the JSON body and includes sanitized headers
    and status code.

    Args:
        response: The httpx.Response object from OpenAI Chat Completions.

    Returns:
        A dictionary representing the serialized OpenAI chat response.
    """
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

    def generate_log_data(
        self, context: "TransactionContext", notes: Optional[SerializableDict] = None
    ) -> Optional[LuthienLogData]:
        if not context.response:
            return None
        try:
            serialized_data = serialize_openai_chat_response(context.response)
            return LuthienLogData(datatype="openai_chat_response", data=serialized_data, notes=notes)
        except Exception as e:
            print(f"Error in {self.TYPE_NAME} generating log data: {e}")
            return None

    def serialize(self) -> SerializableDict:
        return SerializableDict({"type": self.TYPE_NAME})

    @classmethod
    def _from_serialized_impl(cls, config: SerializableDict) -> "OpenAIResponseSpec":
        return cls()
