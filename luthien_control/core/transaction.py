from typing import Any
from uuid import UUID, uuid4

from psygnal.containers import EventedDict
from pydantic import Field

from luthien_control.core.request import Request
from luthien_control.core.response import Response
from luthien_control.utils import DeepEventedModel


class Transaction(DeepEventedModel):
    """A transaction between the Luthien Control API and the client."""

    transaction_id: UUID = Field(default_factory=uuid4)
    openai_request: Request = Field()
    openai_response: Response = Field()
    data: EventedDict[str, Any] = Field(default_factory=EventedDict)
