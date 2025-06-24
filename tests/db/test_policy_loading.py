import datetime
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Awaitable, Callable, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import httpx
import pytest
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.db.control_policy_crud import load_policy_from_db
from luthien_control.db.exceptions import LuthienDBOperationError, LuthienDBQueryError
from luthien_control.db.sqlmodel_models import ClientApiKey
from luthien_control.db.sqlmodel_models import ControlPolicy as ControlPolicyModel
from luthien_control.new_control_policy.control_policy import ControlPolicy
from luthien_control.new_control_policy.exceptions import PolicyLoadError
from luthien_control.new_control_policy.serialization import SerializedPolicy
from luthien_control.settings import Settings
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio
ApiKeyLookupFunc = Callable[[AsyncSession, str], Awaitable[Optional["ClientApiKey"]]]


@pytest.fixture
def load_db_mock_settings() -> Settings:
    """Provides mock Settings for load_policy_from_db tests."""
    return MagicMock(spec=Settings)


@pytest.fixture
def load_db_mock_http_client() -> httpx.AsyncClient:
    """Provides mock AsyncClient for load_policy_from_db tests."""
    return AsyncMock(spec=httpx.AsyncClient)


@pytest.fixture
def load_db_mock_api_key_lookup() -> ApiKeyLookupFunc:
    """Provides mock ApiKeyLookupFunc for load_policy_from_db tests."""

    async def _mock_lookup(session: AsyncSession, key: str) -> ClientApiKey | None:
        if key == "valid-key":
            return ClientApiKey(key_value="valid-key", name="Test Key", is_active=True)
        return None

    return _mock_lookup


@pytest.fixture
def load_db_dependencies(
    load_db_mock_settings,
    load_db_mock_http_client,
    load_db_mock_api_key_lookup,
):
    """Bundles mock dependencies for load_policy_from_db tests."""
    return {
        "settings": load_db_mock_settings,
        "http_client": load_db_mock_http_client,
        "api_key_lookup": load_db_mock_api_key_lookup,
        "db_session": Mock(spec=AsyncSession),
    }


def create_mock_policy_model(
    *,  # Enforce keyword-only arguments for clarity
    id: int = 1,
    name: str = "test_policy",
    type: str = "mock_type",  # Add type field with default
    config: dict | None = None,
    is_active: bool = True,
    description: str | None = "A test policy",
    created_at: datetime.datetime | None = None,
    updated_at: datetime.datetime | None = None,
) -> ControlPolicyModel:
    """Helper to create mock ControlPolicy model instances for testing."""
    if config is None:
        config = {"timeout": 30}
    now = datetime.datetime.now(datetime.UTC)
    return ControlPolicyModel(
        id=id,
        name=name,
        type=type,  # Pass type to constructor
        config=config,
        is_active=is_active,
        description=description,
        created_at=created_at or now,
        updated_at=updated_at or now,
    )


