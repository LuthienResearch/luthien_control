from typing import Any, Optional

from psygnal.containers import EventedDict
from pydantic import Field

from luthien_control.core.request import Request
from luthien_control.core.response import Response
from luthien_control.utils import DeepEventedModel


class Transaction(DeepEventedModel):
    """A transaction between the Luthien Control API and the client."""

    request: Request = Field()
    response: Response = Field()
    data: Optional[EventedDict[str, Any]] = Field(default=None)
