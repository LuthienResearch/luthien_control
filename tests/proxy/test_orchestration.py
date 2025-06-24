import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import fastapi
import httpx
import pytest
from fastapi import Response
from luthien_control.core.transaction import Transaction
from luthien_control.new_control_policy.control_policy import ControlPolicy
from luthien_control.new_control_policy.exceptions import ControlPolicyError
from luthien_control.proxy.orchestration import _initialize_transaction, run_policy_flow
from luthien_control.settings import Settings
from sqlalchemy.ext.asyncio import AsyncSession

# Mark all tests in this module as async
pytestmark = pytest.mark.asyncio

# --- Constants ---
TEST_REQUEST_BODY = b'{"model": "gpt-4", "messages": [{"role": "user", "content": "test"}]}'


@pytest.fixture
def mock_request() -> MagicMock:
    request = MagicMock(spec=fastapi.Request)
    request.scope = {"type": "http", "method": "GET", "path": "/test/path"}
    request.path_params = {"full_path": "/test/path"}
    request.method = "GET"  # Explicitly set the method attribute
    request.query_params = MagicMock(spec=fastapi.datastructures.QueryParams)  # Use MagicMock for query_params
    request.headers = MagicMock(spec=fastapi.datastructures.Headers)
    request.headers.get = MagicMock(return_value="")  # Return empty string for authorization header
    request.headers.raw = []  # httpx.Request needs list of tuples
    request.body = AsyncMock(return_value=TEST_REQUEST_BODY)
    # Add client attribute needed by FastAPI/Starlette internally sometimes
    request.client = MagicMock()
    request.client.host = "testclient"
    request.client.port = 12345
    return request


@pytest.fixture
def mock_settings() -> MagicMock:
    return MagicMock(spec=Settings)


@pytest.fixture
def mock_http_client() -> AsyncMock:
    return AsyncMock(spec=httpx.AsyncClient)


@pytest.fixture
def mock_policy() -> AsyncMock:
    """Provides a single mock ControlPolicy instance that doesn't set context.response."""
    policy_mock = AsyncMock(spec=ControlPolicy)

    # Explicitly define apply to return the transaction passed to it, accepting container and session
    async def apply_effect(transaction, container, session):
        # Simulate some action (optional)
        transaction.data["main_policy_called"] = True
        # Set a mock response payload for testing
        from luthien_control.api.openai_chat_completions.datatypes import Choice, Message, Usage
        from luthien_control.api.openai_chat_completions.response import OpenAIChatCompletionsResponse
        from psygnal.containers import EventedList

        transaction.response.payload = OpenAIChatCompletionsResponse(
            id="test-response",
            object="chat.completion",
            created=1234567890,
            model="gpt-4",
            choices=EventedList(
                [Choice(index=0, message=Message(role="assistant", content="Test response"), finish_reason="stop")]
            ),
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )
        # Return the same transaction
        return transaction

    policy_mock.apply = AsyncMock(side_effect=apply_effect)

    return policy_mock


@pytest.fixture
def mock_policy_raising_exception() -> AsyncMock:
    """Provides a single mock ControlPolicy that raises ControlPolicyError."""
    policy_mock = AsyncMock(spec=ControlPolicy)
    # Provide more details in the mock error for testing
    policy_mock.apply.side_effect = ControlPolicyError(
        "Policy Failed!", policy_name="MockPolicy", status_code=418, detail="Test Detail"
    )
    policy_mock.name = "MockPolicy"  # Ensure name attribute exists
    return policy_mock


@pytest.fixture
def mock_session() -> AsyncMock:
    """Provides a mock AsyncSession."""
    return AsyncMock(spec=AsyncSession)


