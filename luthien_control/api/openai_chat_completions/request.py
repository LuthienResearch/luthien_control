from typing import Optional

from psygnal.containers import EventedDict as EDict
from psygnal.containers import EventedList as EList
from pydantic import Field

from luthien_control.utils.deep_evented_model import DeepEventedModel

from .datatypes import (
    Audio,
    FunctionDefinition,
    Message,
    Prediction,
    RequestFunctionCallSpec,
    ResponseFormat,
    StreamOptions,
    ToolChoice,
    ToolDefinition,
    WebSearchOptions,
)


class OpenAIChatCompletionsRequest(DeepEventedModel):
    """Request context for OpenAI chat completions.

    Based on the OpenAI API reference:
    https://platform.openai.com/docs/api-reference/chat/create?lang=python
    (retrieved 2025-06-16)

    This model is evented and will emit a `changed` signal on any modification.
    """

    messages: EList[Message] = Field()
    model: str = Field()
    audio: Optional[Audio] = Field(default=None)
    frequency_penalty: Optional[float] = Field(default=None)
    function_call: Optional[RequestFunctionCallSpec] = Field(default=None)  # deprecated
    functions: Optional[EList[FunctionDefinition]] = Field(default=None)  # deprecated
    logit_bias: Optional[EDict[str, float]] = Field(default=None)
    logprobs: Optional[bool] = Field(default=None)
    max_completion_tokens: Optional[int] = Field(default=None)
    max_tokens: Optional[int] = Field(default=None)  # deprecated
    metadata: Optional[EDict[str, str]] = Field(default=None)
    modalities: Optional[EList[str]] = Field(default=None)
    n: Optional[int] = Field(default=None)
    parallel_tool_calls: Optional[bool] = Field(default=None)
    prediction: Optional[Prediction] = Field(default=None)
    presence_penalty: Optional[float] = Field(default=None)
    reasoning_effort: Optional[str] = Field(default=None)  # "low", "medium", "high"
    response_format: Optional[ResponseFormat] = Field(default=None)
    seed: Optional[int] = Field(default=None)
    service_tier: Optional[str] = Field(default=None)
    stop: Optional[str | EList[str]] = Field(default=None)
    store: Optional[bool] = Field(default=None)
    stream: Optional[bool] = Field(default=None)
    stream_options: Optional[StreamOptions] = Field(default=None)
    temperature: Optional[float] = Field(default=None)
    tool_choice: Optional[ToolChoice] = Field(default=None)
    tools: Optional[EList[ToolDefinition]] = Field(default=None)
    top_logprobs: Optional[int] = Field(default=None)
    top_p: Optional[float] = Field(default=None)
    user: Optional[str] = Field(default=None)
    web_search_options: Optional[WebSearchOptions] = Field(default=None)
