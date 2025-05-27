"""Defines the RequestHeadersSpec for TxLoggingPolicy."""

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


class RequestHeadersSpec(TxLoggingSpec):
    TYPE_NAME = "RequestHeadersSpec"

    def __init__(self):
        pass

    def generate_log_data(
        self, context: "TransactionContext", notes: Optional[SerializableDict] = None
    ) -> Optional[LuthienLogData]:
        if not context.request:
            return None
        try:
            sanitized_headers = sanitize_headers_util(context.request.headers)
            log_data = {
                "method": context.request.method,
                "url": str(context.request.url),
                "headers": sanitized_headers,
            }
            return LuthienLogData(datatype="request_headers", data=log_data, notes=notes)
        except Exception as e:
            print(f"Error in {self.TYPE_NAME} generating log data: {e}")
            return None

    def serialize(self) -> SerializableDict:
        return SerializableDict({"type": self.TYPE_NAME})

    @classmethod
    def _from_serialized_impl(cls, config: SerializableDict) -> "RequestHeadersSpec":
        return cls()
