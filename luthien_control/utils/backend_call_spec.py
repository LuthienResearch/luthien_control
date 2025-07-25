from typing import Any

from pydantic import BaseModel, Field


class BackendCallSpec(BaseModel):
    """
    A specification for a backend LLM call.
    """

    model: str = Field(default="gpt-4o-mini")
    api_endpoint: str = Field(default="https://api.openai.com/")
    api_key_env_var: str = Field(default="OPENAI_API_KEY")
    request_args: dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments to be passed to OpenAIChatCompletionsRequest.",
    )
