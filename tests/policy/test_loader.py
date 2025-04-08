"""Tests for the PolicyLoader."""

from unittest.mock import MagicMock

import pytest

# Corrected example policies exist for testing purposes
from luthien_control.policies.examples.no_op import NoOpPolicy
from luthien_control.policies.loader import PolicyLoader

# Corrected import a second one if available and configured in mock settings
# from luthien_control.policies.examples.all_caps import AllCapsPolicy


@pytest.fixture
def mock_settings() -> MagicMock:
    """Provides a mock Settings object."""
    settings = MagicMock()
    # Configure mock return values for policy lists with corrected paths
    settings.get_request_policies.return_value = [
        "luthien_control.policies.examples.no_op.NoOpPolicy",
        "invalid.policy.path.DoesNotExist",  # Test invalid path
        "luthien_control.policies.base.Policy",  # Test loading a protocol (should fail instantiation/be skipped)
        # Add another valid policy if testing multiple
        # "luthien_control.policies.examples.all_caps.AllCapsPolicy",
    ]
    settings.get_response_policies.return_value = [
        "luthien_control.policies.examples.no_op.NoOpPolicy",
    ]
    return settings


def test_policy_loader_init(mock_settings):
    """Test that the loader initializes correctly."""
    loader = PolicyLoader(settings=mock_settings)
    assert loader.settings is mock_settings
    assert loader._request_policy_instances == []
    assert loader._response_policy_instances == []


def test_policy_loader_load_policies(mock_settings):
    """Test loading valid and invalid policies."""
    loader = PolicyLoader(settings=mock_settings)
    loader.load_policies()  # Explicitly call load

    # Verify settings methods were called
    mock_settings.get_request_policies.assert_called_once()
    mock_settings.get_response_policies.assert_called_once()

    # Check loaded request policies (only valid ones should load)
    assert len(loader._request_policy_instances) == 1  # Expecting only NoOpPolicy
    assert isinstance(loader._request_policy_instances[0], NoOpPolicy)
    # assert isinstance(loader._request_policy_instances[1], AllCapsPolicy) # If testing multiple

    # Check loaded response policies
    assert len(loader._response_policy_instances) == 1
    assert isinstance(loader._response_policy_instances[0], NoOpPolicy)


def test_policy_loader_get_policies_lazy_load(mock_settings):
    """Test that get_* methods trigger loading if needed."""
    loader = PolicyLoader(settings=mock_settings)

    # Access request policies - should trigger load
    request_policies = loader.get_request_policies()
    assert len(request_policies) == 1
    assert isinstance(request_policies[0], NoOpPolicy)
    mock_settings.get_request_policies.assert_called_once()  # Verify load happened
    mock_settings.get_response_policies.assert_called_once()  # load_policies loads both

    # Reset mock call counts before next check
    mock_settings.get_request_policies.reset_mock()
    mock_settings.get_response_policies.reset_mock()

    # Access response policies - should *not* trigger load again
    response_policies = loader.get_response_policies()
    assert len(response_policies) == 1
    assert isinstance(response_policies[0], NoOpPolicy)
    mock_settings.get_request_policies.assert_not_called()  # Verify load did *not* happen again
    mock_settings.get_response_policies.assert_not_called()

    # Access request policies again - should also not trigger load
    request_policies_again = loader.get_request_policies()
    assert request_policies_again is request_policies  # Should be same list instance
    mock_settings.get_request_policies.assert_not_called()
    mock_settings.get_response_policies.assert_not_called()


def test_policy_loader_instantiate_policies_edge_cases(mock_settings):
    """Test the internal _instantiate_policies with edge cases."""
    loader = PolicyLoader(settings=mock_settings)

    # Test with an empty list
    instances = loader._instantiate_policies([])
    assert instances == []

    # Test with invalid names (already partially covered by load_policies test)
    instances = loader._instantiate_policies(
        [
            "invalid.path",
            "luthien_control.policies.examples.no_op",  # Module, not class
            "luthien_control.policies.examples.no_op.NonExistentClass",
        ]
    )
    assert instances == []  # Current implementation skips all errors
