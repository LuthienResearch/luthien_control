# tests/core/test_policy_loader.py

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from luthien_control.config.settings import Settings

# Import from the new policy_loader module
from luthien_control.control_policy.compound_policy import CompoundPolicy
from luthien_control.control_policy.interface import ControlPolicy
from luthien_control.core.policy_loader import (
    ApiKeyLookupFunc,
    PolicyLoadError,
    instantiate_policy,
)

# Keep mock policies import path for now, may refactor later
from tests.db.mock_policies import (
    MockCompoundPolicy,
    MockNestedPolicy,
    MockNoArgsPolicy,
    MockPolicyWithApiKeyLookup,
    MockSimplePolicy,
)

# Mark all tests in this module as async
pytestmark = pytest.mark.asyncio


# --- Fixtures --- #


@pytest.fixture
def mock_settings() -> Settings:
    """Provides a mock Settings object."""
    return MagicMock(spec=Settings)


@pytest.fixture
def mock_http_client() -> httpx.AsyncClient:
    """Provides a mock httpx.AsyncClient."""
    return MagicMock(spec=httpx.AsyncClient)


@pytest.fixture
def mock_api_key_lookup() -> ApiKeyLookupFunc:
    """Provides a mock ApiKeyLookupFunc."""
    return AsyncMock()


@pytest.fixture
def mock_dependencies(mock_settings, mock_http_client, mock_api_key_lookup):
    """Bundles the common dependencies for instantiate_policy tests."""
    return {
        "settings": mock_settings,
        "http_client": mock_http_client,
        "api_key_lookup": mock_api_key_lookup,
    }


# --- Tests for instantiate_policy --- #


# Patch the importlib/getattr calls within the *new* policy_loader module
@patch("luthien_control.core.policy_loader.importlib.import_module")
@patch("luthien_control.core.policy_loader.getattr")
async def test_instantiate_simple_policy_success(mock_getattr, mock_import_module, mock_dependencies):
    """Test successful instantiation of a simple policy with config."""
    mock_module = MagicMock()
    mock_import_module.return_value = mock_module
    mock_getattr.return_value = MockSimplePolicy  # Return the mock class

    test_config = {
        "policy_class_path": "tests.db.mock_policies.MockSimplePolicy",
        "name": "simple_test_policy",
        "param1": "value1",
        "param2": 123,
    }

    instance = await instantiate_policy(test_config, **mock_dependencies)

    assert isinstance(instance, MockSimplePolicy)
    assert instance.name == "simple_test_policy"  # Check name attribute is set
    assert instance.policy_class_path == test_config["policy_class_path"]  # Check class path attribute
    # Check if settings/client were injected (MockSimplePolicy expects them)
    assert instance.settings is mock_dependencies["settings"]
    assert instance.http_client is mock_dependencies["http_client"]
    # Check if config params were passed
    instance.mock_init.assert_called_once_with(
        settings=mock_dependencies["settings"],
        http_client=mock_dependencies["http_client"],
        timeout=30,  # Expect the default timeout from the mock's __init__
    )
    mock_import_module.assert_called_once_with("tests.db.mock_policies")
    mock_getattr.assert_called_once_with(mock_module, "MockSimplePolicy")


@patch("luthien_control.core.policy_loader.importlib.import_module")
@patch("luthien_control.core.policy_loader.getattr")
async def test_instantiate_with_api_key_lookup(mock_getattr, mock_import_module, mock_dependencies):
    """Test policy instantiation correctly injects api_key_lookup."""
    mock_module = MagicMock()
    mock_import_module.return_value = mock_module
    mock_getattr.return_value = MockPolicyWithApiKeyLookup

    test_config = {
        "policy_class_path": "tests.db.mock_policies.MockPolicyWithApiKeyLookup",
        "name": "api_lookup_policy",
        "tag": "expected_tag",
    }

    instance = await instantiate_policy(test_config, **mock_dependencies)

    assert isinstance(instance, MockPolicyWithApiKeyLookup)
    assert instance.api_key_lookup is mock_dependencies["api_key_lookup"]
    instance.mock_init.assert_called_once_with(api_key_lookup=mock_dependencies["api_key_lookup"], tag="expected_tag")


