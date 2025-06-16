import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import fastapi
import httpx
import pytest
from fastapi import Response
from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.exceptions import ControlPolicyError
from luthien_control.core.tracked_context import TrackedContext
from luthien_control.proxy.orchestration import _initialize_context, run_policy_flow
from luthien_control.settings import Settings
from sqlalchemy.ext.asyncio import AsyncSession

# Mark all tests in this module as async
pytestmark = pytest.mark.asyncio

# --- Constants ---
TEST_REQUEST_BODY = b'{"test": "body"}'


@pytest.fixture
def mock_request() -> MagicMock:
    request = MagicMock(spec=fastapi.Request)
    request.scope = {"type": "http", "method": "GET", "path": "/test/path"}
    request.path_params = {"full_path": "/test/path"}
    request.method = "GET"  # Explicitly set the method attribute
    request.query_params = MagicMock(spec=fastapi.datastructures.QueryParams)  # Use MagicMock for query_params
    request.headers = MagicMock(spec=fastapi.datastructures.Headers)
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

    # Explicitly define apply to return the context passed to it, accepting container and session
    async def apply_effect(context, container, session):
        # Simulate some action (optional)
        context.set_data("main_policy_called", True)
        # Return the same context (TrackedContext)
        return context

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
@patch("luthien_control.proxy.orchestration.ResponseBuilder")  # Patch the builder where it's used
@patch("luthien_control.proxy.orchestration.logger")  # Patch logger
@patch("luthien_control.proxy.orchestration.JSONResponse")  # Patch JSONResponse used directly now
async def test_run_policy_flow_successful(
    MockJSONResponse: MagicMock,
    mock_logger: MagicMock,
    MockDefaultBuilder: MagicMock,
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

    mock_builder_instance = MockDefaultBuilder.return_value
    expected_final_response = Response(content=b"built response")
    mock_builder_instance.build_response.return_value = expected_final_response

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
    assert isinstance(call_kwargs.get("context"), TrackedContext)
    assert call_kwargs.get("context").transaction_id == fixed_test_uuid
    assert call_kwargs.get("container") is mock_container  # Check against mock_container
    assert call_kwargs.get("session") is mock_session

    # Builder *is* used in happy path
    MockDefaultBuilder.assert_called_once_with()
    mock_builder_instance.build_response.assert_called_once()
    context_arg = mock_builder_instance.build_response.call_args[0][0]
    assert isinstance(context_arg, TrackedContext)
    assert context_arg.transaction_id == fixed_test_uuid
    assert context_arg.get_data("main_policy_called") is True

    # Direct JSONResponse should *not* be called in happy path
    MockJSONResponse.assert_not_called()
    # Warning/exception logger should not be called
    mock_logger.warning.assert_not_called()
    mock_logger.exception.assert_not_called()

    # Final response check
    assert response is expected_final_response


@patch("luthien_control.proxy.orchestration.uuid.uuid4")
@patch("luthien_control.proxy.orchestration.ResponseBuilder")  # Patch builder, it's instantiated but not used
@patch("luthien_control.proxy.orchestration.logger")  # Patch logger
@patch("luthien_control.proxy.orchestration.JSONResponse")  # Patch JSONResponse used directly now
async def test_run_policy_flow_policy_exception(
    MockJSONResponse: MagicMock,
    mock_logger: MagicMock,
    MockDefaultBuilder: MagicMock,
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

    # Configure the mocked ResponseBuilder instance (should not be called)
    mock_builder_instance = MockDefaultBuilder.return_value
    mock_builder_instance.build_response.return_value = Response(content=b"builder response NOT USED")

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
    assert isinstance(call_kwargs.get("context"), TrackedContext)
    assert call_kwargs.get("container") is mock_container  # Check against mock_container
    assert call_kwargs.get("session") is mock_session

    # Logging (Warning for ControlPolicyError)
    mock_logger.warning.assert_called_once()
    log_message = mock_logger.warning.call_args[0][0]
    assert f"[{fixed_test_uuid}] Control policy error halted execution:" in log_message
    assert "Policy Failed!" in log_message  # Check original exception message
    mock_logger.exception.assert_not_called()  # No unexpected exceptions logged

    # Response Building (Builder NOT called, direct JSONResponse IS called)
    MockDefaultBuilder.assert_called_once_with()  # Builder is instantiated
    mock_builder_instance.build_response.assert_not_called()  # But build_response is NOT called
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
@patch("luthien_control.proxy.orchestration.ResponseBuilder")  # Patch the builder
@patch("luthien_control.proxy.orchestration.logger")  # Patch logger
@patch("luthien_control.proxy.orchestration.JSONResponse")  # Patch JSONResponse fallback
async def test_run_policy_flow_unexpected_exception(
    MockJSONResponse: MagicMock,
    mock_logger: MagicMock,
    MockDefaultBuilder: MagicMock,
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

    # Configure the mocked ResponseBuilder instance (this path *tries* to use it)
    mock_builder_instance = MockDefaultBuilder.return_value
    expected_builder_error_response = Response(content=b"builder error response")
    mock_builder_instance.build_response.return_value = expected_builder_error_response

    # Configure fallback JSONResponse (should not be called here)
    MockJSONResponse.return_value = Response(content=b"fallback json response NOT USED")

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
    assert isinstance(call_kwargs.get("context"), TrackedContext)
    assert call_kwargs.get("container") is mock_container
    assert call_kwargs.get("session") is mock_session

    # Logging (Exception logged for the unexpected error)
    mock_logger.exception.assert_called_once()
    log_message = mock_logger.exception.call_args[0][0]
    assert f"[{fixed_test_uuid}] Unhandled exception during policy flow:" in log_message
    assert "Something went very wrong" in log_message  # Check original exception message
    mock_logger.warning.assert_not_called()  # No policy warnings logged

    # Response Building (Builder *is* called, fallback JSONResponse is NOT)
    MockDefaultBuilder.assert_called_once_with()
    mock_builder_instance.build_response.assert_called_once()
    context_arg = mock_builder_instance.build_response.call_args[0][0]
    assert isinstance(context_arg, TrackedContext)
    assert context_arg.transaction_id == fixed_test_uuid
    MockJSONResponse.assert_not_called()  # Fallback not used

    # Final Response (should be the one from the builder)
    assert response is expected_builder_error_response


@patch("luthien_control.proxy.orchestration.uuid.uuid4")
@patch("luthien_control.proxy.orchestration.ResponseBuilder")  # Patch builder
@patch("luthien_control.proxy.orchestration.logger")  # Patch logger
@patch("luthien_control.proxy.orchestration.JSONResponse")  # Patch JSONResponse fallback
async def test_run_policy_flow_unexpected_exception_during_build(
    MockJSONResponse: MagicMock,
    mock_logger: MagicMock,
    MockDefaultBuilder: MagicMock,
    mock_uuid4: MagicMock,
    mock_request: MagicMock,
    mock_policy: AsyncMock,  # Use regular policy, trigger error in builder
    mock_container: MagicMock,
    mock_session: AsyncMock,
):
    """
    Test Goal: Verify if builder fails *after* an unexpected policy error,
               both errors are logged, and the fallback JSONResponse is used.
    """
    fixed_test_uuid = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
    mock_uuid4.return_value = fixed_test_uuid

    # Simulate initial unexpected error during policy apply
    initial_unexpected_error = TypeError("Initial policy error")
    mock_policy.apply.side_effect = initial_unexpected_error

    # Configure the mocked ResponseBuilder instance to fail
    mock_builder_instance = MockDefaultBuilder.return_value
    builder_error = RuntimeError("Builder failed!")
    mock_builder_instance.build_response.side_effect = builder_error

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
    mock_policy.apply.assert_awaited_once()  # Policy called, raised initial error
    call_args, call_kwargs = mock_policy.apply.await_args
    assert isinstance(call_kwargs.get("context"), TrackedContext)
    assert call_kwargs.get("container") is mock_container
    assert call_kwargs.get("session") is mock_session

    # Logging (TWO exceptions logged)
    assert mock_logger.exception.call_count == 2
    # Log 1: Initial unexpected error
    log_call_1 = mock_logger.exception.call_args_list[0]
    log_message_1 = log_call_1[0][0]
    assert f"[{fixed_test_uuid}] Unhandled exception during policy flow:" in log_message_1
    assert "Initial policy error" in log_message_1
    # Log 2: Builder error
    log_call_2 = mock_logger.exception.call_args_list[1]
    log_message_2 = log_call_2[0][0]
    assert f"[{fixed_test_uuid}] Exception occurred *during* error response building:" in log_message_2
    assert "Builder failed!" in log_message_2  # Builder error message
    assert "Initial policy error" in log_message_2  # Original error mentioned

    # Response Building (Builder called and failed, JSONResponse fallback IS called)
    MockDefaultBuilder.assert_called_once_with()
    mock_builder_instance.build_response.assert_called_once()  # Builder was called
    MockJSONResponse.assert_called_once()  # Fallback JSONResponse was called

    # Check args passed to fallback JSONResponse
    json_call_kwargs = MockJSONResponse.call_args.kwargs
    assert json_call_kwargs.get("status_code") == 500
    content = json_call_kwargs.get("content")
    assert content is not None
    assert isinstance(content, dict)
    assert content["transaction_id"] == str(fixed_test_uuid)
    # Check detail message mentions both errors
    assert "Initial error: Initial policy error" in content["detail"]
    assert "Error during response building: Builder failed!" in content["detail"]

    # Final Response
    assert response is expected_fallback_response


@patch("luthien_control.proxy.orchestration._initialize_context")
@patch("luthien_control.proxy.orchestration.ResponseBuilder")
@patch("luthien_control.proxy.orchestration.logger")
@patch(
    "luthien_control.proxy.orchestration.JSONResponse"
)  # Keep patch for other tests, but it shouldn't be called here
async def test_run_policy_flow_context_init_exception(
    MockJSONResponse: MagicMock,
    mock_logger: MagicMock,
    MockDefaultBuilder: MagicMock,
    mock_init_context: MagicMock,
    mock_request: MagicMock,
    mock_policy: AsyncMock,
    mock_container: MagicMock,
    mock_session: AsyncMock,
):
    """
    Test Goal: Verify if _initialize_context fails, the exception propagates OUT.
    The orchestrator's try/except should NOT catch this.
    """
    context_error = ValueError("Context creation failed!")
    mock_init_context.side_effect = context_error

    # Call the orchestrator and assert the correct exception is raised
    with pytest.raises(ValueError, match="Context creation failed!"):
        await run_policy_flow(
            request=mock_request,
            main_policy=mock_policy,
            dependencies=mock_container,
            session=mock_session,
        )

    # Assertions: Ensure things *didn't* happen past the point of failure
    mock_request.body.assert_awaited_once()  # Body read before context init attempt
    mock_init_context.assert_called_once_with(mock_request, TEST_REQUEST_BODY)
    mock_policy.apply.assert_not_awaited()  # Policy not called
    mock_logger.exception.assert_not_called()  # Logger within run_policy_flow not called
    mock_logger.warning.assert_not_called()
    MockDefaultBuilder.assert_not_called()  # Builder instance not created
    MockJSONResponse.assert_not_called()  # Fallback JSONResponse not created


async def test_initialize_context_query_params():
    """_initialize_context should build full URL including query parameters."""
    request = SimpleNamespace()
    request.headers = {"x-test": "1"}
    request.method = "GET"
    request.path_params = {"full_path": "/chat"}
    request.query_params = {"foo": "bar", "baz": "qux"}
    body = b"hello"

    # _initialize_context expects a real fastapi.Request; we supply a stub.
    ctx = _initialize_context(request, body)  # type: ignore[arg-type]

    assert ctx.request is not None
    url_str = str(ctx.request.url)
    assert url_str.endswith("/chat?foo=bar&baz=qux")
    assert ctx.request.content == body
