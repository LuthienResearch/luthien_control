from typing import Optional

from pydantic import Field

from luthien_control.api.openai_chat_completions import OpenAIChatCompletionsResponse
from luthien_control.core.streaming_response import StreamingResponseIterator
from luthien_control.utils import DeepEventedModel


class Response(DeepEventedModel):
    """A response from the Luthien Control API."""

    payload: Optional[OpenAIChatCompletionsResponse] = Field(default=None)
    api_endpoint: Optional[str] = Field(default=None)
    streaming_iterator: Optional[StreamingResponseIterator] = Field(default=None, exclude=True)

    @property
    def is_streaming(self) -> bool:
        """Check if this is a streaming response."""
        return self.streaming_iterator is not None