async def test_instantiate_policy_missing_class_path(mock_dependencies):
    """Test PolicyLoadError if policy_class_path is missing."""
    test_config = {"name": "missing_path"}
    with pytest.raises(PolicyLoadError, match="missing required key: 'policy_class_path'"):
        await instantiate_policy(test_config, **mock_dependencies)


async def test_instantiate_policy_missing_name(mock_dependencies):
    """Test PolicyLoadError if name is missing."""
    test_config = {"policy_class_path": "some.path.Policy"}
    with pytest.raises(PolicyLoadError, match="missing required key: 'name'"):
        await instantiate_policy(test_config, **mock_dependencies)


@patch("luthien_control.core.policy_loader.importlib.import_module", side_effect=ImportError("Module not found"))
async def test_instantiate_policy_import_error(mock_import_module, mock_dependencies):
    """Test PolicyLoadError on class import failure (ImportError)."""
    test_config = {
        "policy_class_path": "nonexistent.module.Policy",
        "name": "import_fail_policy",
    }
    with pytest.raises(PolicyLoadError, match="Could not load policy class"):
        await instantiate_policy(test_config, **mock_dependencies)
    mock_import_module.assert_called_once_with("nonexistent.module")


@patch("luthien_control.core.policy_loader.importlib.import_module")
@patch("luthien_control.core.policy_loader.getattr", side_effect=AttributeError("Class not found"))
async def test_instantiate_policy_attribute_error(mock_getattr, mock_import_module, mock_dependencies):
    """Test PolicyLoadError on class import failure (AttributeError)."""
    mock_module = MagicMock()
    mock_import_module.return_value = mock_module

    test_config = {
        "policy_class_path": "tests.db.mock_policies.NonExistentPolicy",
        "name": "attr_fail_policy",
    }
    with pytest.raises(PolicyLoadError, match="Could not load policy class"):
        await instantiate_policy(test_config, **mock_dependencies)
    mock_import_module.assert_called_once_with("tests.db.mock_policies")
    mock_getattr.assert_called_once_with(mock_module, "NonExistentPolicy")


@patch("luthien_control.core.policy_loader.importlib.import_module")
@patch("luthien_control.core.policy_loader.getattr")
async def test_instantiate_nested_policy_success(mock_getattr, mock_import_module, mock_dependencies):
    """Test successful instantiation of a policy with a nested policy config."""

    # Side effect for getattr to return different classes based on name
    def getattr_side_effect(module, class_name):
        if class_name == "MockNestedPolicy":
            return MockNestedPolicy
        elif class_name == "MockSimplePolicy":
            return MockSimplePolicy
        else:
            raise AttributeError(f"Mock class not found: {class_name}")

    mock_module = MagicMock()
    mock_import_module.return_value = mock_module
    mock_getattr.side_effect = getattr_side_effect

    nested_policy_config = {
        "policy_class_path": "tests.db.mock_policies.MockSimplePolicy",
        "name": "nested_simple",
        "timeout": 99,
    }
    parent_policy_config = {
        "policy_class_path": "tests.db.mock_policies.MockNestedPolicy",
        "name": "parent_nested",
        "description": "Parent description",
        "nested_policy": nested_policy_config,
    }

    instance = await instantiate_policy(parent_policy_config, **mock_dependencies)

    assert isinstance(instance, MockNestedPolicy)
    assert instance.name == "parent_nested"
    assert instance.description == "Parent description"
    assert isinstance(instance.nested_policy, MockSimplePolicy)
    assert instance.nested_policy.name == "nested_simple"
    assert instance.nested_policy.timeout == 99

    # Check __init__ was called correctly for parent
    instance.mock_init.assert_called_once()
    init_kwargs = instance.mock_init.call_args.kwargs
    assert isinstance(init_kwargs.get("nested_policy"), MockSimplePolicy)
    assert init_kwargs.get("description") == "Parent description"

    # Check __init__ was called correctly for nested
    instance.nested_policy.mock_init.assert_called_once_with(
        settings=mock_dependencies["settings"],
        http_client=mock_dependencies["http_client"],
        timeout=99,
    )


