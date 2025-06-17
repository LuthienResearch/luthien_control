from typing import Optional

from psygnal.containers import EventedList as EList
from pydantic import Field

from luthien_control.utils.deep_evented_model import DeepEventedModel

from .datatypes import (
    Choice,
    Usage,
)


class OpenAIChatCompletionsResponse(DeepEventedModel):
    """The request for a chat completion."""

    choices: EList[Choice] = Field(default_factory=lambda: EList[Choice]())
    created: int = Field()
    id: str = Field()
    model: str = Field()
    object: str = Field()
    service_tier: Optional[str] = Field(default=None)
    system_fingerprint: Optional[str] = Field(default=None)
    usage: Usage = Field(default_factory=Usage)
