"""Tests for policy serialization and deserialization round-trip."""

from unittest.mock import AsyncMock, patch

import pytest
from luthien_control.control_policy.add_api_key_header import AddApiKeyHeaderPolicy
from luthien_control.control_policy.client_api_key_auth import ClientApiKeyAuthPolicy
from luthien_control.control_policy.compound_policy import CompoundPolicy
from luthien_control.control_policy.initialize_context import InitializeContextPolicy
from luthien_control.control_policy.prepare_backend_headers import PrepareBackendHeadersPolicy
from luthien_control.control_policy.request_logging import RequestLoggingPolicy
from luthien_control.control_policy.send_backend_request import SendBackendRequestPolicy
from luthien_control.db import crud
from luthien_control.db.models import Policy as DbPolicy


# Helper to get full class path
def get_class_path(cls):
    return f"{cls.__module__}.{cls.__qualname__}"


@pytest.mark.asyncio
@patch("luthien_control.db.crud.get_policy_config_by_name", new_callable=AsyncMock)
async def test_round_trip_add_api_key_header(mock_get_config, mock_settings, mock_http_client, mock_api_key_lookup):
    """Test serialization/deserialization for AddApiKeyHeaderPolicy."""
    original_policy = AddApiKeyHeaderPolicy(settings=mock_settings)
    policy_name = "TestAddApiKeyHeader"
    original_policy.name = policy_name
    class_path = get_class_path(AddApiKeyHeaderPolicy)

    serialized_config = original_policy.serialize_config()
    expected_config = {
        "__policy_type__": "AddApiKeyHeaderPolicy",
        "name": policy_name,
        "policy_class_path": None,
    }
    assert serialized_config == expected_config

    mock_db_policy = DbPolicy(
        id=1,
        name=policy_name,
        policy_class_path=class_path,
        config=serialized_config,
        is_active=True,
        description="Test",
    )
    mock_get_config.return_value = mock_db_policy

    loaded_policy = await crud.load_policy_from_db(
        name=policy_name,
        settings=mock_settings,
        http_client=mock_http_client,
        api_key_lookup=mock_api_key_lookup,
    )

    assert isinstance(loaded_policy, AddApiKeyHeaderPolicy)
    assert loaded_policy.name == policy_name
    # No config attributes to check


@pytest.mark.asyncio
@patch("luthien_control.db.crud.get_policy_config_by_name", new_callable=AsyncMock)
async def test_round_trip_send_backend_request(mock_get_config, mock_settings, mock_http_client, mock_api_key_lookup):
    """Test serialization/deserialization for SendBackendRequestPolicy."""
    original_policy = SendBackendRequestPolicy(http_client=mock_http_client)
    policy_name = "TestSendBackend"
    original_policy.name = policy_name
    class_path = get_class_path(SendBackendRequestPolicy)

    serialized_config = original_policy.serialize_config()
    expected_config = {
        "__policy_type__": "SendBackendRequestPolicy",
        "name": policy_name,
        "policy_class_path": None,
    }
    assert serialized_config == expected_config

    mock_db_policy = DbPolicy(
        id=2,
        name=policy_name,
        policy_class_path=class_path,
        config=serialized_config,
        is_active=True,
        description="Test",
    )
    mock_get_config.return_value = mock_db_policy

    loaded_policy = await crud.load_policy_from_db(
        name=policy_name,
        settings=mock_settings,
        http_client=mock_http_client,
        api_key_lookup=mock_api_key_lookup,
    )

    assert isinstance(loaded_policy, SendBackendRequestPolicy)
    assert loaded_policy.name == policy_name
    # No config attributes to check


@pytest.mark.asyncio
@patch("luthien_control.db.crud.get_policy_config_by_name", new_callable=AsyncMock)
async def test_round_trip_request_logging(mock_get_config, mock_settings, mock_http_client, mock_api_key_lookup):
    """Test serialization/deserialization for RequestLoggingPolicy."""
    original_policy = RequestLoggingPolicy()
    policy_name = "TestRequestLogging"
    original_policy.name = policy_name
    class_path = get_class_path(RequestLoggingPolicy)

    serialized_config = original_policy.serialize_config()
    expected_config = {
        "__policy_type__": "RequestLoggingPolicy",
        "name": policy_name,
        "policy_class_path": None,
    }
    assert serialized_config == expected_config

    mock_db_policy = DbPolicy(
        id=3,
        name=policy_name,
        policy_class_path=class_path,
        config=serialized_config,
        is_active=True,
        description="Test",
    )
    mock_get_config.return_value = mock_db_policy

    loaded_policy = await crud.load_policy_from_db(
        name=policy_name,
        settings=mock_settings,
        http_client=mock_http_client,
        api_key_lookup=mock_api_key_lookup,
    )

    assert isinstance(loaded_policy, RequestLoggingPolicy)
    assert loaded_policy.name == policy_name