@patch("luthien_control.core.policy_loader.importlib.import_module")
@patch("luthien_control.core.policy_loader.getattr")
async def test_instantiate_policy_with_list_of_policies(mock_getattr, mock_import_module, mock_dependencies):
    """Test instantiating a policy that takes a list of other policies (like CompoundPolicy)."""

    # Side effect for getattr to return different classes based on name
    def getattr_side_effect(module, class_name):
        if class_name == "MockCompoundPolicy":  # Mock for the main policy
            return MockCompoundPolicy
        elif class_name == "MockSimplePolicy":
            return MockSimplePolicy
        elif class_name == "MockNoArgsPolicy":
            return MockNoArgsPolicy
        else:
            raise AttributeError(f"Mock class not found: {class_name}")

    mock_module = MagicMock()
    mock_import_module.return_value = mock_module
    mock_getattr.side_effect = getattr_side_effect

    policy_config = {
        "name": "compound_test",
        "policy_class_path": "tests.db.mock_policies.MockCompoundPolicy",
        "member_policy_configs": [
            {
                "name": "member_simple",
                "policy_class_path": "tests.db.mock_policies.MockSimplePolicy",
                "param1": "member1",
            },
            {
                "name": "member_no_args",
                "policy_class_path": "tests.db.mock_policies.MockNoArgsPolicy",
            },
            "not_a_policy_dict",  # Should be preserved in the list
            {
                "some_other_data": True  # Should be preserved
            },
        ],
        "other_param": "should_be_ignored_by_compound",
    }

    instance = await instantiate_policy(policy_config, **mock_dependencies)

    assert isinstance(instance, MockCompoundPolicy)
    assert instance.name == "compound_test"

    # Check the policies list passed to the CompoundPolicy constructor
    instance.mock_init.assert_called_once()
    init_kwargs = instance.mock_init.call_args.kwargs
    assert "policies" in init_kwargs
    policies_list = init_kwargs["policies"]

    assert len(policies_list) == 4  # Two instantiated policies + two non-policy items

    # Check first instantiated policy
    assert isinstance(policies_list[0], MockSimplePolicy)
    assert policies_list[0].name == "member_simple"
    policies_list[0].mock_init.assert_called_once_with(
        settings=mock_dependencies["settings"], http_client=mock_dependencies["http_client"], timeout=30
    )

    # Check second instantiated policy
    assert isinstance(policies_list[1], MockNoArgsPolicy)
    assert policies_list[1].name == "member_no_args"
    policies_list[1].mock_init.assert_called_once_with()  # No args expected

    # Check non-policy items preserved
    assert policies_list[2] == "not_a_policy_dict"
    assert policies_list[3] == {"some_other_data": True}

    # Check other_param was ignored by CompoundPolicy (not in its __init__)
    assert "other_param" not in init_kwargs


