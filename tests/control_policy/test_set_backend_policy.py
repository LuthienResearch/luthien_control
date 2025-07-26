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
        assert policy.name == "SetBackendPolicy"  # Now uses default class name
        assert policy.backend_url is None

    def test_init_with_only_name(self):
        """Test initialization with only name."""
        policy = SetBackendPolicy(name="test_policy")
        assert policy.name == "test_policy"
        assert policy.backend_url is None

    def test_init_with_only_backend_url(self):
        """Test initialization with only backend_url."""
        policy = SetBackendPolicy(backend_url="https://api.example.com")
        assert policy.name == "SetBackendPolicy"  # Now uses default class name
        assert policy.backend_url == "https://api.example.com"

    @pytest.mark.asyncio
    async def test_apply_with_backend_url(self):
        """Test apply method when backend_url is set."""
        policy = SetBackendPolicy(backend_url="https://api.example.com/")

        # Create mock objects
        transaction = Mock(spec=Transaction)
        transaction.openai_request = Mock()
        transaction.openai_request.api_endpoint = "chat/completions"  # Initial path
        container = Mock(spec=DependencyContainer)
        session = Mock(spec=AsyncSession)

        # Apply the policy
        result = await policy.apply(transaction, container, session)

        # Verify the backend URL was set (without combining with the original path)
        assert transaction.openai_request.api_endpoint == "https://api.example.com/"
        assert result is transaction

    @pytest.mark.asyncio
    async def test_apply_without_backend_url(self):
        """Test apply method when backend_url is None."""
        policy = SetBackendPolicy(backend_url=None)

        # Create mock objects
        transaction = Mock(spec=Transaction)
        transaction.openai_request = Mock()
        transaction.openai_request.api_endpoint = "chat/completions"  # Initial path
        container = Mock(spec=DependencyContainer)
        session = Mock(spec=AsyncSession)

        # Apply the policy
        result = await policy.apply(transaction, container, session)

        # Verify the backend URL was not modified
        assert transaction.openai_request.api_endpoint == "chat/completions"
        assert result is transaction

    @pytest.mark.asyncio
    async def test_apply_url_joining_scenarios(self):
        """Test URL joining with different base URL and path combinations."""
        test_cases = [
            # (base_url, original_path, expected_result)
            ("https://api.example.com/", "chat/completions", "https://api.example.com/"),
            ("https://api.example.com", "chat/completions", "https://api.example.com"),
            ("https://api.example.com/", "chat/completions", "https://api.example.com/"),
            ("https://api.example.com", "chat/completions", "https://api.example.com"),
        ]

        for base_url, original_path, expected_result in test_cases:
            policy = SetBackendPolicy(backend_url=base_url)

            # Create mock objects
            transaction = Mock(spec=Transaction)
            transaction.openai_request = Mock()
            transaction.openai_request.api_endpoint = original_path
            container = Mock(spec=DependencyContainer)
            session = Mock(spec=AsyncSession)

            # Apply the policy
            result = await policy.apply(transaction, container, session)

            # Verify the URL was joined correctly
            assert transaction.openai_request.api_endpoint == expected_result, f"Failed for {base_url} + {original_path}"
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

        assert policy.name == "SetBackendPolicy"  # Now uses default class name
        assert policy.backend_url is None

    def test_from_serialized_with_non_string_name_raises_validation_error(self):
        """Test from_serialized with non-string name raises ValidationError."""
        config = SerializableDict(name=123, backend_url="https://api.example.com")
        with pytest.raises(Exception):  # Pydantic will raise ValidationError for invalid types
            SetBackendPolicy.from_serialized(config)

    def test_from_serialized_with_non_string_backend_url_raises_validation_error(self):
        """Test from_serialized with non-string backend_url raises ValidationError."""
        config = SerializableDict(name="test_policy", backend_url=123)
        with pytest.raises(Exception):  # Pydantic will raise ValidationError for invalid types
            SetBackendPolicy.from_serialized(config)

    def test_from_serialized_with_all_non_strings_raises_validation_error(self):
        """Test from_serialized with all non-string values raises ValidationError."""
        config = SerializableDict(name=123, backend_url=456)
        with pytest.raises(Exception):  # Pydantic will raise ValidationError for invalid types
            SetBackendPolicy.from_serialized(config)
