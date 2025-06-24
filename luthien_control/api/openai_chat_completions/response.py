from typing import Optional

import fastapi
from psygnal.containers import EventedList as EList
from pydantic import Field

from luthien_control.api.openai_chat_completions.datatypes import (
    Choice,
    Usage,
)
from luthien_control.utils.deep_evented_model import DeepEventedModel


class OpenAIChatCompletionsResponse(DeepEventedModel):
    """The request for a chat completion."""

    choices: EList[Choice] = Field(default_factory=lambda: EList[Choice]())
    created: int = Field()
    id: str = Field()
    model: str = Field()
    object: str = Field(default="chat.completion")
    service_tier: Optional[str] = Field(default=None)
    system_fingerprint: Optional[str] = Field(default=None)
    usage: Usage = Field(default_factory=Usage)


def openai_chat_completions_response_to_fastapi_response(response: OpenAIChatCompletionsResponse) -> fastapi.Response:
    return fastapi.Response(content=response.model_dump_json(), status_code=200)
