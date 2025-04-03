from unittest.mock import MagicMock, patch

import pytest
from luthien_control.config.settings import Settings
from luthien_control.policies.base import Policy
from luthien_control.policy_loader import PolicyLoadError, load_policy

# --- Test Policies (Dummy implementations) ---


class ValidTestPolicy(Policy):
    """A valid policy for testing."""

    async def apply_request_policy(self, request, original_body, request_id):
        return {"content": original_body, "headers": request.headers.raw}

    async def apply_response_policy(self, backend_response, original_response_body, request_id):
        return {
            "content": original_response_body,
            "headers": backend_response.headers,
            "status_code": backend_response.status_code,
        }


class NotAPolicy:
    """A class that does not inherit from Policy."""

    pass


class PolicyWithInitError(Policy):
    """A policy that raises an error during instantiation."""

    def __init__(self):
        raise ValueError("Initialization failed")

    async def apply_request_policy(self, request, original_body, request_id):
        pass  # pragma: no cover

    async def apply_response_policy(self, backend_response, original_response_body, request_id):
        pass  # pragma: no cover


# --- Test Fixtures ---


@pytest.fixture
def mock_settings() -> Settings:
    """Fixture to create a mock Settings object."""
    settings = MagicMock(spec=Settings)
    settings.POLICY_MODULE = ""  # Default empty, override in tests
    return settings


# --- Test Cases ---


@patch("importlib.import_module")
def test_load_policy_success(mock_import_module, mock_settings):
    """Test successful loading of a valid policy class."""
    mock_settings.POLICY_MODULE = "dummy_module.ValidTestPolicy"

    # Configure the mock module returned by import_module
    mock_module = MagicMock()
    mock_module.ValidTestPolicy = ValidTestPolicy
    mock_import_module.return_value = mock_module

    policy_instance = load_policy(mock_settings)

    mock_import_module.assert_called_once_with("dummy_module")
    assert isinstance(policy_instance, ValidTestPolicy)


def test_load_policy_invalid_path_format(mock_settings):
    """Test PolicyLoadError for invalid path format."""
    mock_settings.POLICY_MODULE = "invalid-format"

    with pytest.raises(PolicyLoadError, match="Invalid policy path format"):
        load_policy(mock_settings)


@patch("importlib.import_module")
def test_load_policy_module_not_found(mock_import_module, mock_settings):
    """Test PolicyLoadError when the module cannot be imported."""
    mock_settings.POLICY_MODULE = "nonexistent_module.MyPolicy"
    mock_import_module.side_effect = ImportError("No module named 'nonexistent_module'")

    with pytest.raises(PolicyLoadError, match="Could not import policy module"):
        load_policy(mock_settings)
    mock_import_module.assert_called_once_with("nonexistent_module")


@patch("importlib.import_module")
def test_load_policy_class_not_found(mock_import_module, mock_settings):
    """Test PolicyLoadError when the class is not found in the module."""
    mock_settings.POLICY_MODULE = "dummy_module.MissingPolicy"

    mock_module = MagicMock()
    # Deliberately don't add MissingPolicy to the mock module
    # getattr will now return a MagicMock for MissingPolicy
    mock_import_module.return_value = mock_module

    # Update match for the new error message raised after the isinstance check
    with pytest.raises(PolicyLoadError, match="must be a valid subclass of Policy"):
        load_policy(mock_settings)
    mock_import_module.assert_called_once_with("dummy_module")


@patch("importlib.import_module")
def test_load_policy_not_a_subclass(mock_import_module, mock_settings):
    """Test PolicyLoadError when the loaded class is not a Policy subclass."""
    mock_settings.POLICY_MODULE = "dummy_module.NotAPolicy"

    mock_module = MagicMock()
    mock_module.NotAPolicy = NotAPolicy  # Assign the non-policy class
    mock_import_module.return_value = mock_module

    # Update match for the error message raised by the isinstance/issubclass check
    with pytest.raises(PolicyLoadError, match="must be a valid subclass of Policy"):
        load_policy(mock_settings)
    mock_import_module.assert_called_once_with("dummy_module")


@patch("importlib.import_module")
def test_load_policy_instantiation_error(mock_import_module, mock_settings):
    """Test PolicyLoadError when the policy class fails to instantiate."""
    mock_settings.POLICY_MODULE = "dummy_module.PolicyWithInitError"

    mock_module = MagicMock()
    mock_module.PolicyWithInitError = PolicyWithInitError  # Assign the class that errors
    mock_import_module.return_value = mock_module

    with pytest.raises(PolicyLoadError, match="Could not instantiate policy class"):
        load_policy(mock_settings)
    mock_import_module.assert_called_once_with("dummy_module")
