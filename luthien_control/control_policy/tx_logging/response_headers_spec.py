"""Defines the ResponseHeadersSpec for TxLoggingPolicy."""

import logging
from typing import Optional

from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.control_policy.tx_logging.logging_utils import (
    _sanitize_headers as sanitize_headers_util,
)
from luthien_control.control_policy.tx_logging.tx_logging_spec import (
    LuthienLogData,
    TxLoggingSpec,
)
from luthien_control.core.tracked_context import TrackedContext

logger = logging.getLogger(__name__)


class ResponseHeadersSpec(TxLoggingSpec):
    TYPE_NAME = "ResponseHeadersSpec"

    def __init__(self):
        pass

    def generate_log_data(self, context: "TrackedContext", notes: Optional[SerializableDict] = None) -> LuthienLogData:
        if not context.response:
            logger.warning(
                f"ResponseHeadersSpec: No response found in {self.TYPE_NAME} for transaction {context.transaction_id}"
            )
            return LuthienLogData(datatype="response_headers", data=None, notes=notes)
        sanitized_headers = sanitize_headers_util(context.response.headers)
        log_data = {
            "status_code": context.response.status_code,
            "headers": sanitized_headers,
        }
        return LuthienLogData(datatype="response_headers", data=log_data, notes=notes)

    def serialize(self) -> SerializableDict:
        return SerializableDict({"type": self.TYPE_NAME})

    @classmethod
    def _from_serialized_impl(cls, config: SerializableDict) -> "ResponseHeadersSpec":
        return cls()
