import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import fastapi
import httpx
import pytest
from fastapi import Response  # Import Response for direct creation
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession  # Import AsyncSession

from luthien_control.config.settings import Settings
from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.exceptions import ControlPolicyError

# Import DefaultResponseBuilder
from luthien_control.core.response_builder.default_builder import DefaultResponseBuilder
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

    # Explicitly define apply to return the context passed to it, accepting container and session
    async def apply_effect(context, container, session):
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
    # Update side effect to match new apply signature
    policy_mock.apply.side_effect = ControlPolicyError("Policy Failed!")
    return policy_mock


@pytest.fixture
def mock_session() -> AsyncMock:
    """Provides a mock AsyncSession."""
    return AsyncMock(spec=AsyncSession)


@patch("luthien_control.proxy.orchestration.uuid.uuid4")
@patch("luthien_control.proxy.orchestration.DefaultResponseBuilder")  # Patch the builder where it's used
async def test_run_policy_flow_successful(
    MockDefaultBuilder: MagicMock,  # Inject the patched class
    mock_uuid4: MagicMock,
    mock_request: MagicMock,
    mock_policy: AsyncMock,
    mock_dependencies: MagicMock,
    mock_session: AsyncMock,  # Add session fixture
):
    """
    Test Goal: Verify the happy path: context init, policy runs with container/session,
               and the default builder is invoked.
    """
    fixed_test_uuid = uuid.UUID("12345678-1234-5678-1234-567812345678")
    mock_uuid4.return_value = fixed_test_uuid

    # Configure the mocked DefaultResponseBuilder instance
    mock_builder_instance = MockDefaultBuilder.return_value
    expected_final_response = Response(content=b"built response")
    mock_builder_instance.build_response.return_value = expected_final_response

    # Call the orchestrator, passing container and session
    response = await run_policy_flow(
        request=mock_request,
        main_policy=mock_policy,
        dependencies=mock_dependencies,
        session=mock_session,  # Pass session
    )

    # Assertions
    # 1. Context Initialization
    mock_request.body.assert_awaited_once()
    mock_uuid4.assert_called_once()
    # 2. Policy Application
    # Check policy was called with context, container, and session
    mock_policy.apply.assert_awaited_once()
    call_args, call_kwargs = mock_policy.apply.await_args
    assert isinstance(call_args[0], TransactionContext)
    assert call_args[0].transaction_id == fixed_test_uuid
    assert call_kwargs.get("container") is mock_dependencies  # Check container
    assert call_kwargs.get("session") is mock_session  # Check session
    # 3. Response Building (using the internal DefaultResponseBuilder instance)
    MockDefaultBuilder.assert_called_once_with()  # Check builder was instantiated
    mock_builder_instance.build_response.assert_called_once()
    context_arg = mock_builder_instance.build_response.call_args[0][0]
    assert isinstance(context_arg, TransactionContext)
    assert context_arg.transaction_id == fixed_test_uuid
    assert context_arg.data.get("main_policy_called") is True
    # 4. Final Response
    assert response is expected_final_response


@patch("luthien_control.proxy.orchestration.uuid.uuid4")
@patch("luthien_control.proxy.orchestration.DefaultResponseBuilder")  # Patch the builder where it's used
async def test_run_policy_flow_policy_exception(
    MockDefaultBuilder: MagicMock,
    mock_uuid4: MagicMock,
    mock_request: MagicMock,
    mock_policy_raising_exception: AsyncMock,
    mock_dependencies: MagicMock,
    mock_session: AsyncMock,  # Add session fixture
):
    """
    Test Goal: Verify that if the policy raises ControlPolicyError, the exception
               is caught, and the builder is called with the context state.
    """
    fixed_test_uuid = uuid.UUID("abcdefab-cdef-abcd-efab-cdefabcdefab")
    mock_uuid4.return_value = fixed_test_uuid

    # Configure the mocked DefaultResponseBuilder instance
    mock_builder_instance = MockDefaultBuilder.return_value
    expected_error_response = Response(content=b"error response")
    mock_builder_instance.build_response.return_value = expected_error_response

    # Call the orchestrator
    response = await run_policy_flow(
        request=mock_request,
        main_policy=mock_policy_raising_exception,
        dependencies=mock_dependencies,
        session=mock_session,  # Pass session
    )

    # Assertions
    # 1. Context Initialization
    mock_request.body.assert_awaited_once()
    mock_uuid4.assert_called_once()
    # 2. Policy Application (raised exception)
    mock_policy_raising_exception.apply.assert_awaited_once()
    call_args, call_kwargs = mock_policy_raising_exception.apply.await_args
    assert isinstance(call_args[0], TransactionContext)
    assert call_kwargs.get("container") is mock_dependencies  # Check container
    assert call_kwargs.get("session") is mock_session  # Check session
    # 3. Response Building (called even after exception)
    MockDefaultBuilder.assert_called_once_with()  # Check builder was instantiated
    mock_builder_instance.build_response.assert_called_once()
    context_arg = mock_builder_instance.build_response.call_args[0][0]
    assert isinstance(context_arg, TransactionContext)
    assert context_arg.transaction_id == fixed_test_uuid
    # 4. Final Response
    assert response is expected_error_response