@patch("luthien_control.proxy.orchestration.uuid.uuid4")
@patch("luthien_control.proxy.orchestration.openai_chat_completions_response_to_fastapi_response")
@patch("luthien_control.proxy.orchestration.logger")  # Patch logger
@patch("luthien_control.proxy.orchestration.JSONResponse")  # Patch JSONResponse used directly now
async def test_run_policy_flow_successful(
    MockJSONResponse: MagicMock,
    mock_logger: MagicMock,
    mock_response_converter: MagicMock,
    mock_uuid4: MagicMock,
    mock_request: MagicMock,
    mock_policy: AsyncMock,
    mock_container: MagicMock,
    mock_session: AsyncMock,
):
    """
    Test Goal: Verify the happy path: context init, policy runs, builder invoked.
    (Added logger/JSONResponse patches for consistency, though not strictly needed here)
    """
    fixed_test_uuid = uuid.UUID("12345678-1234-5678-1234-567812345678")
    mock_uuid4.return_value = fixed_test_uuid

    # Mock the response converter to return a fastapi response
    expected_final_response = Response(content=b"built response")
    mock_response_converter.return_value = expected_final_response

    # Call the orchestrator
    response = await run_policy_flow(
        request=mock_request,
        main_policy=mock_policy,
        dependencies=mock_container,  # Pass mock_container
        session=mock_session,
    )

    # Assertions
    mock_request.body.assert_awaited_once()
    mock_uuid4.assert_called_once()
    mock_policy.apply.assert_awaited_once()
    call_args, call_kwargs = mock_policy.apply.await_args
    assert isinstance(call_kwargs.get("transaction"), Transaction)
    assert call_kwargs.get("transaction").transaction_id == fixed_test_uuid
    assert call_kwargs.get("container") is mock_container  # Check against mock_container
    assert call_kwargs.get("session") is mock_session

    # Response converter should be called with the response payload
    mock_response_converter.assert_called_once()
    # The policy should have set response payload (mocked in this test)
    # In a real scenario, the policy would set transaction.response.payload

    # Direct JSONResponse should *not* be called in happy path
    MockJSONResponse.assert_not_called()
    # Warning/exception logger should not be called
    mock_logger.warning.assert_not_called()
    mock_logger.exception.assert_not_called()

    # Final response check
    assert response is expected_final_response


@patch("luthien_control.proxy.orchestration.uuid.uuid4")
@patch("luthien_control.proxy.orchestration.logger")  # Patch logger
@patch("luthien_control.proxy.orchestration.JSONResponse")  # Patch JSONResponse used directly now
async def test_run_policy_flow_policy_exception(
    MockJSONResponse: MagicMock,
    mock_logger: MagicMock,
    mock_uuid4: MagicMock,
    mock_request: MagicMock,
    mock_policy_raising_exception: AsyncMock,
    mock_container: MagicMock,  # Renamed fixture
    mock_session: AsyncMock,
):
    """
    Test Goal: Verify ControlPolicyError is caught, logged, *direct* JSONResponse used.
    Builder should NOT be called.
    """
    fixed_test_uuid = uuid.UUID("abcdefab-cdef-abcd-efab-cdefabcdefab")
    mock_uuid4.return_value = fixed_test_uuid

    # Configure the mocked JSONResponse (used directly in this path)
    expected_error_response = Response(content=b"direct json error response")
    MockJSONResponse.return_value = expected_error_response

    # No ResponseBuilder to configure in this path

    # Call the orchestrator
    response = await run_policy_flow(
        request=mock_request,
        main_policy=mock_policy_raising_exception,
        dependencies=mock_container,  # Pass mock_container
        session=mock_session,
    )

    # Assertions
    mock_request.body.assert_awaited_once()
    mock_uuid4.assert_called_once()
    mock_policy_raising_exception.apply.assert_awaited_once()
    call_args, call_kwargs = mock_policy_raising_exception.apply.await_args
    assert isinstance(call_kwargs.get("transaction"), Transaction)
    assert call_kwargs.get("container") is mock_container  # Check against mock_container
    assert call_kwargs.get("session") is mock_session

    # Logging (Warning for ControlPolicyError)
    mock_logger.warning.assert_called_once()
    log_message = mock_logger.warning.call_args[0][0]
    assert f"[{fixed_test_uuid}] Control policy error halted execution:" in log_message
    assert "Policy Failed!" in log_message  # Check original exception message
    mock_logger.exception.assert_not_called()  # No unexpected exceptions logged

    # Response Building (direct JSONResponse IS called)
    MockJSONResponse.assert_called_once()

    # Check args passed to JSONResponse
    json_call_kwargs = MockJSONResponse.call_args.kwargs
    assert json_call_kwargs.get("status_code") == 418  # Status from mock exception
    content = json_call_kwargs.get("content")
    assert content is not None
    assert isinstance(content, dict)
    assert content["transaction_id"] == str(fixed_test_uuid)
    assert "Policy error in 'MockPolicy': Test Detail" in content["detail"]

    # Final Response
    assert response is expected_error_response


