import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import httpx
import pytest
from luthien_control.config.settings import Settings
from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.exceptions import PolicyLoadError
from luthien_control.db.control_policy_crud import load_policy_from_db
from luthien_control.db.sqlmodel_models import ClientApiKey
from luthien_control.db.sqlmodel_models import ControlPolicy as ControlPolicyModel
from luthien_control.dependencies import ApiKeyLookupFunc
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio


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
    policy_class_path: str = "luthien_control.tests.db.mock_policies.MockSimplePolicy",
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
        policy_class_path=policy_class_path,
        config=config,
        is_active=is_active,
        description=description,
        created_at=created_at or now,
        updated_at=updated_at or now,
    )


# Mock the database fetch function used *within* load_policy_from_db
@patch("luthien_control.db.control_policy_crud.get_policy_by_name", new_callable=AsyncMock)
# Mock the new policy loading function (which is synchronous)
@patch("luthien_control.db.control_policy_crud.load_policy", new_callable=MagicMock)
async def test_load_policy_from_db_success(
    mock_load_policy,
    mock_get_policy_by_name,  # Renamed from mock_get_config for clarity
    load_db_dependencies,
    mock_db_session: AsyncSession,
):
    """Test successfully loading and instantiating a policy from DB config."""
    policy_name = "test_policy_success"
    mock_policy_config_model = create_mock_policy_model(name=policy_name)
    mock_get_policy_by_name.return_value = mock_policy_config_model

    # Mock the instantiated policy object that load_policy should return
    mock_instantiated_policy = MagicMock(spec=ControlPolicy)
    mock_load_policy.return_value = mock_instantiated_policy

    # Call the function under test
    loaded_policy = await load_policy_from_db(
        name=policy_name,
        session=mock_db_session,  # Pass the mock session
        settings=load_db_dependencies["settings"],
        http_client=load_db_dependencies["http_client"],
        api_key_lookup=load_db_dependencies["api_key_lookup"],
    )

    # Assertions
    mock_get_policy_by_name.assert_awaited_once_with(mock_db_session, policy_name)
    # Assert load_policy is called with the expected policy_data dict and dependencies
    expected_policy_data = {"name": mock_policy_config_model.name, "config": mock_policy_config_model.config or {}}
    expected_dependencies = {
        "api_key_lookup": load_db_dependencies["api_key_lookup"],
        "settings": load_db_dependencies["settings"],
        "http_client": load_db_dependencies["http_client"],
        "db_session": mock_db_session,  # Assign mock_db_session to the key
    }
    mock_load_policy.assert_called_once_with(expected_policy_data, **expected_dependencies)
    assert loaded_policy == mock_instantiated_policy


@patch("luthien_control.db.control_policy_crud.get_policy_by_name", new_callable=AsyncMock, return_value=None)
async def test_load_policy_from_db_not_found_patch_get(
    mock_get_policy_by_name,
    load_db_dependencies,
    mock_db_session,  # Keep using mock session for this specific variation
):
    """Test PolicyLoadError using PATCHED get_policy_by_name returning None."""
    # This test variant ensures the error is raised even if DB call is mocked
    policy_name = "non_existent_policy_patch"

    with pytest.raises(PolicyLoadError, match="not found in database"):
        await load_policy_from_db(
            name=policy_name,
            session=mock_db_session,
            settings=load_db_dependencies["settings"],
            http_client=load_db_dependencies["http_client"],
            api_key_lookup=load_db_dependencies["api_key_lookup"],
        )
    mock_get_policy_by_name.assert_awaited_once_with(mock_db_session, policy_name)


# Test using the actual DB session
async def test_load_policy_from_db_not_found_real_session(
    load_db_dependencies,
    async_session: AsyncSession,  # Use real session from tests/db/conftest.py
):
    """Test PolicyLoadError using a REAL session where the policy doesn't exist."""
    policy_name = "non_existent_policy_real"

    # Since the DB is empty, get_policy_by_name inside load_policy_from_db
    # will return None.
    with pytest.raises(PolicyLoadError, match="not found in database"):
        await load_policy_from_db(
            name=policy_name,
            session=async_session,  # Pass the real session
            settings=load_db_dependencies["settings"],
            http_client=load_db_dependencies["http_client"],
            api_key_lookup=load_db_dependencies["api_key_lookup"],
        )


# Keep the original patch for get_policy_by_name to ensure isolation if needed
# @patch("luthien_control.db.control_policy_crud.get_policy_by_name", new_callable=AsyncMock)
# Patch instantiate_policy to simulate failure
@patch(
    "luthien_control.db.control_policy_crud.load_policy",
    new_callable=MagicMock,
    side_effect=PolicyLoadError("Instantiation failed"),  # This is the initial error
)
async def test_load_policy_from_db_instantiation_fails(
    mock_load_policy,
    # mock_get_policy_by_name, # Remove patch for get_policy
    load_db_dependencies,
    async_session: AsyncSession,  # Use real session
):
    """Test PolicyLoadError when load_policy fails, using real session."""
    policy_name = "instantiation_failure_policy"
    # Create the policy config in the real DB first
    policy_to_create = create_mock_policy_model(name=policy_name)
    # We need the actual create function now
    from luthien_control.db.control_policy_crud import save_policy_to_db

    created_policy = await save_policy_to_db(async_session, policy_to_create)
    assert created_policy is not None
    assert created_policy.name == policy_name

    # Match the error raised by the mock's side_effect
    with pytest.raises(PolicyLoadError, match="Instantiation failed"):
        await load_policy_from_db(
            name=policy_name,
            session=async_session,  # Use real session
            settings=load_db_dependencies["settings"],
            http_client=load_db_dependencies["http_client"],
            api_key_lookup=load_db_dependencies["api_key_lookup"],
        )

    # mock_get_policy_by_name.assert_awaited_once_with(async_session, policy_name)
    mock_load_policy.assert_called_once()  # Verify load_policy was called
