from typing import Any, Optional, Type, Union

from psygnal.containers import EventedDict as EDict
from psygnal.containers import EventedList as EList
from pydantic import Field, field_validator

from luthien_control.utils.deep_evented_model import DeepEventedModel

"""
Supporting data types for OpenAI chat completions.

Based on
https://platform.openai.com/docs/api-reference/chat/object and
https://platform.openai.com/docs/api-reference/chat/create
(2025-06-16)
"""


class URLCitation(DeepEventedModel):
    end_index: int = Field()
    start_index: int = Field()
    title: str = Field()
    url: str = Field()


class Annotation(DeepEventedModel):
    url_citation: URLCitation = Field()
    type: str = Field(default="url_citation")


class Audio(DeepEventedModel):
    data: str = Field()
    expires_at: int = Field()
    id: str = Field()
    transcript: str = Field()


class FunctionCall(DeepEventedModel):
    arguments: str = Field()
    name: str = Field()


class ToolCall(DeepEventedModel):
    id: str = Field()
    function: FunctionCall = Field()
    type: str = Field(default="function")


class Message(DeepEventedModel):
    """A message in a chat completion."""

    content: Optional[str] = Field(default=None)
    refusal: Optional[str] = Field(default=None)
    role: str = Field(default_factory=str)
    annotations: EList[Annotation] = Field(default_factory=lambda: EList[Annotation]())
    audio: Optional[Audio] = Field(default=None)
    function_call: Optional[FunctionCall] = Field(default=None)
    tool_calls: Optional[EList[ToolCall]] = Field(default_factory=lambda: EList[ToolCall]())


class LogProbs(DeepEventedModel):
    """Log probability information for the choice."""

    content: Optional[EList[EDict]] = Field(default_factory=lambda: EList[EDict]())
    refusal: Optional[EList[EDict]] = Field(default_factory=lambda: EList[EDict]())


class Choice(DeepEventedModel):
    """A single choice in a chat completion response."""

    index: int = Field(default=0)
    message: Message = Field(default_factory=Message)
    finish_reason: Optional[str] = Field(default=None)
    logprobs: Optional[LogProbs] = Field(default=None)


class PromptTokensDetails(DeepEventedModel):
    """Details about prompt token usage."""

    cached_tokens: int = Field(default=0)
    audio_tokens: int = Field(default=0)


class CompletionTokensDetails(DeepEventedModel):
    """Details about completion token usage."""

    reasoning_tokens: int = Field(default=0)
    audio_tokens: int = Field(default=0)
    accepted_prediction_tokens: int = Field(default=0)
    rejected_prediction_tokens: int = Field(default=0)


class Usage(DeepEventedModel):
    """Token usage statistics for the chat completion request."""

    prompt_tokens: int = Field(default=0)
    completion_tokens: int = Field(default=0)
    total_tokens: int = Field(default=0)
    prompt_tokens_details: Optional[PromptTokensDetails] = Field(default_factory=PromptTokensDetails)
    completion_tokens_details: Optional[CompletionTokensDetails] = Field(default_factory=CompletionTokensDetails)


# ------------------ Request Objects ------------------


class ImageUrl(DeepEventedModel):
    """The image URL details."""

    url: str
    detail: str = "auto"

    @field_validator("detail")
    def detail_must_be_valid(cls, v: str) -> str:
        """Validate that detail is one of 'auto', 'low', or 'high'."""
        if v not in ("auto", "low", "high"):
            raise ValueError("detail must be 'auto', 'low', or 'high'")
        return v


class ContentPartText(DeepEventedModel):
    """A text content part."""

    type: str = Field(default="text", frozen=True)
    text: str = Field()


class ContentPartImage(DeepEventedModel):
    """An image content part."""

    type: str = Field(default="image_url", frozen=True)
    image_url: ImageUrl = Field()


class ResponseFormat(DeepEventedModel):
    """An object specifying the format that the model must output.

    See https://platform.openai.com/docs/guides/structured-outputs?api-mode=responses
    """

    type: str = Field(default="text")
    json_schema: Optional[EDict[str, Type]] = Field(default=None)

    @field_validator("type")
    def type_must_be_valid(cls, v: str) -> str:
        if v not in ("text", "json_object", "json_schema"):
            raise ValueError("type must be 'text', 'json_object', or 'json_schema'")
        return v

    @field_validator("json_schema")
    def json_schema_must_be_valid(cls, v: Optional[EDict[str, Type]]) -> Optional[EDict[str, Type]]:
        if v is None:
            return v
        for key, value in v.items():
            if not isinstance(key, str):
                raise ValueError(f"json_schema keys must be strings, got {key} of type {type(key)}")
            if not isinstance(value, type):
                raise ValueError(f"json_schema values must be types, got {value} of type {type(value)}")
        return v


class FunctionDefinition(DeepEventedModel):
    """The definition of a function that can be called by the model."""

    name: str = Field()
    description: Optional[str] = Field(default=None)
    parameters: Optional[EDict[str, Any]] = Field(default_factory=EDict)


class ToolDefinition(DeepEventedModel):
    """A tool that can be used by the model."""

    type: str = Field(default="function", frozen=True)
    function: FunctionDefinition = Field()


class ToolChoiceFunction(DeepEventedModel):
    """The function to call in a tool choice."""

    name: str = Field()


class ToolChoice(DeepEventedModel):
    """A specific tool choice."""

    type: str = Field(default="function", frozen=True)
    function: ToolChoiceFunction = Field()


class RequestFunctionCall(DeepEventedModel):
    """A function call in a request."""

    name: str = Field()


RequestFunctionCallSpec = Union[str, RequestFunctionCall]

Content = Union[str, EList[Union[ContentPartText, ContentPartImage]]]


class Prediction(DeepEventedModel):
    content: Content = Field()


class StreamOptions(DeepEventedModel):
    include_usage: Optional[bool] = Field(default=None)


class ApproximateLocation(DeepEventedModel):
    city: Optional[str] = Field(default=None)
    country: Optional[str] = Field(default=None)
    region: Optional[str] = Field(default=None)
    timezone: Optional[str] = Field(default=None)


class UserLocation(DeepEventedModel):
    approximate: Optional[ApproximateLocation] = Field(default=None)
    type: Optional[str] = Field(default=None)


class WebSearchOptions(DeepEventedModel):
    search_context_size: Optional[str] = Field(default=None)
    user_location: Optional[UserLocation] = Field(default=None)
