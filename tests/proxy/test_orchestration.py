import pytest
from unittest.mock import AsyncMock, MagicMock, call, patch
import uuid

import fastapi
import httpx

from luthien_control.config.settings import Settings
from luthien_control.control_policy.initialize_context import InitializeContextPolicy
from luthien_control.control_policy.interface import ControlPolicy
from luthien_control.core.context import TransactionContext
from luthien_control.core.response_builder.interface import ResponseBuilder
from luthien_control.proxy.orchestration import run_policy_flow

# Mark all tests in this module as async
pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_request() -> MagicMock:
    return MagicMock(spec=fastapi.Request)


@pytest.fixture
def mock_settings() -> MagicMock:
    return MagicMock(spec=Settings)


@pytest.fixture
def mock_http_client() -> AsyncMock:
    return AsyncMock(spec=httpx.AsyncClient)


@pytest.fixture
def mock_initial_policy() -> AsyncMock:
    policy = AsyncMock(spec=InitializeContextPolicy)

    # Simulate the policy adding request data to the context
    async def apply_effect(context, **kwargs):
        context.request = {"mock_key": "mock_value"}  # Simulate adding request data
        return context

    policy.apply = AsyncMock(side_effect=apply_effect)
    return policy


@pytest.fixture
def mock_policies() -> list[AsyncMock]:
    policies = [
        AsyncMock(spec=ControlPolicy),
        AsyncMock(spec=ControlPolicy),
    ]

    # Simulate policies modifying context sequentially
    async def apply_effect_1(context):
        context.policy_1_called = True
        return context

    async def apply_effect_2(context):
        context.policy_2_called = True
        return context

    policies[0].apply = AsyncMock(side_effect=apply_effect_1)
    policies[1].apply = AsyncMock(side_effect=apply_effect_2)
    return policies


@pytest.fixture
def mock_builder() -> MagicMock:
    builder = MagicMock(spec=ResponseBuilder)
    builder.build_response.return_value = MagicMock(spec=fastapi.Response)
    return builder


@pytest.fixture
def mock_policies_with_exception() -> list[AsyncMock]:
    """Fixture for policies where the first one raises an exception."""
    policies = [
        AsyncMock(spec=ControlPolicy),
        AsyncMock(spec=ControlPolicy),
    ]
    policies[0].apply = AsyncMock(side_effect=ValueError("Policy Error"))
    policies[1].apply = AsyncMock()  # This should not be called
    return policies


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
    mock_policies: list[AsyncMock],
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
        policies=mock_policies,
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
    context_at_start = initial_call_args[0][0]
    assert isinstance(context_at_start, TransactionContext)
    assert context_at_start.transaction_id == fixed_test_uuid
    assert initial_call_args[1]["fastapi_request"] == mock_request

    # Check subsequent policy calls - use call_args to verify context passing
    # Assert policy 1 was called with the context returned by initial_policy's side_effect
    mock_policies[0].apply.assert_awaited_once()
    context_passed_to_policy1 = mock_policies[0].apply.await_args[0][0]
    assert context_passed_to_policy1.transaction_id == fixed_test_uuid
    assert hasattr(context_passed_to_policy1, "request")  # Initial policy should have added this
    assert context_passed_to_policy1.request == {"mock_key": "mock_value"}

    # Assert policy 2 was called with the context returned by policy 1's side_effect
    mock_policies[1].apply.assert_awaited_once()
    context_passed_to_policy2 = mock_policies[1].apply.await_args[0][0]
    assert context_passed_to_policy2.transaction_id == fixed_test_uuid
    assert context_passed_to_policy2.policy_1_called is True  # Policy 1 should have modified this

    # Check builder call with the final context from policy 2's side_effect
    mock_builder.build_response.assert_called_once()
    context_passed_to_builder = mock_builder.build_response.call_args[0][0]
    assert context_passed_to_builder.transaction_id == fixed_test_uuid
    assert context_passed_to_builder.policy_2_called is True  # Policy 2 should have modified this

    # Check final response
    assert response == mock_builder.build_response.return_value


@patch("uuid.uuid4")
async def test_run_policy_flow_policy_exception(
    mock_uuid4: MagicMock,
    mock_request: MagicMock,
    mock_policies_with_exception: list[AsyncMock],
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
        policies=mock_policies_with_exception,
        builder=mock_builder,
        settings=mock_settings,
        http_client=mock_http_client,
        initial_context_policy=mock_initial_policy,
    )

    # Assertions
    mock_uuid4.assert_called_once()
    mock_initial_policy.apply.assert_awaited_once()
    # Capture context after successful initial policy call
    context_after_initial = mock_initial_policy.apply.await_args[0][0]
    # Verify it has the expected state after initial policy side effect ran
    assert hasattr(context_after_initial, "request")
    assert context_after_initial.request == {"mock_key": "mock_value"}

    # Check that the failing policy was called with the context from the initial policy
    mock_policies_with_exception[0].apply.assert_awaited_once_with(context_after_initial)

    # Check that the subsequent policy was NOT called
    mock_policies_with_exception[1].apply.assert_not_awaited()

    # Check that the builder WAS called with the context *before* the exception
    # (i.e., the state after the initial policy succeeded)
    mock_builder.build_response.assert_called_once_with(context_after_initial)

    # Check final response is the one from the builder
    assert response == mock_builder.build_response.return_value


@patch("uuid.uuid4")
async def test_run_policy_flow_initial_policy_exception(
    mock_uuid4: MagicMock,
    mock_request: MagicMock,
    mock_policies: list[AsyncMock],  # Use standard policies, they shouldn't be called
    mock_builder: MagicMock,
    mock_settings: MagicMock,
    mock_http_client: AsyncMock,
    mock_initial_policy_exception: AsyncMock,
):
    """Test handling of exceptions raised by the initial context policy."""
    fixed_test_uuid = uuid.UUID("aaaaabbb-bbbb-cccc-dddd-eeeeefffff00")
    mock_uuid4.return_value = fixed_test_uuid

    # Call the orchestrator
    response = await run_policy_flow(
        request=mock_request,
        policies=mock_policies,
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
    mock_policies[0].apply.assert_not_awaited()
    mock_policies[1].apply.assert_not_awaited()

    # Check that the builder WAS called with the context created *before* the initial policy call
    builder_call_args = mock_builder.build_response.call_args
    assert builder_call_args is not None, "Builder was not called"
    context_passed_to_builder = builder_call_args[0][0]
    assert isinstance(context_passed_to_builder, TransactionContext)
    assert context_passed_to_builder.transaction_id == fixed_test_uuid
    # --- Assertion fixed --- Check the request attribute is None
    assert context_passed_to_builder.request is None  # Initial policy failed before setting it

    # Check final response is the one from the builder
    assert response == mock_builder.build_response.return_value
