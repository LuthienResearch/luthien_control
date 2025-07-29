"""Tests that OpenAI-specific policies are no-ops for raw requests."""

from unittest.mock import MagicMock

import pytest
from luthien_control.control_policy.add_api_key_header import AddApiKeyHeaderPolicy
from luthien_control.control_policy.add_api_key_header_from_env import AddApiKeyHeaderFromEnvPolicy
from luthien_control.control_policy.leaked_api_key_detection import LeakedApiKeyDetectionPolicy
from luthien_control.control_policy.model_name_replacement import ModelNameReplacementPolicy
from luthien_control.core.raw_request import RawRequest
from luthien_control.core.request_type import RequestType
from luthien_control.core.transaction import Transaction


@pytest.mark.asyncio
class TestPolicyRawRequestNoop:
    """Test that OpenAI-specific policies are no-ops for raw requests."""

    async def test_add_api_key_header_policy_noop_for_raw(self):
        """Test AddApiKeyHeaderPolicy is no-op for raw requests."""
        raw_request = RawRequest(method="GET", path="v1/models", api_key="test-key")
        transaction = Transaction(raw_request=raw_request)
        original_request = transaction.raw_request

        policy = AddApiKeyHeaderPolicy()
        mock_container = MagicMock()
        mock_session = MagicMock()
        result = await policy.apply(transaction, mock_container, mock_session)

        assert result is transaction
        assert result.raw_request is original_request
        assert result.request_type == RequestType.RAW_PASSTHROUGH

    async def test_add_api_key_header_from_env_policy_noop_for_raw(self):
        """Test AddApiKeyHeaderFromEnvPolicy is no-op for raw requests."""
        raw_request = RawRequest(method="GET", path="v1/models", api_key="test-key")
        transaction = Transaction(raw_request=raw_request)
        original_request = transaction.raw_request

        policy = AddApiKeyHeaderFromEnvPolicy(api_key_env_var_name="TEST_API_KEY")
        mock_container = MagicMock()
        mock_session = MagicMock()
        result = await policy.apply(transaction, mock_container, mock_session)

        assert result is transaction
        assert result.raw_request is original_request
        assert result.request_type == RequestType.RAW_PASSTHROUGH

    async def test_leaked_api_key_detection_policy_noop_for_raw(self):
        """Test LeakedApiKeyDetectionPolicy is no-op for raw requests."""
        raw_request = RawRequest(method="GET", path="v1/models", api_key="test-key")
        transaction = Transaction(raw_request=raw_request)
        original_request = transaction.raw_request

        policy = LeakedApiKeyDetectionPolicy()
        mock_container = MagicMock()
        mock_session = MagicMock()
        result = await policy.apply(transaction, mock_container, mock_session)

        assert result is transaction
        assert result.raw_request is original_request
        assert result.request_type == RequestType.RAW_PASSTHROUGH

    async def test_model_name_replacement_policy_noop_for_raw(self):
        """Test ModelNameReplacementPolicy is no-op for raw requests."""
        raw_request = RawRequest(method="GET", path="v1/models", api_key="test-key")
        transaction = Transaction(raw_request=raw_request)
        original_request = transaction.raw_request

        policy = ModelNameReplacementPolicy(model_mapping={"fake-model": "real-model"})
        mock_container = MagicMock()
        mock_session = MagicMock()
        result = await policy.apply(transaction, mock_container, mock_session)

        assert result is transaction
        assert result.raw_request is original_request
        assert result.request_type == RequestType.RAW_PASSTHROUGH
