from typing import Any, Optional
from uuid import UUID, uuid4

from psygnal.containers import EventedDict
from pydantic import Field, model_validator

from luthien_control.core.raw_request import RawRequest
from luthien_control.core.raw_response import RawResponse
from luthien_control.core.request import Request
from luthien_control.core.request_type import RequestType
from luthien_control.core.response import Response
from luthien_control.utils import DeepEventedModel


class Transaction(DeepEventedModel):
    """A transaction between the Luthien Control API and the client."""

    transaction_id: UUID = Field(default_factory=uuid4)
    openai_request: Optional[Request] = Field(default=None)
    openai_response: Optional[Response] = Field(default=None)
    raw_request: Optional[RawRequest] = Field(default=None)
    raw_response: Optional[RawResponse] = Field(default=None)
    data: EventedDict[str, Any] = Field(default_factory=EventedDict)

    @model_validator(mode="after")
    def validate_request_type(self):
        if self.openai_request is not None and self.raw_request is not None:
            raise ValueError("Transaction cannot have both openai_request and raw_request")
        if self.openai_request is None and self.raw_request is None:
            raise ValueError("Transaction must have either openai_request or raw_request")
        return self

    @property
    def request_type(self) -> RequestType:
        return RequestType.OPENAI_CHAT if self.openai_request else RequestType.RAW_PASSTHROUGH