@patch("luthien_control.db.control_policy_crud.get_policy_by_name", new_callable=AsyncMock)
@patch("luthien_control.db.control_policy_crud.load_policy", new_callable=MagicMock)
async def test_load_policy_from_db_success(
    mock_load_policy: MagicMock,
    mock_get_policy_by_name: AsyncMock,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test successfully loading and instantiating a policy from DB config."""
    policy_name = "test_policy_success"
    mock_policy_config_model = create_mock_policy_model(name=policy_name)
    mock_get_policy_by_name.return_value = mock_policy_config_model

    mock_instantiated_policy = MagicMock(spec=ControlPolicy)
    mock_load_policy.return_value = mock_instantiated_policy

    loaded_policy = await load_policy_from_db(
        name=policy_name,
        container=mock_container,
    )

    mock_container.db_session_factory.assert_called_once()
    mock_get_policy_by_name.assert_awaited_once_with(mock_db_session, policy_name)

    expected_policy_data = SerializedPolicy(
        type=mock_policy_config_model.type,
        config=mock_policy_config_model.config,
    )
    mock_load_policy.assert_called_once_with(expected_policy_data)
    assert loaded_policy == mock_instantiated_policy


@patch("luthien_control.db.control_policy_crud.get_policy_by_name", new_callable=AsyncMock)
async def test_load_policy_from_db_not_found_patch_get(
    mock_get_policy_by_name: AsyncMock,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test LuthienDBQueryError using PATCHED get_policy_by_name raising exception."""
    policy_name = "non_existent_policy_patch"
    mock_get_policy_by_name.side_effect = LuthienDBQueryError(f"Policy with name '{policy_name}' not found")

    with pytest.raises(LuthienDBQueryError, match="not found"):
        await load_policy_from_db(
            name=policy_name,
            container=mock_container,
        )
    mock_container.db_session_factory.assert_called_once()
    mock_get_policy_by_name.assert_awaited_once_with(mock_db_session, policy_name)


# Use the in-memory async_session fixture from tests/db/conftest.py
async def test_load_policy_from_db_not_found_in_memory_db(
    async_session: AsyncSession,  # Use in-memory session
    mock_settings: Settings,  # Use mock settings
    mock_http_client: httpx.AsyncClient,  # Use mock client
):
    """Test LuthienDBQueryError using an in-memory DB where the policy doesn't exist."""
    policy_name = "non_existent_policy_real"

    # Create a simple factory for the provided in-memory session
    @asynccontextmanager
    async def session_factory() -> AsyncGenerator[AsyncSession, None]:
        yield async_session

    # Construct a container with mocks and the real session factory
    container = DependencyContainer(
        settings=mock_settings,
        http_client=mock_http_client,
        db_session_factory=session_factory,
    )

    # Since the DB is empty (function-scoped in-memory session),
    # get_policy_by_name inside load_policy_from_db will raise an exception.
    with pytest.raises(LuthienDBQueryError, match="not found"):
        await load_policy_from_db(
            name=policy_name,
            container=container,  # Pass the constructed container
        )


# Patch load_policy to simulate failure, use in-memory session
@patch(
    "luthien_control.db.control_policy_crud.load_policy",
    new_callable=MagicMock,
    side_effect=PolicyLoadError("Instantiation failed"),
)
async def test_load_policy_from_db_instantiation_fails_in_memory_db(
    mock_load_policy,
    async_session: AsyncSession,  # Use in-memory session
    mock_settings: Settings,  # Use mock settings
    mock_http_client: httpx.AsyncClient,  # Use mock client
):
    """Test LuthienDBOperationError when load_policy fails, using in-memory session."""
    policy_name = "instantiation_failure_policy"
    # Create the policy config in the in-memory DB first
    policy_to_create = create_mock_policy_model(name=policy_name)
    from luthien_control.db.control_policy_crud import save_policy_to_db

    created_policy = await save_policy_to_db(async_session, policy_to_create)
    assert created_policy is not None

    # Create a simple factory for the provided in-memory session
    @asynccontextmanager
    async def session_factory() -> AsyncGenerator[AsyncSession, None]:
        yield async_session

    # Construct a container with mocks and the real session factory
    container = DependencyContainer(
        settings=mock_settings,
        http_client=mock_http_client,
        db_session_factory=session_factory,
    )

    # Match the error raised by the mock's side_effect (wrapped in LuthienDBOperationError)
    with pytest.raises(LuthienDBOperationError, match="Failed to instantiate policy"):
        await load_policy_from_db(
            name=policy_name,
            container=container,  # Pass the constructed container
        )

    mock_load_policy.assert_called_once()  # Verify load_policy was called


@patch("luthien_control.db.control_policy_crud.get_policy_by_name", new_callable=AsyncMock)
@patch("luthien_control.db.control_policy_crud.load_policy", new_callable=MagicMock)
async def test_load_policy_from_db_loader_error(
    mock_load_policy: MagicMock,
    mock_get_policy_by_name: AsyncMock,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test LuthienDBOperationError if load_policy fails internally."""
    policy_name = "test_policy_loader_error"
    mock_policy_config_model = create_mock_policy_model(name=policy_name)
    mock_get_policy_by_name.return_value = mock_policy_config_model

    mock_load_policy.side_effect = PolicyLoadError("Mock loader failure")

    with pytest.raises(LuthienDBOperationError, match="Failed to instantiate policy"):
        await load_policy_from_db(
            name=policy_name,
            container=mock_container,
        )

    mock_container.db_session_factory.assert_called_once()
    mock_get_policy_by_name.assert_awaited_once_with(mock_db_session, policy_name)
    expected_policy_data = SerializedPolicy(
        type=mock_policy_config_model.type,
        config=mock_policy_config_model.config,
    )
    mock_load_policy.assert_called_once_with(expected_policy_data)
