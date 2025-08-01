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

    # Test that handler is configured correctly
    handler = root_logger.handlers[0]
    assert isinstance(handler, logging.StreamHandler)
    # In test environment, stream might be wrapped by pytest
    # Just verify it's a StreamHandler pointing to some stream


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

    # Test that handler is configured correctly
    handler = root_logger.handlers[0]
    assert isinstance(handler, logging.StreamHandler)
    # In test environment, stream might be wrapped by pytest
    # Just verify it's a StreamHandler pointing to some stream


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

    # Test that handler is configured correctly
    handler = root_logger.handlers[0]
    assert isinstance(handler, logging.StreamHandler)
    # In test environment, stream might be wrapped by pytest
    # Just verify it's a StreamHandler pointing to some stream
