import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import fastapi
import httpx
import pytest
from luthien_control.config.settings import Settings
from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.exceptions import ControlPolicyError
from luthien_control.core.transaction_context import TransactionContext
from luthien_control.proxy.orchestration import run_policy_flow

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

    # Explicitly define apply to return the context passed to it, accepting session
    async def apply_effect(context, session):
        # Simulate some action (optional)
        context.data["main_policy_called"] = True
        # Return a *new* context mock to avoid identity issues in assertions
        new_context = MagicMock(spec=TransactionContext)
        new_context.transaction_id = context.transaction_id
        new_context.data = context.data.copy()
        new_context.request = context.request
        new_context.response = None  # Explicitly set response to None
        return new_context

    policy_mock.apply = AsyncMock(side_effect=apply_effect)
    return policy_mock


@pytest.fixture
def mock_policy_raising_exception() -> AsyncMock:
    """Provides a single mock ControlPolicy that raises ControlPolicyError."""
    policy_mock = AsyncMock(spec=ControlPolicy)
    policy_mock.apply.side_effect = ControlPolicyError("Policy Failed!")
    return policy_mock


@pytest.fixture
def mock_builder() -> MagicMock:
    builder = MagicMock()
    # Store the response object to check identity against
    response_obj = fastapi.Response(content="built")
    builder.build_response = MagicMock(return_value=response_obj)
    # Add the expected object as an attribute for easier access in the test
    builder._expected_response = response_obj
    return builder


@patch("luthien_control.proxy.orchestration.uuid.uuid4")  # Patch uuid within orchestration module
async def test_run_policy_flow_successful(
    mock_uuid4: MagicMock,
    mock_request: MagicMock,
    mock_policy: AsyncMock,
    mock_builder: MagicMock,
    mock_dependencies: MagicMock,
):
    """
    Test Goal: Verify the happy path where context is initialized, the main
               policy runs successfully (using a session from container),
               and the response builder is invoked.
    """
    fixed_test_uuid = uuid.UUID("12345678-1234-5678-1234-567812345678")
    mock_uuid4.return_value = fixed_test_uuid
    # Mock final response from builder
    expected_final_response = MagicMock(spec=fastapi.Response)
    mock_builder.build_response.return_value = expected_final_response

    # Mock the session factory within the container
    mock_session = mock_dependencies.mock_session
    # Assume policy needs session
    mock_policy.apply.__code__ = MagicMock(co_varnames=("self", "context", "session"))

    # Call the orchestrator, passing the container
    response = await run_policy_flow(
        request=mock_request,
        main_policy=mock_policy,
        builder=mock_builder,
        dependencies=mock_dependencies,
    )

    # Assertions
    # 1. Context Initialization
    mock_request.body.assert_awaited_once()
    mock_uuid4.assert_called_once()
    # 2. Session Factory Usage
    mock_dependencies.db_session_factory.assert_called_once()
    mock_dependencies.db_session_factory.return_value.__aenter__.assert_awaited_once()
    # 3. Policy Application
    # Check policy was called with initial context and the session
    mock_policy.apply.assert_awaited_once()
    call_args, call_kwargs = mock_policy.apply.await_args
    assert isinstance(call_args[0], TransactionContext)  # Check first arg is context
    assert call_args[0].transaction_id == fixed_test_uuid
    assert call_kwargs.get("session") is mock_session  # Check session was passed
    # 4. Response Building
    mock_builder.build_response.assert_called_once()
    context_arg = mock_builder.build_response.call_args[0][0]
    assert isinstance(context_arg, TransactionContext)
    assert context_arg.transaction_id == fixed_test_uuid
    assert context_arg.data.get("main_policy_called") is True
    # 5. Final Response
    assert response is expected_final_response


@patch("luthien_control.proxy.orchestration.uuid.uuid4")  # Patch uuid within orchestration module
async def test_run_policy_flow_policy_exception(
    mock_uuid4: MagicMock,
    mock_request: MagicMock,
    mock_policy_raising_exception: AsyncMock,
    mock_builder: MagicMock,
    mock_dependencies: MagicMock,
):
    """
    Test Goal: Verify that if the main policy raises a ControlPolicyError,
               the exception is caught, the session context is exited,
               and the builder is called with the context state.
    """
    fixed_test_uuid = uuid.UUID("abcdefab-cdef-abcd-efab-cdefabcdefab")
    mock_uuid4.return_value = fixed_test_uuid
    # Mock the session factory and session
    mock_session = mock_dependencies.mock_session
    # Assume policy needs session
    mock_policy_raising_exception.apply.__code__ = MagicMock(co_varnames=("self", "context", "session"))

    # Mock final response from builder
    expected_error_response = MagicMock(spec=fastapi.Response)
    mock_builder.build_response.return_value = expected_error_response

    # Call the orchestrator, passing the container
    response = await run_policy_flow(
        request=mock_request,
        main_policy=mock_policy_raising_exception,
        builder=mock_builder,
        dependencies=mock_dependencies,
    )

    # Assertions
    # 1. Context Initialization & Session Start
    mock_request.body.assert_awaited_once()
    mock_uuid4.assert_called_once()
    mock_dependencies.db_session_factory.assert_called_once()
    mock_dependencies.db_session_factory.return_value.__aenter__.assert_awaited_once()
    # 2. Policy Application (raised exception)
    mock_policy_raising_exception.apply.assert_awaited_once()
    call_args, call_kwargs = mock_policy_raising_exception.apply.await_args
    assert isinstance(call_args[0], TransactionContext)
    assert call_kwargs.get("session") is mock_session
    # 3. Session Exit
    mock_dependencies.db_session_factory.return_value.__aexit__.assert_awaited_once()
    # 4. Response Building (called even after exception)
    # The context passed to the builder is the one *before* the exception handler modified it.
    assert mock_builder.build_response.call_count == 1
    context_arg = mock_builder.build_response.call_args[0][0]
    assert isinstance(context_arg, TransactionContext)
    assert context_arg.transaction_id == fixed_test_uuid
    # 5. Final Response
    assert response is expected_error_response


