import inspect
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
    request.query_params = MagicMock(spec=fastapi.datastructures.QueryParams) # Use MagicMock for query_params
    request.headers = MagicMock(spec=fastapi.datastructures.Headers)
    request.headers.raw = [] # httpx.Request needs list of tuples
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
def mock_builder() -> MagicMock:
    builder = MagicMock()
    # Store the response object to check identity against
    response_obj = fastapi.Response(content="built")
    builder.build_response = MagicMock(return_value=response_obj)
    # Add the expected object as an attribute for easier access in the test
    builder._expected_response = response_obj
    return builder


@patch("luthien_control.proxy.orchestration.uuid.uuid4") # Patch uuid within orchestration module
async def test_run_policy_flow_successful(
    mock_uuid4: MagicMock,
    mock_request: MagicMock,
    mock_policy: AsyncMock,
    mock_builder: MagicMock,
    mock_settings: MagicMock, # Use actual fixture name
    mock_http_client: AsyncMock, # Use actual fixture name
):
    """
    Test Goal: Verify the happy path where context is initialized, the main
               policy runs successfully, and the response builder is invoked.
    """
    fixed_test_uuid = uuid.UUID("12345678-1234-5678-1234-567812345678")
    mock_uuid4.return_value = fixed_test_uuid

    # Call the orchestrator
    response = await run_policy_flow(
        request=mock_request,
        main_policy=mock_policy,
        builder=mock_builder,
        settings=mock_settings,
        http_client=mock_http_client,
    )

    # --- Assertions ---
    # 1. Context Initialization Check (Implicit via main_policy call)
    mock_uuid4.assert_called_once()
    mock_request.body.assert_awaited_once() # Ensure body was read

    # 2. Main Policy Call Check
    mock_policy.apply.assert_awaited_once()
    context_passed_to_main = mock_policy.apply.await_args[0][0]

    # Verify context state *before* main policy ran
    assert isinstance(context_passed_to_main, TransactionContext)
    assert context_passed_to_main.transaction_id == fixed_test_uuid
    assert context_passed_to_main.response is None
    assert context_passed_to_main.request is not None
    assert context_passed_to_main.request.method == mock_request.method
    assert context_passed_to_main.request.url == mock_request.path_params["full_path"]
    # Ensure content was correctly passed
    # Read the request content within the test context for comparison
    request_content = await context_passed_to_main.request.aread()
    assert request_content == TEST_REQUEST_BODY


    # Simulate the effect of the main policy's side effect for subsequent checks
    # We need to await the side effect call if it's async
    if inspect.iscoroutinefunction(mock_policy.apply.side_effect):
        context_after_main_policy = await mock_policy.apply.side_effect(context_passed_to_main)
    else:
        context_after_main_policy = mock_policy.apply.side_effect(context_passed_to_main)

    # Check the side effect of the main policy
    assert context_after_main_policy.data.get("main_policy_called") is True

    # 3. Builder Call Check
    mock_builder.build_response.assert_called_once_with(context_after_main_policy)

    # 4. Final Response Check
    # Retrieve the specific object instance created in the fixture
    expected_response_object = mock_builder._expected_response
    assert response is expected_response_object


@patch("luthien_control.proxy.orchestration.uuid.uuid4") # Patch uuid within orchestration module
async def test_run_policy_flow_policy_exception(
    mock_uuid4: MagicMock,
    mock_request: MagicMock,
    mock_policy_raising_exception: AsyncMock,
    mock_builder: MagicMock,
    mock_settings: MagicMock, # Use actual fixture name
    mock_http_client: AsyncMock, # Use actual fixture name
):
    """
    Test Goal: Verify that if the main policy raises a ControlPolicyError,
               the exception is caught, and the builder is called with the
               context state *before* the exception occurred.
    """
    fixed_test_uuid = uuid.UUID("abcdefab-cdef-abcd-efab-cdefabcdefab")
    mock_uuid4.return_value = fixed_test_uuid

    # Call the orchestrator
    response = await run_policy_flow(
        request=mock_request,
        main_policy=mock_policy_raising_exception,
        builder=mock_builder,
        settings=mock_settings,
        http_client=mock_http_client,
    )

    # --- Assertions ---
    # 1. Context Initialization Check
    mock_uuid4.assert_called_once()
    mock_request.body.assert_awaited_once()

    # 2. Failing Policy Call Check
    mock_policy_raising_exception.apply.assert_awaited_once()
    context_before_exception = mock_policy_raising_exception.apply.await_args[0][0]

    # Verify context state was correctly initialized before the exception
    assert isinstance(context_before_exception, TransactionContext)
    assert context_before_exception.transaction_id == fixed_test_uuid
    assert context_before_exception.request is not None
    request_content = await context_before_exception.request.aread()
    assert request_content == TEST_REQUEST_BODY


    # 3. Builder Call Check
    # Crucially, the builder is called with the context *before* the exception
    # was raised and added to it by the `except ControlPolicyError` block.
    mock_builder.build_response.assert_called_once_with(context_before_exception)

    # 4. Final Response Check
    # Retrieve the specific object instance created in the fixture
    expected_response_object = mock_builder._expected_response
    assert response is expected_response_object


@patch("luthien_control.proxy.orchestration.uuid.uuid4") # Patch uuid within orchestration module
async def test_run_policy_flow_context_init_exception(
    mock_uuid4: MagicMock,
    mock_request: MagicMock,
    mock_policy: AsyncMock, # Use the regular policy mock
    mock_builder: MagicMock,
    mock_settings: MagicMock, # Use actual fixture name
    mock_http_client: AsyncMock, # Use actual fixture name
):
    """
    Test Goal: Verify that if an exception occurs during context initialization
               (specifically, reading the request body), the exception propagates
               and subsequent steps (policy application, response building) are skipped.
    """
    # Simulate failure during request body reading
    mock_request.body = AsyncMock(side_effect=ValueError("Failed to read body"))

    # Expect the call to run_policy_flow to raise the underlying exception
    with pytest.raises(ValueError, match="Failed to read body"):
        await run_policy_flow(
            request=mock_request,
            main_policy=mock_policy,
            builder=mock_builder,
            settings=mock_settings,
            http_client=mock_http_client,
        )

    # --- Assertions ---
    # 1. Body Reading Attempted (and failed)
    mock_request.body.assert_awaited_once()

    # 2. UUID Generation NOT Called (occurs after body reading)
    mock_uuid4.assert_not_called()

    # 3. Main Policy NOT Called
    mock_policy.apply.assert_not_awaited()

    # 4. Builder NOT Called
    mock_builder.build_response.assert_not_called()
