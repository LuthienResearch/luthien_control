from typing import Any, Literal, Optional, Type, Union

from psygnal.containers import EventedDict as EDict
from psygnal.containers import EventedList as EList
from pydantic import Field

from luthien_control.utils.deep_evented_model import DeepEventedModel

"""
Supporting data types for OpenAI chat completions.

Based on
https://platform.openai.com/docs/api-reference/chat/object and
https://platform.openai.com/docs/api-reference/chat/create
(2025-06-16)

Example OpenAI streaming response:
{
  "id": "chatcmpl-B9MHDbslfkBeAs8l4bebGdFOJ6PeG",
  "object": "chat.completion",
  "created": 1741570283,
  "model": "gpt-4o-2024-08-06",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "The image shows a wooden boardwalk.",
        "refusal": null,
        "annotations": []
      },
      "logprobs": null,
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 1117,
    "completion_tokens": 6,
    "total_tokens": 1123,
    "prompt_tokens_details": {
      "cached_tokens": 0,
      "audio_tokens": 0
    },
    "completion_tokens_details": {
      "reasoning_tokens": 0,
      "audio_tokens": 0,
      "accepted_prediction_tokens": 0,
      "rejected_prediction_tokens": 0
    }
  },
  "service_tier": "default",
  "system_fingerprint": "fp_fc9f1d7035"
}
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
    """Function call details.

    For streaming responses, name may be provided in the first chunk and arguments
    may be built up incrementally across multiple chunks.
    """

    arguments: str = Field(default="")
    name: Optional[str] = Field(default=None)


class ToolCall(DeepEventedModel):
    """Tool/function call made by the model.

    For streaming responses, the index field indicates the position in the tool_calls array,
    allowing reconstruction of the complete array from multiple chunks where each chunk
    may contain only a subset of the tool calls.
    """

    id: Optional[str] = Field(default=None)
    function: FunctionCall = Field()
    type: Optional[str] = Field(default="function")
    index: Optional[int] = Field(default=None, description="Index in tool_calls array (used in streaming responses)")


class Message(DeepEventedModel):
    """A message in a chat completion."""

    role: str = Field()
    content: str = Field()
    refusal: Optional[str] = Field(default=None)
    annotations: EList[Annotation] = Field(default_factory=lambda: EList[Annotation]())
    audio: Optional[Audio] = Field(default=None)
    function_call: Optional[FunctionCall] = Field(default=None)
    tool_calls: Optional[EList[ToolCall]] = Field(default_factory=lambda: None)


class LogProbs(DeepEventedModel):
    """Log probability information for the choice."""

    content: Optional[EList[EDict]] = Field(default_factory=lambda: EList[EDict]())
    refusal: Optional[EList[EDict]] = Field(default_factory=lambda: EList[EDict]())


class Choice(DeepEventedModel):
    """A single choice in a chat completion response."""

    index: int = Field(default=0)
    message: Message = Field()
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

    prompt_tokens: int = Field()
    completion_tokens: int = Field()
    total_tokens: int = Field()
    prompt_tokens_details: PromptTokensDetails = Field(default_factory=PromptTokensDetails)
    completion_tokens_details: CompletionTokensDetails = Field(default_factory=CompletionTokensDetails)


# ------------------ Request Objects ------------------


class ImageUrl(DeepEventedModel):
    """The image URL details."""

    url: str
    detail: Literal["auto", "low", "high"] = "auto"


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

    type: Literal["text", "json_object", "json_schema"] = Field(default="text")
    json_schema: Optional[EDict[str, Type]] = Field(default=None)


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