@patch("luthien_control.proxy.orchestration.uuid.uuid4")  # Patch uuid within orchestration module
async def test_run_policy_flow_unexpected_exception(
    mock_uuid4: MagicMock,
    mock_request: MagicMock,
    mock_policy: AsyncMock,
    mock_builder: MagicMock,
    mock_dependencies: MagicMock,
):
    """
    Test Goal: Verify that if the main policy raises an unexpected Exception,
               it's caught, logged, the builder is called, and a generic
               error response is returned.
    """
    fixed_test_uuid = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
    mock_uuid4.return_value = fixed_test_uuid
    # Mock the session factory and session
    mock_session = mock_dependencies.mock_session
    # Assume policy needs session
    mock_policy.apply.__code__ = MagicMock(co_varnames=("self", "context", "session"))

    # Simulate unexpected error during policy apply
    unexpected_error = ValueError("Something went very wrong")
    mock_policy.apply.side_effect = unexpected_error

    # Mock final response from builder (which should be called even on unexpected error)
    expected_generic_error_response = MagicMock(spec=fastapi.Response)
    mock_builder.build_response.return_value = expected_generic_error_response

    # Call the orchestrator and expect the response builder to still be called
    # The orchestrator should catch the unexpected error, log it, and proceed
    # to the builder.
    with patch("luthien_control.proxy.orchestration.logger") as mock_logger:
        # The orchestrator catches the exception internally and returns a response
        response = await run_policy_flow(
            request=mock_request,
            main_policy=mock_policy,
            builder=mock_builder,
            dependencies=mock_dependencies,
        )

    # Assertions
    # 1. Context Init, Session Start, Policy Apply (attempted)
    mock_request.body.assert_awaited_once()
    mock_uuid4.assert_called_once()
    mock_dependencies.db_session_factory.assert_called_once()
    mock_dependencies.db_session_factory.return_value.__aenter__.assert_awaited_once()
    mock_policy.apply.assert_awaited_once()  # Ensure the policy was called

    # 2. Session Exit (should still happen in finally block)
    mock_dependencies.db_session_factory.return_value.__aexit__.assert_awaited_once()

    # 3. Logging (Check the exception was logged)
    mock_logger.exception.assert_called_once()
    log_msg = mock_logger.exception.call_args[0][0]
    assert "Unhandled exception during policy flow" in log_msg
    assert str(fixed_test_uuid) in log_msg  # Check context info in log

    # 4. Response Building (ensure builder was called despite the internal exception)
    assert mock_builder.build_response.call_count == 1
    (context_arg,) = mock_builder.build_response.call_args.args  # Positional arg
    kwargs_arg = mock_builder.build_response.call_args.kwargs
    assert isinstance(context_arg, TransactionContext)
    assert context_arg.transaction_id == fixed_test_uuid
    assert kwargs_arg.get("exception") is None  # Default builder ignores non-ControlPolicyError

    # 5. Final Response (ensure the builder's response was returned)
    assert response is expected_generic_error_response


@patch("luthien_control.proxy.orchestration._initialize_context")  # Patch context init
async def test_run_policy_flow_context_init_exception(
    mock_init_context: MagicMock,
    mock_request: MagicMock,
    mock_policy: AsyncMock,
    mock_builder: MagicMock,
    mock_dependencies: MagicMock,
):
    """
    Test Goal: Verify that if an exception occurs during context initialization,
               it propagates and subsequent steps are skipped.
    """
    # Simulate failure during context initialization
    init_error = ValueError("Failed to initialize context")
    mock_init_context.side_effect = init_error

    # Expect the call to run_policy_flow to raise the underlying exception
    with pytest.raises(ValueError, match="Failed to initialize context"):
        await run_policy_flow(
            request=mock_request,
            main_policy=mock_policy,
            builder=mock_builder,
            dependencies=mock_dependencies,
        )

    # Assertions
    mock_init_context.assert_called_once()  # Ensure init was attempted
    mock_policy.apply.assert_not_awaited()  # Policy should not be called
    mock_builder.build_response.assert_not_called()  # Builder should not be called
    mock_dependencies.db_session_factory.assert_not_called()  # Session factory not called
