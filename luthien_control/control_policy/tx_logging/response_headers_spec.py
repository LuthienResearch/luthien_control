"""Defines the ResponseHeadersSpec for TxLoggingPolicy."""

import logging
from typing import TYPE_CHECKING, Optional

from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.control_policy.tx_logging.logging_utils import (
    _sanitize_headers as sanitize_headers_util,
)
from luthien_control.control_policy.tx_logging.tx_logging_spec import (
    LuthienLogData,
    TxLoggingSpec,
)

if TYPE_CHECKING:
    from luthien_control.core.transaction_context import TransactionContext

logger = logging.getLogger(__name__)


class ResponseHeadersSpec(TxLoggingSpec):
    TYPE_NAME = "ResponseHeadersSpec"

    def __init__(self):
        pass

    def generate_log_data(
        self, context: "TransactionContext", notes: Optional[SerializableDict] = None
    ) -> Optional[LuthienLogData]:
        if not context.response:
            return None
        try:
            sanitized_headers = sanitize_headers_util(context.response.headers)
            log_data = {
                "status_code": context.response.status_code,
                "reason_phrase": context.response.reason_phrase,
                "headers": sanitized_headers,
            }
            return LuthienLogData(datatype="response_headers", data=log_data, notes=notes)
        except Exception as e:
            print(f"Error in {self.TYPE_NAME} generating log data: {e}")
            return None

    def serialize(self) -> SerializableDict:
        return SerializableDict({"type": self.TYPE_NAME})

    @classmethod
    def _from_serialized_impl(cls, config: SerializableDict) -> "ResponseHeadersSpec":
        return cls()
