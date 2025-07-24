from typing import Optional

from pydantic import Field

from luthien_control.api.openai_chat_completions import OpenAIChatCompletionsResponse
from luthien_control.utils import DeepEventedModel


class Response(DeepEventedModel):
    """A response from the Luthien Control API."""

    payload: Optional[OpenAIChatCompletionsResponse] = Field(default=None)
    api_endpoint: Optional[str] = Field(default=None)