@patch("luthien_control.core.policy_loader.importlib.import_module")
@patch("luthien_control.core.policy_loader.getattr")
@patch("luthien_control.core.policy_loader.issubclass")
@patch("luthien_control.core.policy_loader.inspect.isclass")
async def test_compound_policy_db_load_bug(
    mock_isclass, mock_issubclass, mock_getattr, mock_import_module, mock_dependencies
):
    """Test for a bug where compound policy configs loaded from DB aren't properly instantiated."""

    # Configure mocks to bypass class type checking
    mock_isclass.return_value = True
    # Make issubclass return True when checking if our mocks are subclasses of ControlPolicy
    mock_issubclass.side_effect = lambda cls, base: True if base is ControlPolicy else isinstance(cls, type(base))

    # Create mock policy classes for our test that don't require special args
    class MockClientAuthPolicy(ControlPolicy):
        def __init__(self):
            self.name = "ClientAuth"
            self.policy_class_path = "luthien_control.control_policy.client_api_key_auth.ClientApiKeyAuthPolicy"

        async def apply(self, context):
            return context

        def serialize_config(self):
            return {
                "name": self.name,
                "__policy_type__": "ClientApiKeyAuthPolicy",
                "policy_class_path": self.policy_class_path
            }

    class MockAddKeyPolicy(ControlPolicy):
        def __init__(self):
            self.name = "AddBackendKey"
            self.policy_class_path = "luthien_control.control_policy.add_api_key_header.AddApiKeyHeaderPolicy"

        async def apply(self, context):
            return context

        def serialize_config(self):
            return {
                "name": self.name,
                "__policy_type__": "AddApiKeyHeaderPolicy",
                "policy_class_path": self.policy_class_path
            }

    # Side effect for getattr to return different classes based on name
    def getattr_side_effect(module, class_name):
        if class_name == "CompoundPolicy":  # Real compound policy
            return CompoundPolicy
        elif class_name == "ClientApiKeyAuthPolicy":
            return MockClientAuthPolicy
        elif class_name == "AddApiKeyHeaderPolicy":
            return MockAddKeyPolicy
        elif class_name == "MockSimplePolicy":
            return MockSimplePolicy
        elif class_name == "MockNoArgsPolicy":
            return MockNoArgsPolicy
        else:
            raise AttributeError(f"Mock class not found: {class_name}")

    # Our real classes will be instantiated directly instead of using MagicMock instances

    mock_module = MagicMock()
    mock_import_module.return_value = mock_module
    mock_getattr.side_effect = getattr_side_effect

    # Recreate the real DB config structure we get from the database
    policy_config = {
        "name": "root",
        "policy_class_path": "luthien_control.control_policy.compound_policy.CompoundPolicy",
        "member_policy_configs": [
            {
                "name": "ClientAuth",
                "__policy_type__": "ClientApiKeyAuthPolicy",
                "policy_class_path": "luthien_control.control_policy.client_api_key_auth.ClientApiKeyAuthPolicy"
            },
            {
                "name": "AddBackendKey",
                "__policy_type__": "AddApiKeyHeaderPolicy",
                "policy_class_path": "luthien_control.control_policy.add_api_key_header.AddApiKeyHeaderPolicy"
            },
        ],
        "__policy_type__": "CompoundPolicy",
    }

    # This should pass if member_policy_configs are properly instantiated as policy objects
    # It should fail if they're passed as raw dictionaries to CompoundPolicy constructor
    instance = await instantiate_policy(policy_config, **mock_dependencies)

    # If things worked correctly, we should have a CompoundPolicy instance
    assert isinstance(instance, CompoundPolicy)
    assert instance.name == "root"

    # The policies in the CompoundPolicy should be actual policy instances, not config dicts
    assert len(instance.policies) == 2

    # Check that the instantiated policies in CompoundPolicy are actual policy instances
    # not just config dictionaries
    assert isinstance(instance.policies[0], MockClientAuthPolicy)
    assert isinstance(instance.policies[1], MockAddKeyPolicy)

    # Check that they have the correct names from the configs
    assert instance.policies[0].name == "ClientAuth"
    assert instance.policies[1].name == "AddBackendKey"


@patch("luthien_control.core.policy_loader.importlib.import_module")
@patch("luthien_control.core.policy_loader.getattr")
async def test_instantiate_nested_policy_load_fails(mock_getattr, mock_import_module, mock_dependencies):
    """Test that if a nested policy fails to load, the overall load fails."""

    # Side effect for getattr: succeed for parent, fail for nested
    def getattr_side_effect(module, class_name):
        if class_name == "MockNestedPolicy":
            return MockNestedPolicy
        elif class_name == "MockBrokenPolicy":
            raise AttributeError("Cannot find MockBrokenPolicy")  # Simulate failure
        else:
            raise AttributeError(f"Mock class not found: {class_name}")

    mock_module = MagicMock()
    mock_import_module.return_value = mock_module
    mock_getattr.side_effect = getattr_side_effect

    nested_broken_config = {
        "policy_class_path": "tests.db.mock_policies.MockBrokenPolicy",  # This will fail getattr
        "name": "nested_broken",
    }
    parent_policy_config = {
        "policy_class_path": "tests.db.mock_policies.MockNestedPolicy",
        "name": "parent_of_broken",
        "nested_policy": nested_broken_config,
    }

    with pytest.raises(PolicyLoadError, match="Failed to instantiate nested policy 'nested_broken'"):
        await instantiate_policy(parent_policy_config, **mock_dependencies)

    # Check that getattr was called for both parent and attempted for child
    assert mock_getattr.call_count == 2
    mock_getattr.assert_any_call(mock_module, "MockNestedPolicy")
    mock_getattr.assert_any_call(mock_module, "MockBrokenPolicy")
