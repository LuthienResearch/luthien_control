from typing import Dict, Optional

from pydantic import Field

from luthien_control.core.streaming_response import StreamingResponseIterator
from luthien_control.utils import DeepEventedModel


class RawResponse(DeepEventedModel):
    """A raw HTTP response."""

    status_code: int = Field()
    headers: Dict[str, str] = Field(default_factory=dict)
    body: Optional[bytes] = Field(default=None)
    content: Optional[str] = Field(default=None)
    streaming_iterator: Optional[StreamingResponseIterator] = Field(default=None, exclude=True)

    @property
    def is_streaming(self) -> bool:
        """Check if this is a streaming response."""
        return self.streaming_iterator is not None
