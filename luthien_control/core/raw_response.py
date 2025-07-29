from typing import Dict, Optional

from pydantic import Field

from luthien_control.utils import DeepEventedModel


class RawResponse(DeepEventedModel):
    """A raw HTTP response."""

    status_code: int = Field()
    headers: Dict[str, str] = Field(default_factory=dict)
    body: Optional[bytes] = Field(default=None)
    content: Optional[str] = Field(default=None)