@pytest.mark.asyncio
@patch("luthien_control.db.crud.get_policy_config_by_name", new_callable=AsyncMock)
async def test_round_trip_prepare_backend_headers(
    mock_get_config, mock_settings, mock_http_client, mock_api_key_lookup
):
    """Test serialization/deserialization for PrepareBackendHeadersPolicy."""
    original_policy = PrepareBackendHeadersPolicy(settings=mock_settings)
    policy_name = "TestPrepareHeaders"
    original_policy.name = policy_name
    class_path = get_class_path(PrepareBackendHeadersPolicy)

    serialized_config = original_policy.serialize_config()
    expected_config = {
        "__policy_type__": "PrepareBackendHeadersPolicy",
        "name": policy_name,
        "policy_class_path": None,
    }
    assert serialized_config == expected_config

    mock_db_policy = DbPolicy(
        id=4,
        name=policy_name,
        policy_class_path=class_path,
        config=serialized_config,
        is_active=True,
        description="Test",
    )
    mock_get_config.return_value = mock_db_policy

    loaded_policy = await crud.load_policy_from_db(
        name=policy_name,
        settings=mock_settings,
        http_client=mock_http_client,
        api_key_lookup=mock_api_key_lookup,
    )

    assert isinstance(loaded_policy, PrepareBackendHeadersPolicy)
    assert loaded_policy.name == policy_name


@pytest.mark.asyncio
@patch("luthien_control.db.crud.get_policy_config_by_name", new_callable=AsyncMock)
async def test_round_trip_client_api_key_auth(mock_get_config, mock_settings, mock_http_client, mock_api_key_lookup):
    """Test serialization/deserialization for ClientApiKeyAuthPolicy."""
    original_policy = ClientApiKeyAuthPolicy(api_key_lookup=mock_api_key_lookup)
    policy_name = "TestClientAuth"
    original_policy.name = policy_name
    class_path = get_class_path(ClientApiKeyAuthPolicy)

    serialized_config = original_policy.serialize_config()
    expected_config = {
        "__policy_type__": "ClientApiKeyAuthPolicy",
        "name": policy_name,
        "policy_class_path": None,
    }
    assert serialized_config == expected_config

    mock_db_policy = DbPolicy(
        id=5,
        name=policy_name,
        policy_class_path=class_path,
        config=serialized_config,
        is_active=True,
        description="Test",
    )
    mock_get_config.return_value = mock_db_policy

    loaded_policy = await crud.load_policy_from_db(
        name=policy_name,
        settings=mock_settings,
        http_client=mock_http_client,
        api_key_lookup=mock_api_key_lookup,
    )

    assert isinstance(loaded_policy, ClientApiKeyAuthPolicy)
    assert loaded_policy.name == policy_name


@pytest.mark.asyncio
@patch("luthien_control.db.crud.get_policy_config_by_name", new_callable=AsyncMock)
async def test_round_trip_initialize_context(mock_get_config, mock_settings, mock_http_client, mock_api_key_lookup):
    """Test serialization/deserialization for InitializeContextPolicy."""
    original_policy = InitializeContextPolicy(settings=mock_settings)  # Pass settings even if unused internally
    policy_name = "TestInitContext"
    original_policy.name = policy_name
    class_path = get_class_path(InitializeContextPolicy)

    serialized_config = original_policy.serialize_config()
    expected_config = {
        "__policy_type__": "InitializeContextPolicy",
        "name": policy_name,
        "policy_class_path": None,
    }
    assert serialized_config == expected_config

    mock_db_policy = DbPolicy(
        id=6,
        name=policy_name,
        policy_class_path=class_path,
        config=serialized_config,
        is_active=True,
        description="Test",
    )
    mock_get_config.return_value = mock_db_policy

    loaded_policy = await crud.load_policy_from_db(
        name=policy_name,
        settings=mock_settings,
        http_client=mock_http_client,
        api_key_lookup=mock_api_key_lookup,
    )

    assert isinstance(loaded_policy, InitializeContextPolicy)
    assert loaded_policy.name == policy_name


