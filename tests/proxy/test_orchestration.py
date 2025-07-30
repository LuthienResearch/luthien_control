import uuid
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import fastapi
import pytest
from fastapi import Response
from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.exceptions import ControlPolicyError
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.raw_response import RawResponse
from luthien_control.proxy.orchestration import _initialize_openai_transaction, run_policy_flow

pytestmark = pytest.mark.asyncio

TEST_REQUEST_BODY = b'{"model": "gpt-4", "messages": [{"role": "user", "content": "test"}]}'
TEST_UUID = uuid.UUID("12345678-1234-5678-1234-567812345678")


def create_test_response():
    """Helper to create a test OpenAI response payload."""
    from luthien_control.api.openai_chat_completions.datatypes import Choice, Message, Usage
    from luthien_control.api.openai_chat_completions.response import OpenAIChatCompletionsResponse
    from psygnal.containers import EventedList

    return OpenAIChatCompletionsResponse(
        id="test-response",
        object="chat.completion",
        created=1234567890,
        model="gpt-4",
        choices=EventedList(
            [Choice(index=0, message=Message(role="assistant", content="Test response"), finish_reason="stop")]
        ),
        usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )


@pytest.fixture
def mock_request():
    request = MagicMock(spec=fastapi.Request)
    request.path_params = {"full_path": "v1/chat/completions"}
    request.method = "POST"
    request.headers = MagicMock()
    request.headers.get = MagicMock(return_value="")
    request.body = AsyncMock(return_value=TEST_REQUEST_BODY)
    return request


class MockPolicy(ControlPolicy):
    """Configurable mock policy for testing."""

    behavior: str = "success"

    def __init__(self, behavior="success", **data):
        data["behavior"] = behavior
        super().__init__(type="mock_policy", **data)
        self.name = data.get("name", "MockPolicy")

    async def apply(self, transaction, container, session):
        transaction.data["main_policy_called"] = True

        if self.behavior == "success":
            if transaction.openai_response is None:
                from luthien_control.core.response import Response

                transaction.openai_response = Response()
            transaction.openai_response.payload = create_test_response()
        elif self.behavior == "none_payload":
            if transaction.openai_response is None:
                from luthien_control.core.response import Response

                transaction.openai_response = Response()
            transaction.openai_response.payload = None
        elif self.behavior == "control_error":
            raise ControlPolicyError("Policy Failed!", policy_name=self.name, status_code=418, detail="Test Detail")
        elif self.behavior == "unexpected_error":
            raise ValueError("Something went very wrong")
        elif self.behavior == "raw_response":
            transaction.raw_response = RawResponse(
                status_code=200,
                headers={"content-type": "application/json"},
                body=b'{"models": ["gpt-3.5", "gpt-4"]}',
                content='{"models": ["gpt-3.5", "gpt-4"]}',
            )

        return transaction

    def serialize(self) -> SerializableDict:
        return {"behavior": self.behavior}

    @classmethod
    def from_serialized(cls, config: SerializableDict, **kwargs) -> "MockPolicy":
        behavior = config.get("behavior", "success")
        return cls(behavior=str(behavior) if behavior is not None else "success")


@pytest.fixture
def mock_policy():
    return MockPolicy("success")


# Core behavior tests - what matters to users


@patch("luthien_control.proxy.orchestration.uuid.uuid4")
@patch("luthien_control.proxy.orchestration.openai_chat_completions_response_to_fastapi_response")
async def test_successful_flow_returns_converted_response(mock_converter, mock_uuid4, mock_request, mock_policy):
    """Test: successful policy execution returns converted response."""
    mock_uuid4.return_value = TEST_UUID
    expected_response = Response(content=b"success")
    mock_converter.return_value = expected_response

    result = await run_policy_flow(mock_request, mock_policy, MagicMock(), AsyncMock())

    assert result is expected_response


@pytest.mark.parametrize(
    "error_behavior,expected_status",
    [
        ("control_error", 418),
        ("unexpected_error", 500),
    ],
)
@patch("luthien_control.proxy.orchestration.uuid.uuid4")
async def test_error_flows_return_json_error(mock_uuid4, mock_request, error_behavior, expected_status):
    """Test: policy errors return appropriate JSON error responses."""
    mock_uuid4.return_value = TEST_UUID
    error_policy = MockPolicy(error_behavior)

    result = await run_policy_flow(mock_request, error_policy, MagicMock(), AsyncMock())

    assert result.status_code == expected_status
    # That's it - we don't care about the exact error message format, just that it's an error


