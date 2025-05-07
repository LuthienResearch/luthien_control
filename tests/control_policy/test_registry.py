import inspect
from typing import Dict, Type

# Import the classes directly for comparison
from luthien_control.control_policy.add_api_key_header import AddApiKeyHeaderPolicy
from luthien_control.control_policy.add_api_key_header_from_env import AddApiKeyHeaderFromEnvPolicy
from luthien_control.control_policy.client_api_key_auth import ClientApiKeyAuthPolicy
from luthien_control.control_policy.serial_policy import SerialPolicy
from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.registry import POLICY_NAME_TO_CLASS
from luthien_control.control_policy.send_backend_request import SendBackendRequestPolicy

# Define the expected mappings for verification
EXPECTED_POLICY_MAPPINGS: Dict[str, Type[ControlPolicy]] = {
    "AddApiKeyHeader": AddApiKeyHeaderPolicy,
    "AddApiKeyHeaderFromEnv": AddApiKeyHeaderFromEnvPolicy,
    "ClientApiKeyAuth": ClientApiKeyAuthPolicy,
    "CompoundPolicy": SerialPolicy,  # legacy compatibility
    "SerialPolicy": SerialPolicy,
    "SendBackendRequest": SendBackendRequestPolicy,
}


def test_policy_name_to_class_exists_and_is_dict():
    """Verify that the POLICY_NAME_TO_CLASS registry exists and is a dictionary."""
    assert isinstance(POLICY_NAME_TO_CLASS, dict)


def test_policy_name_to_class_contains_expected_policies():
    """Verify that the registry contains exactly the expected policy names and classes."""
    # Check if all expected keys are present
    for name, expected_class in EXPECTED_POLICY_MAPPINGS.items():
        assert name in POLICY_NAME_TO_CLASS
        assert POLICY_NAME_TO_CLASS[name] == expected_class
        assert issubclass(POLICY_NAME_TO_CLASS[name], ControlPolicy)
        assert inspect.isclass(POLICY_NAME_TO_CLASS[name])
