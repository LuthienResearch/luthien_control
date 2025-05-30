"""Defines the OpenAIRequestSpec for TxLoggingPolicy."""

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
from luthien_control.core.transaction_context import TransactionContext

logger = logging.getLogger(__name__)

OPENAI_CHAT_REQUEST_FIELDS: List[str] = [
    "model",
    "messages",
    "temperature",
    "top_p",
    "n",
    "stream",
    "stop",
    "max_tokens",
    "presence_penalty",
    "frequency_penalty",
    "logit_bias",
    "user",
    "functions",
    "function_call",
    "tools",
    "tool_choice",
    "response_format",
]


def serialize_openai_chat_request(request: httpx.Request) -> Dict[str, Any]:
    """Serializes an httpx.Request known to be for OpenAI Chat Completions.

    Extracts relevant fields from the JSON body and sanitizes headers.

    Args:
        request: The httpx.Request object for OpenAI Chat Completions.

    Returns:
        A dictionary representing the serialized OpenAI chat request.
    """
    serialized_data = {
        "method": request.method,
        "url": str(request.url),
        "headers": _sanitize_headers(request.headers),  # General header sanitization
    }
    openai_payload = {}
    try:
        request_body = json.loads(request.content.decode("utf-8"))
        for field in OPENAI_CHAT_REQUEST_FIELDS:
            if field in request_body:
                openai_payload[field] = request_body[field]

    except (json.JSONDecodeError, UnicodeDecodeError, AttributeError) as e:
        logger.error(f"Error parsing OpenAI request: {e}")
        openai_payload["error"] = f"{type(e).__name__}: {str(e)}"

    serialized_data["content"] = openai_payload
    return serialized_data


class OpenAIRequestSpec(TxLoggingSpec):
    TYPE_NAME = "OpenAIRequestSpec"

    def __init__(self):
        pass

    def generate_log_data(
        self, context: "TransactionContext", notes: Optional[SerializableDict] = None
    ) -> LuthienLogData:
        if not context.request:
            logger.warning(
                f"OpenAIRequestSpec: No request found in {self.TYPE_NAME} for transaction {context.transaction_id}"
            )
            return LuthienLogData(datatype="openai_chat_request", data=None, notes=notes)
        serialized_data = serialize_openai_chat_request(context.request)
        return LuthienLogData(datatype="openai_chat_request", data=serialized_data, notes=notes)

    def serialize(self) -> SerializableDict:
        return SerializableDict({"type": self.TYPE_NAME})

    @classmethod
    def _from_serialized_impl(cls, config: SerializableDict) -> "OpenAIRequestSpec":
        return cls()