async def test_none_payload_returns_error(mock_request):
    """Test: None payload returns 500 error."""
    none_policy = MockPolicy("none_payload")

    result = await run_policy_flow(mock_request, none_policy, MagicMock(), AsyncMock())

    assert result.status_code == 500


@patch("luthien_control.proxy.orchestration._initialize_openai_transaction")
async def test_initialization_errors_propagate(mock_init, mock_request, mock_policy):
    """Test: initialization errors are not caught."""
    mock_init.side_effect = ValueError("Init failed")

    with pytest.raises(ValueError, match="Init failed"):
        await run_policy_flow(mock_request, mock_policy, MagicMock(), AsyncMock())


async def test_raw_request_flow():
    """Test: raw requests return properly built responses."""
    mock_request = MagicMock(spec=fastapi.Request)
    mock_request.path_params = {"full_path": "v1/models"}
    mock_request.method = "GET"
    mock_request.headers = MagicMock()
    mock_request.headers.get = MagicMock(return_value="Bearer test-key")
    mock_request.headers.items = MagicMock(return_value=[])
    mock_request.body = AsyncMock(return_value=b"")

    raw_policy = MockPolicy("raw_response")

    result = await run_policy_flow(mock_request, raw_policy, MagicMock(), AsyncMock())

    # Core behavior: we get a FastAPI Response with the right content
    assert isinstance(result, fastapi.Response)
    assert result.status_code == 200
    assert b"gpt-3.5" in result.body


async def test_no_raw_response_path():
    """Test: raw request with policy that doesn't set raw_response returns 500 error."""
    mock_request = MagicMock(spec=fastapi.Request)
    mock_request.path_params = {"full_path": "v1/models"}
    mock_request.method = "GET"
    mock_request.headers = MagicMock()
    mock_request.headers.get = MagicMock(return_value="Bearer test-key")
    mock_request.headers.items = MagicMock(return_value=[])
    mock_request.body = AsyncMock(return_value=b"")

    # Policy that doesn't set raw_response for a raw request - should return 500
    normal_policy = MockPolicy("success")

    result = await run_policy_flow(mock_request, normal_policy, MagicMock(), AsyncMock())

    # Should get 500 error when no raw response is set for raw request
    assert result.status_code == 500


# Transaction initialization test - this is a utility function worth testing


async def test_initialize_transaction():
    """Test: transaction initialization works correctly."""
    body = TEST_REQUEST_BODY
    url = "/chat/completions"
    api_key = "test-key"

    transaction = _initialize_openai_transaction(body, url, api_key)

    assert transaction.openai_request is not None
    assert transaction.openai_request.api_endpoint == url
    assert transaction.openai_request.api_key == api_key
    assert transaction.openai_request.payload.model == "gpt-4"


# Debug mode test - simplified to just check if debug info appears


@patch("luthien_control.proxy.orchestration.Settings")
async def test_debug_mode_includes_debug_info(mock_settings_class, mock_request):
    """Test: debug mode includes debug info in error responses."""
    mock_settings = MagicMock()
    mock_settings.dev_mode.return_value = True
    mock_settings_class.return_value = mock_settings

    debug_policy = MagicMock(spec=ControlPolicy)
    debug_policy.name = "DebugPolicy"

    async def mock_apply(transaction, container, session):
        error = ControlPolicyError("Auth failed", policy_name="DebugPolicy", status_code=401)
        setattr(error, "debug_info", {"test": "debug"})
        raise error

    debug_policy.apply = mock_apply

    result = await run_policy_flow(mock_request, debug_policy, MagicMock(), AsyncMock())

    assert result.status_code == 401
    body_text = cast(bytes, result.body).decode()
    assert "debug" in body_text  # Debug info should be present


