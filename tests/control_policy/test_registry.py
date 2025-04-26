import inspect
from typing import Dict, Type

# Import the classes directly for comparison
from luthien_control.control_policy.add_api_key_header import AddApiKeyHeaderPolicy
from luthien_control.control_policy.client_api_key_auth import ClientApiKeyAuthPolicy
from luthien_control.control_policy.compound_policy import CompoundPolicy
from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.registry import POLICY_CLASS_TO_NAME, POLICY_NAME_TO_CLASS
from luthien_control.control_policy.send_backend_request import SendBackendRequestPolicy

# Define the expected mappings for verification
EXPECTED_POLICY_MAPPINGS: Dict[str, Type[ControlPolicy]] = {
    "AddApiKeyHeader": AddApiKeyHeaderPolicy,
    "ClientApiKeyAuth": ClientApiKeyAuthPolicy,
    "CompoundPolicy": CompoundPolicy,
    "SendBackendRequest": SendBackendRequestPolicy,
}


def test_policy_name_to_class_exists_and_is_dict():
    """Verify that the POLICY_NAME_TO_CLASS registry exists and is a dictionary."""
    assert isinstance(POLICY_NAME_TO_CLASS, dict)


def test_policy_name_to_class_contains_expected_policies():
    """Verify that the registry contains exactly the expected policy names and classes."""
    # Check if all expected keys are present
    assert set(POLICY_NAME_TO_CLASS.keys()) == set(EXPECTED_POLICY_MAPPINGS.keys())

    # Check if the classes match for each key
    for name, expected_class in EXPECTED_POLICY_MAPPINGS.items():
        assert name in POLICY_NAME_TO_CLASS
        assert POLICY_NAME_TO_CLASS[name] == expected_class
        assert issubclass(POLICY_NAME_TO_CLASS[name], ControlPolicy)
        assert inspect.isclass(POLICY_NAME_TO_CLASS[name])


def test_policy_class_to_name_is_consistent():
    """Verify that the reverse mapping POLICY_CLASS_TO_NAME is consistent."""
    assert isinstance(POLICY_CLASS_TO_NAME, dict)
    assert len(POLICY_CLASS_TO_NAME) == len(POLICY_NAME_TO_CLASS)

    for name, policy_class in POLICY_NAME_TO_CLASS.items():
        assert policy_class in POLICY_CLASS_TO_NAME
        assert POLICY_CLASS_TO_NAME[policy_class] == name
