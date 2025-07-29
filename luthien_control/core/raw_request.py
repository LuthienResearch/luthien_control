from typing import Dict, Optional

from pydantic import Field

from luthien_control.utils import DeepEventedModel


class RawRequest(DeepEventedModel):
    """A raw HTTP request."""

    method: str = Field()
    path: str = Field()
    headers: Dict[str, str] = Field(default_factory=dict)
    body: Optional[bytes] = Field(default=None)
    api_key: str = Field()
    backend_url: Optional[str] = Field(default=None)
