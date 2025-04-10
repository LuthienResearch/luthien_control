import inspect
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import fastapi
import httpx
import pytest
from luthien_control.config.settings import Settings
from luthien_control.control_policy.exceptions import ControlPolicyError
from luthien_control.control_policy.initialize_context import InitializeContextPolicy
from luthien_control.control_policy.interface import ControlPolicy
from luthien_control.core.context import TransactionContext
from luthien_control.proxy.orchestration import run_policy_flow

# Mark all tests in this module as async
pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_request() -> MagicMock:
    request = MagicMock(spec=fastapi.Request)
    request.scope = {"type": "http", "method": "GET", "path": "/test"}
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

    # Explicitly define apply to return the context passed to it
    async def apply_effect(context):
        # Simulate some action (optional)
        context.data["main_policy_called"] = True
        return context

    policy_mock.apply = AsyncMock(side_effect=apply_effect)
    return policy_mock


@pytest.fixture
def mock_policy_raising_exception() -> AsyncMock:
    """Provides a single mock ControlPolicy that raises ControlPolicyError."""
    policy_mock = AsyncMock(spec=ControlPolicy)
    policy_mock.apply.side_effect = ControlPolicyError("Policy Failed!")
    return policy_mock


@pytest.fixture
def mock_initial_policy_exception() -> AsyncMock:
    """Fixture for the initial policy that raises an exception."""
    policy = AsyncMock(spec=InitializeContextPolicy)
    policy.apply = AsyncMock(side_effect=ValueError("Initial Policy Error"))
    return policy


@patch("uuid.uuid4")
async def test_run_policy_flow_successful(
    mock_uuid4: MagicMock,
    mock_request: MagicMock,
    mock_policy: AsyncMock,
    mock_builder: MagicMock,
    mock_settings: MagicMock,
    mock_http_client: AsyncMock,
    mock_initial_policy: AsyncMock,
):
    """Test the successful execution of the policy flow."""
    fixed_test_uuid = uuid.UUID("12345678-1234-5678-1234-567812345678")
    mock_uuid4.return_value = fixed_test_uuid

    # Call the orchestrator
    response = await run_policy_flow(
        request=mock_request,
        main_policy=mock_policy,
        builder=mock_builder,
        settings=mock_settings,
        http_client=mock_http_client,
        initial_context_policy=mock_initial_policy,
    )

    # Assertions
    mock_uuid4.assert_called_once()

    # Check initial policy call and capture the context passed to it
    mock_initial_policy.apply.assert_awaited_once()
    initial_call_args = mock_initial_policy.apply.await_args
    context_passed_to_initial = initial_call_args[0][0]  # The context object
    request_passed_to_initial = initial_call_args[1]["fastapi_request"]  # The request kwarg

    assert isinstance(context_passed_to_initial, TransactionContext)
    assert context_passed_to_initial.transaction_id == fixed_test_uuid
    assert request_passed_to_initial is mock_request

    # Verify the side effect of the initial policy happened (context was modified)
    context_after_initial = await mock_initial_policy.apply.side_effect(
        context_passed_to_initial, request_passed_to_initial
    )
    assert context_after_initial.data.get("initialized") is True
    assert context_after_initial.fastapi_request is mock_request

    # Check that the main policy was called with the context after initialization
    mock_policy.apply.assert_awaited_once_with(context_after_initial)
    context_after_main_policy = await mock_policy.apply.side_effect(context_after_initial)

    # Need to await the side effect call if it's async
    if inspect.iscoroutinefunction(mock_policy.apply.side_effect):
        context_after_main_policy = await mock_policy.apply.side_effect(context_after_initial)
    else:
        context_after_main_policy = mock_policy.apply.side_effect(context_after_initial)

    # Check the side effect of the main policy
    assert context_after_main_policy.data.get("main_policy_called") is True

    # Check that the builder was called with the context after the last policy ran
    mock_builder.build_response.assert_called_once_with(context_after_main_policy)

    # Assert the response matches the builder's output
    assert response is mock_builder.build_response.return_value


@patch("uuid.uuid4")
async def test_run_policy_flow_policy_exception(
    mock_uuid4: MagicMock,
    mock_request: MagicMock,
    mock_policy_raising_exception: AsyncMock,
    mock_builder: MagicMock,
    mock_settings: MagicMock,
    mock_http_client: AsyncMock,
    mock_initial_policy: AsyncMock,
):
    """Test handling of exceptions raised by a policy during execution."""
    fixed_test_uuid = uuid.UUID("abcdefab-cdef-abcd-efab-cdefabcdefab")
    mock_uuid4.return_value = fixed_test_uuid

    # Call the orchestrator
    response = await run_policy_flow(
        request=mock_request,
        main_policy=mock_policy_raising_exception,
        builder=mock_builder,
        settings=mock_settings,
        http_client=mock_http_client,
        initial_context_policy=mock_initial_policy,
    )

    # Assertions
    mock_uuid4.assert_called_once()
    mock_initial_policy.apply.assert_awaited_once()
    # Capture context after successful initial policy call
    context_after_initial = await mock_initial_policy.apply.side_effect(
        mock_initial_policy.apply.await_args[0][0], mock_initial_policy.apply.await_args[1]["fastapi_request"]
    )  # Get context state after init

    # Verify it has the expected state after initial policy side effect ran
    assert context_after_initial.data.get("initialized") is True

    # Check that the failing policy was called with the context from the initial policy
    mock_policy_raising_exception.apply.assert_awaited_once_with(context_after_initial)

    # Check builder was called with the context *after* initial policy finished
    # In case of ControlPolicyError, the builder is called with the context state *before* the exception
    mock_builder.build_response.assert_called_once_with(context_after_initial)

    # Check final response is the one from the builder
    assert response is mock_builder.build_response.return_value


@patch("uuid.uuid4")
async def test_run_policy_flow_initial_policy_exception(
    mock_uuid4: MagicMock,
    mock_request: MagicMock,
    mock_policy: AsyncMock,
    mock_builder: MagicMock,
    mock_settings: MagicMock,
    mock_http_client: AsyncMock,
    mock_initial_policy_exception: AsyncMock,
):
    """Test handling of exceptions raised by the initial context policy."""
    fixed_test_uuid = uuid.UUID("aaaaabbb-bbbb-cccc-dddd-eeeeefffff00")
    mock_uuid4.return_value = fixed_test_uuid

    # Configure the initial policy mock to raise an exception
    mock_initial_policy_exception.apply.side_effect = ValueError("Initial Policy Error")

    # Expect the call to run_policy_flow to raise the exception from the initial policy
    with pytest.raises(ValueError, match="Initial Policy Error"):
        await run_policy_flow(
            request=mock_request,
            main_policy=mock_policy,
            builder=mock_builder,
            settings=mock_settings,
            http_client=mock_http_client,
            initial_context_policy=mock_initial_policy_exception,
        )

    # Assertions
    mock_uuid4.assert_called_once()

    # Check initial policy was called (and raised)
    mock_initial_policy_exception.apply.assert_awaited_once()
    initial_call_args = mock_initial_policy_exception.apply.await_args
    context_at_start = initial_call_args[0][0]
    assert isinstance(context_at_start, TransactionContext)
    assert context_at_start.transaction_id == fixed_test_uuid
    assert initial_call_args[1]["fastapi_request"] == mock_request

    # Check that subsequent policies were NOT called
    mock_policy.apply.assert_not_awaited()

    # Check that the builder was NOT called
    mock_builder.build_response.assert_not_called()