@pytest.mark.asyncio
@patch("luthien_control.db.crud.get_policy_config_by_name", new_callable=AsyncMock)
async def test_round_trip_compound_policy(mock_get_config, mock_settings, mock_http_client, mock_api_key_lookup):
    """Test serialization/deserialization for CompoundPolicy using DB lookup."""
    # Use actual policy types for members where dependencies are simple or mocked
    member1 = InitializeContextPolicy()
    member1.name = "MemberInit"
    member1_class_path = get_class_path(InitializeContextPolicy)
    member1.policy_class_path = member1_class_path  # Set path manually for serialization test

    member2 = RequestLoggingPolicy()
    member2.name = "MemberLog"
    member2_class_path = get_class_path(RequestLoggingPolicy)
    member2.policy_class_path = member2_class_path

    # Create original CompoundPolicy
    original_policy = CompoundPolicy(policies=[member1, member2])
    policy_name = "TestCompoundDB"
    original_policy.name = policy_name
    compound_class_path = get_class_path(CompoundPolicy)
    original_policy.policy_class_path = compound_class_path  # Set path manually

    # Serialize (New Format)
    member1_config = member1.serialize_config()
    member2_config = member2.serialize_config()
    expected_serialized_config = {
        "__policy_type__": "CompoundPolicy",
        "name": policy_name,
        "policy_class_path": compound_class_path,
        "member_policy_configs": [member1_config, member2_config],
    }
    serialized_config = original_policy.serialize_config()
    assert serialized_config == expected_serialized_config

    # Mock DB records for Compound and its members
    mock_compound_db_policy = DbPolicy(
        id=7,
        name=policy_name,
        policy_class_path=compound_class_path,
        config=serialized_config,  # Store the NEW serialized config
        is_active=True,
        description="Test Compound from DB",
    )
    DbPolicy(
        id=8,
        name=member1.name,
        policy_class_path=member1_class_path,
        config=member1_config,  # Store member config (though loader won't use it here)
        is_active=True,
        description="Test Member 1",
    )
    DbPolicy(
        id=9,
        name=member2.name,
        policy_class_path=member2_class_path,
        config=member2_config,
        is_active=True,
        description="Test Member 2",
    )

    # Setup mock for get_policy_config_by_name to return the correct DB record based on name
    def side_effect(name, *args, **kwargs):
        if name == policy_name:
            return mock_compound_db_policy
        # In this test, the loader SHOULD NOT query for members because the config is embedded
        # If it does query, something is wrong with the loading logic using the override.
        # However, for robustness if other tests need it, we can return them.
        elif name == member1.name:
            pytest.fail(f"Loader unexpectedly tried to fetch member '{member1.name}' from DB")
            # return mock_member1_db_policy # Should not be called
        elif name == member2.name:
            pytest.fail(f"Loader unexpectedly tried to fetch member '{member2.name}' from DB")
            # return mock_member2_db_policy # Should not be called
        return None

    mock_get_config.side_effect = side_effect

    # Load the policy using the top-level name
    loaded_policy = await crud.load_policy_from_db(
        name=policy_name,
        settings=mock_settings,
        http_client=mock_http_client,
        api_key_lookup=mock_api_key_lookup,
    )

    # Assertions
    assert isinstance(loaded_policy, CompoundPolicy)
    assert loaded_policy.name == policy_name
    assert loaded_policy.policy_class_path == compound_class_path
    assert len(loaded_policy.policies) == 2

    loaded_member1, loaded_member2 = loaded_policy.policies
    assert isinstance(loaded_member1, InitializeContextPolicy)
    assert loaded_member1.name == member1.name
    assert loaded_member1.policy_class_path == member1_class_path

    assert isinstance(loaded_member2, RequestLoggingPolicy)
    assert loaded_member2.name == member2.name
    assert loaded_member2.policy_class_path == member2_class_path

    # Ensure the mock was called only for the top-level policy
    mock_get_config.assert_called_once_with(policy_name)


@pytest.mark.asyncio
@patch("luthien_control.db.crud.get_policy_config_by_name", new_callable=AsyncMock)
async def test_serialize_compound_missing_member_name(mock_get_config):
    """Test CompoundPolicy serialize raises error if member name is missing."""
    member1 = RequestLoggingPolicy()
    member1.name = None  # Simulate missing name

    compound_policy = CompoundPolicy(policies=[member1])
    compound_policy.name = "BadCompound"

    with pytest.raises(ValueError, match="member policy RequestLoggingPolicy has no name set"):
        compound_policy.serialize_config()
