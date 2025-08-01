"""Unit tests for proxy debugging utilities."""

from datetime import UTC, datetime
from unittest.mock import patch

from luthien_control.core.logging import create_debug_response


class TestCreateDebugResponse:
    """Test cases for the create_debug_response function."""

    def test_create_debug_response_basic(self):
        """Test basic response creation without debug info."""
        response = create_debug_response(
            status_code=400, message="Test error", transaction_id="test-123", include_debug_info=False
        )

        assert response == {"detail": "Test error", "transaction_id": "test-123"}

    def test_create_debug_response_with_debug_info_and_details(self):
        """Test response creation with debug info and details (lines 143-146)."""
        test_details = {"key": "value", "number": 42}

        with patch("luthien_control.core.logging.datetime") as mock_datetime:
            mock_now = datetime(2023, 1, 1, 0, 0, 0, tzinfo=UTC)
            mock_datetime.now.return_value = mock_now
            mock_datetime.UTC = UTC

            response = create_debug_response(
                status_code=500,
                message="Internal error",
                transaction_id="test-456",
                details=test_details,
                include_debug_info=True,
            )

        # The debug field should contain a string representation of the debug dict
        assert response["detail"] == "Internal error"
        assert response["transaction_id"] == "test-456"
        assert "debug" in response
        assert "timestamp" in response["debug"]
        assert "key" in response["debug"]
        assert "number" in response["debug"]

    def test_create_debug_response_with_debug_info_no_details(self):
        """Test response creation with debug info enabled but no details."""
        response = create_debug_response(
            status_code=404, message="Not found", transaction_id="test-789", details=None, include_debug_info=True
        )

        assert response == {"detail": "Not found", "transaction_id": "test-789"}
        assert "debug" not in response

    def test_create_debug_response_with_debug_info_empty_details(self):
        """Test response creation with debug info enabled but empty details."""
        response = create_debug_response(
            status_code=422, message="Validation error", transaction_id="test-000", details={}, include_debug_info=True
        )

        assert response == {"detail": "Validation error", "transaction_id": "test-000"}
        assert "debug" not in response

    def test_create_debug_response_debug_disabled_with_details(self):
        """Test response creation with debug info disabled but details provided."""
        test_details = {"error": "detailed error info"}

        response = create_debug_response(
            status_code=403,
            message="Forbidden",
            transaction_id="test-111",
            details=test_details,
            include_debug_info=False,
        )

        assert response == {"detail": "Forbidden", "transaction_id": "test-111"}
        assert "debug" not in response

    def test_create_debug_response_default_parameters(self):
        """Test response creation with default parameters."""
        test_details = {"context": "test context"}

        with patch("luthien_control.core.logging.datetime") as mock_datetime:
            mock_now = datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC)
            mock_datetime.now.return_value = mock_now
            mock_datetime.UTC = UTC

            response = create_debug_response(
                status_code=200,
                message="Success",
                transaction_id="test-default",
                details=test_details,
                # include_debug_info defaults to True
            )

        # The debug field should contain a string representation of the debug dict
        assert response["detail"] == "Success"
        assert response["transaction_id"] == "test-default"
        assert "debug" in response
        assert "timestamp" in response["debug"]
        assert "context" in response["debug"]