@patch("luthien_control.proxy.orchestration.uuid.uuid4")
@patch("luthien_control.proxy.orchestration.logger")  # Patch logger
@patch("luthien_control.proxy.orchestration.JSONResponse")  # Patch JSONResponse fallback
async def test_run_policy_flow_unexpected_exception(
    MockJSONResponse: MagicMock,
    mock_logger: MagicMock,
    mock_uuid4: MagicMock,
    mock_request: MagicMock,
    mock_policy: AsyncMock,
    mock_container: MagicMock,
    mock_session: AsyncMock,
):
    """
    Test Goal: Verify unexpected Exception is caught, logged, builder *is* called,
               and builder's response returned. Fallback JSONResponse not used.
    """
    fixed_test_uuid = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
    mock_uuid4.return_value = fixed_test_uuid

    unexpected_error = ValueError("Something went very wrong")
    mock_policy.apply.side_effect = unexpected_error

    # Configure fallback JSONResponse (this should be called for unexpected errors)
    expected_error_response = Response(content=b"error response")
    MockJSONResponse.return_value = expected_error_response

    # Call the orchestrator
    response = await run_policy_flow(
        request=mock_request,
        main_policy=mock_policy,
        dependencies=mock_container,
        session=mock_session,
    )

    # Assertions
    mock_request.body.assert_awaited_once()
    mock_uuid4.assert_called_once()
    mock_policy.apply.assert_awaited_once()
    call_args, call_kwargs = mock_policy.apply.await_args
    assert isinstance(call_kwargs.get("transaction"), Transaction)
    assert call_kwargs.get("container") is mock_container
    assert call_kwargs.get("session") is mock_session

    # Logging (Exception logged for the unexpected error)
    mock_logger.exception.assert_called_once()
    log_message = mock_logger.exception.call_args[0][0]
    assert f"[{fixed_test_uuid}] Unhandled exception during policy flow:" in log_message
    assert "Something went very wrong" in log_message  # Check original exception message
    mock_logger.warning.assert_not_called()  # No policy warnings logged

    # Response Building (JSONResponse IS called for unexpected exceptions)
    MockJSONResponse.assert_called_once()
    json_call_kwargs = MockJSONResponse.call_args.kwargs
    assert json_call_kwargs.get("status_code") == 500
    content = json_call_kwargs.get("content")
    assert content is not None
    assert isinstance(content, dict)
    assert content["transaction_id"] == str(fixed_test_uuid)
    assert "Internal Server Error" in content["detail"]

    # Final Response
    assert response is expected_error_response


