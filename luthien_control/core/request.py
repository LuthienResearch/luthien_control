from pydantic import Field

from luthien_control.api.openai_chat_completions import OpenAIChatCompletionsRequest
from luthien_control.utils import DeepEventedModel


class Request(DeepEventedModel):
    """A request to the Luthien Control API."""

    payload: OpenAIChatCompletionsRequest = Field()
    api_endpoint: str = Field()
    api_key: str = Field()