@patch("luthien_control.proxy.orchestration.uuid.uuid4")
@patch("luthien_control.proxy.orchestration.DefaultResponseBuilder")  # Patch the builder
@patch("luthien_control.proxy.orchestration.logger")  # Patch logger
async def test_run_policy_flow_unexpected_exception(
    mock_logger: MagicMock,
    MockDefaultBuilder: MagicMock,
    mock_uuid4: MagicMock,
    mock_request: MagicMock,
    mock_policy: AsyncMock,  # Use regular mock policy
    mock_dependencies: MagicMock,
    mock_session: AsyncMock,  # Add session fixture
):
    """
    Test Goal: Verify unexpected Exception is caught, logged, builder called,
               and error response returned.
    """
    fixed_test_uuid = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
    mock_uuid4.return_value = fixed_test_uuid

    # Simulate unexpected error during policy apply
    unexpected_error = ValueError("Something went very wrong")
    mock_policy.apply.side_effect = unexpected_error

    # Configure the mocked DefaultResponseBuilder instance
    mock_builder_instance = MockDefaultBuilder.return_value
    expected_generic_error_response = Response(content=b"generic error")
    mock_builder_instance.build_response.return_value = expected_generic_error_response

    # Call the orchestrator
    response = await run_policy_flow(
        request=mock_request,
        main_policy=mock_policy,
        dependencies=mock_dependencies,
        session=mock_session,  # Pass session
    )

    # Assertions
    # 1. Context Init, Policy Apply (attempted)
    mock_request.body.assert_awaited_once()
    mock_uuid4.assert_called_once()
    mock_policy.apply.assert_awaited_once()  # Ensure the policy was called
    # Check args passed to policy apply
    call_args, call_kwargs = mock_policy.apply.await_args
    assert isinstance(call_args[0], TransactionContext)
    assert call_kwargs.get("container") is mock_dependencies
    assert call_kwargs.get("session") is mock_session

    # 2. Logging (Check the exception was logged)
    mock_logger.exception.assert_called_once()
    log_message = mock_logger.exception.call_args[0][0]
    assert f"[{fixed_test_uuid}] Unhandled exception during policy flow:" in log_message

    # 3. Response Building (using internal builder)
    MockDefaultBuilder.assert_called_once_with()
    mock_builder_instance.build_response.assert_called_once()
    context_arg = mock_builder_instance.build_response.call_args[0][0]
    assert isinstance(context_arg, TransactionContext)

    # 4. Final Response
    assert response is expected_generic_error_response