@patch("luthien_control.proxy.orchestration.uuid.uuid4")
@patch("luthien_control.proxy.orchestration.openai_chat_completions_response_to_fastapi_response")
@patch("luthien_control.proxy.orchestration.logger")  # Patch logger
@patch("luthien_control.proxy.orchestration.JSONResponse")  # Patch JSONResponse fallback
async def test_run_policy_flow_unexpected_exception_during_build(
    MockJSONResponse: MagicMock,
    mock_logger: MagicMock,
    mock_response_converter: MagicMock,
    mock_uuid4: MagicMock,
    mock_request: MagicMock,
    mock_policy: AsyncMock,  # Use regular policy, trigger error in builder
    mock_container: MagicMock,
    mock_session: AsyncMock,
):
    """
    Test Goal: Verify if response converter fails after successful policy execution,
               the error is caught and JSONResponse is used as fallback.
    """
    fixed_test_uuid = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
    mock_uuid4.return_value = fixed_test_uuid

    # Policy runs successfully (uses default mock_policy which sets response payload)
    # But response converter will fail
    converter_error = RuntimeError("Response converter failed!")
    mock_response_converter.side_effect = converter_error

    # Configure the mocked JSONResponse (fallback)
    expected_fallback_response = Response(content=b"fallback json response")
    MockJSONResponse.return_value = expected_fallback_response

    # Call the orchestrator
    response = await run_policy_flow(
        request=mock_request,
        main_policy=mock_policy,  # Pass regular policy
        dependencies=mock_container,
        session=mock_session,
    )

    # Assertions
    mock_request.body.assert_awaited_once()
    mock_uuid4.assert_called_once()
    mock_policy.apply.assert_awaited_once()  # Policy called successfully
    call_args, call_kwargs = mock_policy.apply.await_args
    assert isinstance(call_kwargs.get("transaction"), Transaction)
    assert call_kwargs.get("container") is mock_container
    assert call_kwargs.get("session") is mock_session

    # Response converter was called but failed
    mock_response_converter.assert_called_once()

    # Logging (Converter error should be logged)
    mock_logger.exception.assert_called_once()
    log_message = mock_logger.exception.call_args[0][0]
    assert f"[{fixed_test_uuid}] Unhandled exception during policy flow:" in log_message
    assert "Response converter failed!" in log_message

    # Response Building (JSONResponse fallback IS called)
    MockJSONResponse.assert_called_once()  # Fallback JSONResponse was called

    # Check args passed to fallback JSONResponse
    json_call_kwargs = MockJSONResponse.call_args.kwargs
    assert json_call_kwargs.get("status_code") == 500
    content = json_call_kwargs.get("content")
    assert content is not None
    assert isinstance(content, dict)
    assert content["transaction_id"] == str(fixed_test_uuid)
    # Check detail message
    assert "Internal Server Error" in content["detail"]

    # Final Response
    assert response is expected_fallback_response


@patch("luthien_control.proxy.orchestration._initialize_transaction")
@patch("luthien_control.proxy.orchestration.logger")
@patch("luthien_control.proxy.orchestration.JSONResponse")
async def test_run_policy_flow_context_init_exception(
    MockJSONResponse: MagicMock,
    mock_logger: MagicMock,
    mock_init_transaction: MagicMock,
    mock_request: MagicMock,
    mock_policy: AsyncMock,
    mock_container: MagicMock,
    mock_session: AsyncMock,
):
    """
    Test Goal: Verify if _initialize_transaction fails, the exception propagates OUT.
    The orchestrator's try/except should NOT catch this.
    """
    transaction_error = ValueError("Transaction creation failed!")
    mock_init_transaction.side_effect = transaction_error

    # Call the orchestrator and assert the correct exception is raised
    with pytest.raises(ValueError, match="Transaction creation failed!"):
        await run_policy_flow(
            request=mock_request,
            main_policy=mock_policy,
            dependencies=mock_container,
            session=mock_session,
        )

    # Assertions: Ensure things *didn't* happen past the point of failure
    mock_request.body.assert_awaited_once()  # Body read before transaction init attempt
    # Check that _initialize_transaction was called with body, url, and api_key
    mock_init_transaction.assert_called_once()
    call_args = mock_init_transaction.call_args
    assert call_args[0][0] == TEST_REQUEST_BODY  # body
    assert call_args[0][1] == "/test/path"  # url from path_params
    assert call_args[0][2] == ""  # api_key (empty from mock headers)

    mock_policy.apply.assert_not_awaited()  # Policy not called
    mock_logger.exception.assert_not_called()  # Logger within run_policy_flow not called
    mock_logger.warning.assert_not_called()
    MockJSONResponse.assert_not_called()  # Fallback JSONResponse not created


async def test_initialize_context_query_params():
    """_initialize_transaction should store the URL and API key."""
    body = b'{"model": "gpt-4", "messages": [{"role": "user", "content": "test"}]}'
    url = "/chat/completions"
    api_key = "test-api-key"

    # _initialize_transaction now takes body, url, and api_key
    transaction = _initialize_transaction(body, url, api_key)

    assert transaction.request is not None
    assert transaction.request.api_endpoint == url
    assert transaction.request.api_key == api_key
    assert transaction.request.payload.model == "gpt-4"
    assert len(transaction.request.payload.messages) == 1
    assert transaction.request.payload.messages[0].content == "test"
