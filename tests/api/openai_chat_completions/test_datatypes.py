import pytest
from luthien_control.api.openai_chat_completions.datatypes import (
    Annotation,
    ApproximateLocation,
    Audio,
    Choice,
    CompletionTokensDetails,
    ContentPartImage,
    ContentPartText,
    FunctionCall,
    FunctionDefinition,
    ImageUrl,
    LogProbs,
    Message,
    Prediction,
    PromptTokensDetails,
    ResponseFormat,
    StreamOptions,
    ToolCall,
    ToolChoice,
    ToolChoiceFunction,
    ToolDefinition,
    URLCitation,
    Usage,
    UserLocation,
    WebSearchOptions,
)
from pydantic import ValidationError


def test_url_citation_instantiation():
    """Test that URLCitation can be instantiated."""
    instance = URLCitation(end_index=1, start_index=0, title="test", url="http://example.com")
    assert isinstance(instance, URLCitation)


def test_annotation_instantiation():
    """Test that Annotation can be instantiated."""
    citation = URLCitation(end_index=1, start_index=0, title="test", url="http://example.com")
    instance = Annotation(url_citation=citation)
    assert isinstance(instance, Annotation)


def test_audio_instantiation():
    """Test that Audio can be instantiated."""
    instance = Audio(data="data", expires_at=123, id="id", transcript="transcript")
    assert isinstance(instance, Audio)


def test_function_call_instantiation():
    """Test that FunctionCall can be instantiated."""
    instance = FunctionCall(arguments="{}", name="test_func")
    assert isinstance(instance, FunctionCall)


def test_tool_call_instantiation():
    """Test that ToolCall can be instantiated."""
    func_call = FunctionCall(arguments="{}", name="test_func")
    instance = ToolCall(id="tool1", function=func_call)
    assert isinstance(instance, ToolCall)


def test_message_instantiation():
    """Test that Message can be instantiated."""
    instance = Message(content="hello", role="user")
    assert isinstance(instance, Message)


def test_log_probs_instantiation():
    """Test that LogProbs can be instantiated."""
    instance = LogProbs()
    assert isinstance(instance, LogProbs)


def test_choice_instantiation():
    """Test that Choice can be instantiated."""
    instance = Choice()
    assert isinstance(instance, Choice)


def test_prompt_tokens_details_instantiation():
    """Test that PromptTokensDetails can be instantiated."""
    instance = PromptTokensDetails()
    assert isinstance(instance, PromptTokensDetails)


def test_completion_tokens_details_instantiation():
    """Test that CompletionTokensDetails can be instantiated."""
    instance = CompletionTokensDetails()
    assert isinstance(instance, CompletionTokensDetails)


def test_usage_instantiation():
    """Test that Usage can be instantiated."""
    instance = Usage()
    assert isinstance(instance, Usage)


def test_image_url_instantiation():
    """Test that ImageUrl can be instantiated and validates `detail`."""
    # Test default value
    instance = ImageUrl(url="http://example.com/img.png")
    assert instance.detail == "auto"

    # Test explicit valid values
    for detail_value in ["auto", "low", "high"]:
        instance = ImageUrl(url="http://example.com/img.png", detail=detail_value)  # type: ignore
        assert instance.detail == detail_value

    # Test invalid value
    with pytest.raises(ValidationError):
        ImageUrl(url="http://example.com/img.png", detail="invalid")  # type: ignore


def test_content_part_text_instantiation():
    """Test that ContentPartText can be instantiated."""
    instance = ContentPartText(text="Hello")
    assert isinstance(instance, ContentPartText)
    assert instance.text == "Hello"


def test_content_part_image_instantiation():
    """Test that ContentPartImage can be instantiated."""
    img_url = ImageUrl(url="http://example.com/img.png")
    instance = ContentPartImage(image_url=img_url)
    assert isinstance(instance, ContentPartImage)


def test_response_format_json_schema_validation():
    """Test json_schema validation in ResponseFormat."""
    from psygnal.containers import EventedDict as EDict

    # Test with valid json_schema
    valid_schema = EDict({"name": str, "age": int})
    instance = ResponseFormat(type="json_schema", json_schema=valid_schema)
    assert instance.json_schema == valid_schema

    # Test with None json_schema
    instance_none = ResponseFormat(type="json_schema", json_schema=None)
    assert instance_none.json_schema is None

    # Test with invalid type for validation
    with pytest.raises(ValidationError):
        ResponseFormat(type="invalid_format", json_schema=None)  # type: ignore

    # Test with invalid json_schema - non-string key
    with pytest.raises(ValidationError):
        ResponseFormat(type="json_schema", json_schema=EDict({123: int}))

    # Test with invalid json_schema - non-type value
    with pytest.raises(ValidationError):
        ResponseFormat(type="json_schema", json_schema=EDict({"name": "not_a_type"}))


def test_function_definition_instantiation():
    """Test that FunctionDefinition can be instantiated."""
    instance = FunctionDefinition(name="my_func", description="A test function.")
    assert isinstance(instance, FunctionDefinition)


def test_tool_definition_instantiation():
    """Test that ToolDefinition can be instantiated."""
    func_def = FunctionDefinition(name="my_func")
    instance = ToolDefinition(function=func_def)
    assert isinstance(instance, ToolDefinition)


def test_tool_choice_function_instantiation():
    """Test that ToolChoiceFunction can be instantiated."""
    instance = ToolChoiceFunction(name="my_func")
    assert isinstance(instance, ToolChoiceFunction)


def test_tool_choice_instantiation():
    """Test that ToolChoice can be instantiated."""
    func_choice = ToolChoiceFunction(name="my_func")
    instance = ToolChoice(function=func_choice)
    assert isinstance(instance, ToolChoice)


def test_prediction_instantiation():
    """Test that Prediction can be instantiated."""
    instance = Prediction(content="predicted text")
    assert isinstance(instance, Prediction)


def test_stream_options_instantiation():
    """Test that StreamOptions can be instantiated."""
    instance = StreamOptions(include_usage=True)
    assert isinstance(instance, StreamOptions)


def test_approximate_location_instantiation():
    """Test that ApproximateLocation can be instantiated."""
    instance = ApproximateLocation(city="San Francisco")
    assert isinstance(instance, ApproximateLocation)


def test_user_location_instantiation():
    """Test that UserLocation can be instantiated."""
    approx = ApproximateLocation(city="San Francisco")
    instance = UserLocation(approximate=approx)
    assert isinstance(instance, UserLocation)


def test_web_search_options_instantiation():
    """Test that WebSearchOptions can be instantiated."""
    instance = WebSearchOptions(search_context_size="small")
    assert isinstance(instance, WebSearchOptions)