async def test_openai_streaming_response_flow(mock_request):
    """Test: OpenAI streaming response returns StreamingResponse."""
    from luthien_control.core.response import Response
    from luthien_control.core.streaming_response import ChunkedTextIterator

    # Create a mock policy using MagicMock
    streaming_policy = MagicMock(spec=ControlPolicy)
    streaming_policy.name = "StreamingPolicy"

    # Configure policy to return streaming response
    async def streaming_apply(transaction, container, session):
        transaction.data["main_policy_called"] = True
        if transaction.openai_response is None:
            transaction.openai_response = Response()
        # Create streaming iterator
        streaming_iterator = ChunkedTextIterator("Hello streaming world", chunk_size=5)
        transaction.openai_response.streaming_iterator = streaming_iterator
        return transaction

    streaming_policy.apply = streaming_apply

    with patch("luthien_control.proxy.orchestration.openai_streaming_response_to_fastapi_response") as mock_streaming:
        mock_streaming_response = fastapi.Response(b"streaming content")
        mock_streaming.return_value = mock_streaming_response

        result = await run_policy_flow(mock_request, streaming_policy, MagicMock(), AsyncMock())

        assert result is mock_streaming_response
        mock_streaming.assert_called_once()


async def test_raw_streaming_response_flow():
    """Test: Raw streaming response returns FastAPI StreamingResponse."""
    from luthien_control.core.streaming_response import ChunkedTextIterator

    mock_request = MagicMock(spec=fastapi.Request)
    mock_request.path_params = {"full_path": "v1/models"}
    mock_request.method = "GET"
    mock_request.headers = MagicMock()
    mock_request.headers.get = MagicMock(return_value="Bearer test-key")
    mock_request.headers.items = MagicMock(return_value=[])
    mock_request.body = AsyncMock(return_value=b"")

    # Configure policy to return streaming raw response
    streaming_policy = MagicMock(spec=ControlPolicy)
    streaming_policy.name = "StreamingPolicy"

    async def streaming_apply(transaction, container, session):
        streaming_iterator = ChunkedTextIterator("streaming data", chunk_size=5)
        transaction.raw_response = RawResponse(
            status_code=200, headers={"content-type": "text/event-stream"}, streaming_iterator=streaming_iterator
        )
        return transaction

    streaming_policy.apply = streaming_apply

    result = await run_policy_flow(mock_request, streaming_policy, MagicMock(), AsyncMock())

    # Should get a StreamingResponse
    from fastapi.responses import StreamingResponse

    assert isinstance(result, StreamingResponse)
    assert result.status_code == 200


@patch("luthien_control.proxy.orchestration.Settings")
async def test_unexpected_error_with_debug_info(mock_settings_class, mock_request):
    """Test: unexpected error with debug info in dev mode."""
    mock_settings = MagicMock()
    mock_settings.dev_mode.return_value = True
    mock_settings_class.return_value = mock_settings

    # Policy that raises unexpected error with debug info
    error_policy = MagicMock(spec=ControlPolicy)
    error_policy.name = "ErrorPolicy"

    async def error_apply(transaction, container, session):
        error = ValueError("Unexpected failure")
        setattr(error, "debug_info", {"error_details": "network_timeout"})
        raise error

    error_policy.apply = error_apply

    result = await run_policy_flow(mock_request, error_policy, MagicMock(), AsyncMock())

    assert result.status_code == 500
    body_text = cast(bytes, result.body).decode()
    assert "error_details" in body_text  # Debug info should be present


@patch("luthien_control.proxy.orchestration.Settings")
async def test_control_policy_error_with_cause_debug_info(mock_settings_class, mock_request):
    """Test: ControlPolicyError with debug info in __cause__ exception."""
    mock_settings = MagicMock()
    mock_settings.dev_mode.return_value = True
    mock_settings_class.return_value = mock_settings

    error_policy = MagicMock(spec=ControlPolicy)
    error_policy.name = "CauseErrorPolicy"

    async def cause_error_apply(transaction, container, session):
        # Create underlying exception with debug info
        cause_error = RuntimeError("Underlying error")
        setattr(cause_error, "debug_info", {"cause_details": "connection_failed"})

        # Create ControlPolicyError with the cause
        policy_error = ControlPolicyError("Policy failed", policy_name="CauseErrorPolicy", status_code=502)
        policy_error.__cause__ = cause_error
        raise policy_error

    error_policy.apply = cause_error_apply

    result = await run_policy_flow(mock_request, error_policy, MagicMock(), AsyncMock())

    assert result.status_code == 502
    body_text = cast(bytes, result.body).decode()
    assert "cause_details" in body_text  # Debug info from __cause__ should be present