# Test for exception during response building (remains largely the same, uses internal builder)
@patch("luthien_control.proxy.orchestration.uuid.uuid4")
@patch("luthien_control.proxy.orchestration.DefaultResponseBuilder")  # Patch builder
@patch("luthien_control.proxy.orchestration.logger")  # Patch logger
@patch("luthien_control.proxy.orchestration.JSONResponse")  # Patch JSONResponse fallback
async def test_run_policy_flow_unexpected_exception_during_build(
    MockJSONResponse: MagicMock,
    mock_logger: MagicMock,
    MockDefaultBuilder: MagicMock,
    mock_uuid4: MagicMock,
    mock_request: MagicMock,
    mock_policy_raising_exception: AsyncMock,  # Policy raises known error
    mock_dependencies: MagicMock,
    mock_session: AsyncMock,  # Add session
):
    """
    Test Goal: Verify exception during builder.build_response is caught,
               logged, and a fallback JSONResponse is returned.
    """
    fixed_test_uuid = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
    mock_uuid4.return_value = fixed_test_uuid

    # Simulate exception *during* build_response call
    build_exception = RuntimeError("Builder failed!")
    mock_builder_instance = MockDefaultBuilder.return_value
    mock_builder_instance.build_response.side_effect = build_exception

    # Mock the fallback JSONResponse
    expected_fallback_response = MagicMock(spec=JSONResponse)
    MockJSONResponse.return_value = expected_fallback_response

    # Call the orchestrator (policy raises ControlPolicyError, triggers builder)
    response = await run_policy_flow(
        request=mock_request,
        main_policy=mock_policy_raising_exception,
        dependencies=mock_dependencies,
        session=mock_session,  # Pass session
    )

    # Assertions
    # 1. Context Init, Policy Apply
    mock_request.body.assert_awaited_once()
    mock_uuid4.assert_called_once()
    mock_policy_raising_exception.apply.assert_awaited_once()

    # 2. Logging (Check builder exception was logged)
    mock_logger.exception.assert_called_once()
    log_message = mock_logger.exception.call_args[0][0]
    assert f"[{fixed_test_uuid}] Exception occurred *during* error response building:" in log_message

    # 3. Response Building Attempt (using internal builder)
    MockDefaultBuilder.assert_called_once_with()
    mock_builder_instance.build_response.assert_called_once()  # Builder was called

    # 4. Fallback JSONResponse Creation
    MockJSONResponse.assert_called_once()
    kwargs = MockJSONResponse.call_args[1]
    assert kwargs["status_code"] == 500
    assert "content" in kwargs
    assert "detail" in kwargs["content"]
    assert str(fixed_test_uuid) in kwargs["content"]["detail"]
    assert "Builder failed!" in kwargs["content"]["detail"]
    assert "Policy Failed!" in kwargs["content"]["detail"]  # Original policy error included

    # 5. Final Response (is the fallback)
    assert response is expected_fallback_response


@patch("luthien_control.proxy.orchestration._initialize_context")
@patch("luthien_control.proxy.orchestration.DefaultResponseBuilder")
@patch("luthien_control.proxy.orchestration.logger")
@patch("luthien_control.proxy.orchestration.JSONResponse")
async def test_run_policy_flow_context_init_exception(
    MockJSONResponse: MagicMock,
    mock_logger: MagicMock,
    MockDefaultBuilder: MagicMock,
    mock_init_context: MagicMock,
    mock_request: MagicMock,
    mock_policy: AsyncMock,
    mock_dependencies: MagicMock,
    mock_session: AsyncMock,  # Add session
):
    """
    Test Goal: Verify exception during context init is caught, logged,
               and a fallback JSONResponse is returned.
    """
    init_exception = ValueError("Context creation failed!")
    mock_init_context.side_effect = init_exception

    # Mock the fallback JSONResponse
    expected_fallback_response = MagicMock(spec=JSONResponse)
    MockJSONResponse.return_value = expected_fallback_response

    # Call the orchestrator
    response = await run_policy_flow(
        request=mock_request,
        main_policy=mock_policy,
        dependencies=mock_dependencies,
        session=mock_session,  # Pass session
    )

    # Assertions
    # 1. Context Init Attempt
    mock_request.body.assert_awaited_once()
    mock_init_context.assert_called_once()
    # 2. Policy Apply NOT called
    mock_policy.apply.assert_not_called()
    # 3. Builder NOT instantiated or called
    MockDefaultBuilder.assert_not_called()
    # 4. Logging (Check init exception was logged)
    mock_logger.exception.assert_called_once()
    log_message = mock_logger.exception.call_args[0][0]
    assert "Unhandled exception during policy flow:" in log_message
    assert "Context creation failed!" in str(mock_logger.exception.call_args[0][1])
    # 5. Fallback JSONResponse Creation
    MockJSONResponse.assert_called_once()
    kwargs = MockJSONResponse.call_args[1]
    assert kwargs["status_code"] == 500
    assert "content" in kwargs
    assert "detail" in kwargs["content"]
    assert "Context creation failed!" in kwargs["content"]["detail"]
    # Transaction ID might not be available if context init failed early
    assert "transaction_id" not in kwargs["content"] or kwargs["content"]["transaction_id"] is None

    # 6. Final Response (is the fallback)
    assert response is expected_fallback_response
