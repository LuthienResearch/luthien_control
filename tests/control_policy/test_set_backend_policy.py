from unittest.mock import Mock

import pytest
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.control_policy.set_backend_policy import SetBackendPolicy
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.transaction import Transaction
from sqlalchemy.ext.asyncio import AsyncSession


class TestSetBackendPolicy:
    """Test cases for SetBackendPolicy."""

    def test_init_with_name_and_backend_url(self):
        """Test initialization with name and backend_url."""
        policy = SetBackendPolicy(name="test_policy", backend_url="https://api.example.com")
        assert policy.name == "test_policy"
        assert policy.backend_url == "https://api.example.com"

    def test_init_with_defaults(self):
        """Test initialization with default values."""
        policy = SetBackendPolicy()
        assert policy.name is None
        assert policy.backend_url is None

    def test_init_with_only_name(self):
        """Test initialization with only name."""
        policy = SetBackendPolicy(name="test_policy")
        assert policy.name == "test_policy"
        assert policy.backend_url is None

    def test_init_with_only_backend_url(self):
        """Test initialization with only backend_url."""
        policy = SetBackendPolicy(backend_url="https://api.example.com")
        assert policy.name is None
        assert policy.backend_url == "https://api.example.com"

    @pytest.mark.asyncio
    async def test_apply_with_backend_url(self):
        """Test apply method when backend_url is set."""
        policy = SetBackendPolicy(backend_url="https://api.example.com")

        # Create mock objects
        transaction = Mock(spec=Transaction)
        transaction.request = Mock()
        container = Mock(spec=DependencyContainer)
        session = Mock(spec=AsyncSession)

        # Apply the policy
        result = await policy.apply(transaction, container, session)

        # Verify the backend URL was set
        assert transaction.request.api_endpoint == "https://api.example.com"
        assert result is transaction

    @pytest.mark.asyncio
    async def test_apply_without_backend_url(self):
        """Test apply method when backend_url is None."""
        policy = SetBackendPolicy(backend_url=None)

        # Create mock objects
        transaction = Mock(spec=Transaction)
        transaction.request = Mock()
        transaction.request.api_endpoint = "original_endpoint"
        container = Mock(spec=DependencyContainer)
        session = Mock(spec=AsyncSession)

        # Apply the policy
        result = await policy.apply(transaction, container, session)

        # Verify the backend URL was not modified
        assert transaction.request.api_endpoint == "original_endpoint"
        assert result is transaction

    def test_get_policy_specific_config(self):
        """Test _get_policy_specific_config method."""
        policy = SetBackendPolicy(backend_url="https://api.example.com")
        config = policy._get_policy_specific_config()

        assert isinstance(config, dict)
        assert config["backend_url"] == "https://api.example.com"

    def test_get_policy_specific_config_none(self):
        """Test _get_policy_specific_config method with None backend_url."""
        policy = SetBackendPolicy(backend_url=None)
        config = policy._get_policy_specific_config()

        assert isinstance(config, dict)
        assert config["backend_url"] is None

    def test_from_serialized_with_name_and_backend_url(self):
        """Test from_serialized with name and backend_url."""
        config = SerializableDict(name="test_policy", backend_url="https://api.example.com")
        policy = SetBackendPolicy.from_serialized(config)

        assert policy.name == "test_policy"
        assert policy.backend_url == "https://api.example.com"

    def test_from_serialized_with_empty_config(self):
        """Test from_serialized with empty config."""
        config = SerializableDict()
        policy = SetBackendPolicy.from_serialized(config)

        assert policy.name is None
        assert policy.backend_url is None

    def test_from_serialized_with_non_string_name(self):
        """Test from_serialized with non-string name."""
        config = SerializableDict(name=123, backend_url="https://api.example.com")
        policy = SetBackendPolicy.from_serialized(config)

        assert policy.name is None  # Non-string name should be converted to None
        assert policy.backend_url == "https://api.example.com"

    def test_from_serialized_with_non_string_backend_url(self):
        """Test from_serialized with non-string backend_url."""
        config = SerializableDict(name="test_policy", backend_url=123)
        policy = SetBackendPolicy.from_serialized(config)

        assert policy.name == "test_policy"
        assert policy.backend_url is None  # Non-string backend_url should be converted to None

    def test_from_serialized_with_all_non_strings(self):
        """Test from_serialized with all non-string values."""
        config = SerializableDict(name=123, backend_url=456)
        policy = SetBackendPolicy.from_serialized(config)

        assert policy.name is None
        assert policy.backend_url is None
