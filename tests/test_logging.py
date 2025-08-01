import logging
from unittest.mock import patch

import pytest
from luthien_control.core.logging import (
    DEFAULT_LOG_LEVEL,
    NOISY_LIBRARIES,
    setup_logging,
)


# Ensure clean logging state between tests
@pytest.fixture(autouse=True)
def reset_logging():
    # Force reconfiguration by removing existing handlers
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    root.handlers.clear()

    yield

    # Clean up after test
    root.handlers.clear()
    root.handlers.extend(original_handlers)


@patch("luthien_control.core.logging.Settings")
def test_setup_logging_default_level(MockSettings):
    """Test setup_logging configures logging with default level and works correctly."""
    # Arrange
    mock_settings_instance = MockSettings.return_value
    mock_settings_instance.get_log_level.return_value = DEFAULT_LOG_LEVEL

    # Act
    setup_logging()

    # Assert
    root_logger = logging.getLogger()
    assert root_logger.level == logging.INFO
    assert len(root_logger.handlers) >= 1  # At least console handler

    # Test that noisy libraries are suppressed
    for lib_name in NOISY_LIBRARIES:
        lib_logger = logging.getLogger(lib_name)
        assert lib_logger.level == logging.WARNING

    assert isinstance(root_logger.handlers[0], logging.StreamHandler)


@patch("luthien_control.core.logging.Settings")
def test_setup_logging_specific_level(MockSettings):
    """Test setup_logging uses the level provided by settings."""
    # Arrange
    log_level_name = "DEBUG"
    mock_settings_instance = MockSettings.return_value
    mock_settings_instance.get_log_level.return_value = log_level_name

    # Clear any existing handlers to force reconfiguration
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    # Act
    setup_logging()

    # Assert
    root_logger = logging.getLogger()
    assert root_logger.level == logging.DEBUG

    assert isinstance(root_logger.handlers[0], logging.StreamHandler)


@patch("luthien_control.core.logging.Settings")
def test_setup_logging_invalid_level(MockSettings, capsys):
    """Test setup_logging defaults to INFO and warns on invalid level."""
    # Arrange
    invalid_level = "INVALID_LEVEL"
    mock_settings_instance = MockSettings.return_value
    mock_settings_instance.get_log_level.return_value = invalid_level

    # Clear any existing handlers to force reconfiguration
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    # Act
    setup_logging()

    # Assert
    captured = capsys.readouterr()
    assert f"WARNING: Invalid LOG_LEVEL '{invalid_level}'" in captured.err

    # Should fall back to default level
    root_logger = logging.getLogger()
    assert root_logger.level == logging.INFO

    assert isinstance(root_logger.handlers[0], logging.StreamHandler)


class TestCreateDebugResponse:
    """Test cases for the create_debug_response function."""

    def test_create_debug_response_basic(self):
        """Test basic response creation without debug info."""
        from luthien_control.core.logging import create_debug_response

        response = create_debug_response(
            status_code=400, message="Test error", transaction_id="test-123", include_debug_info=False
        )

        assert response == {"detail": "Test error", "transaction_id": "test-123"}

    def test_create_debug_response_with_debug_info_and_details(self):
        """Test response creation with debug info and details."""
        from datetime import UTC, datetime

        from luthien_control.core.logging import create_debug_response

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

        assert response["detail"] == "Internal error"
        assert response["transaction_id"] == "test-456"
        assert "debug" in response
        assert all(key in response["debug"] for key in ["timestamp", "key", "number"])

    def test_create_debug_response_with_debug_info_no_details(self):
        """Test response creation with debug info enabled but no details."""
        from luthien_control.core.logging import create_debug_response

        response = create_debug_response(
            status_code=404, message="Not found", transaction_id="test-789", details=None, include_debug_info=True
        )

        assert response == {"detail": "Not found", "transaction_id": "test-789"}
        assert "debug" not in response

    def test_create_debug_response_with_debug_info_empty_details(self):
        """Test response creation with debug info enabled but empty details."""
        from luthien_control.core.logging import create_debug_response

        response = create_debug_response(
            status_code=422, message="Validation error", transaction_id="test-000", details={}, include_debug_info=True
        )

        assert response == {"detail": "Validation error", "transaction_id": "test-000"}
        assert "debug" not in response

    def test_create_debug_response_debug_disabled_with_details(self):
        """Test response creation with debug info disabled but details provided."""
        from luthien_control.core.logging import create_debug_response

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
        from datetime import UTC, datetime

        from luthien_control.core.logging import create_debug_response

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

        assert response["detail"] == "Success"
        assert response["transaction_id"] == "test-default"
        assert "debug" in response
        assert all(key in response["debug"] for key in ["timestamp", "context"])
