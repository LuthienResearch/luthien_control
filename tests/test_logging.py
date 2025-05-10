import logging
import sys
from unittest.mock import MagicMock, patch

import pytest
from luthien_control.core.logging import (
    DEFAULT_LOG_LEVEL,
    LOG_FORMAT,
    NOISY_LIBRARIES,
    setup_logging,
)


# Ensure clean logging state between tests
@pytest.fixture(autouse=True)
def reset_logging():
    logging.shutdown()
    # Reset handlers of the root logger
    root = logging.getLogger()
    if root.hasHandlers():
        root.handlers.clear()


@patch("luthien_control.core.logging.Settings")
@patch("luthien_control.core.logging.logging.basicConfig")
@patch("luthien_control.core.logging.logging.getLogger")
def test_setup_logging_default_level(mock_get_logger: MagicMock, mock_basic_config: MagicMock, MockSettings: MagicMock):
    """Test setup_logging uses DEFAULT_LOG_LEVEL when settings provide None or default."""
    # Arrange
    mock_settings_instance = MockSettings.return_value
    mock_settings_instance.get_log_level.return_value = DEFAULT_LOG_LEVEL
    mock_logger_instance = MagicMock()
    mock_get_logger.return_value = mock_logger_instance

    # Act
    setup_logging()

    # Assert
    mock_settings_instance.get_log_level.assert_called_once_with(default=DEFAULT_LOG_LEVEL)
    mock_basic_config.assert_called_once_with(level=logging.INFO, format=LOG_FORMAT, stream=sys.stderr)
    assert mock_get_logger.call_count >= len(NOISY_LIBRARIES) + 1  # +1 for the config log
    for lib_name in NOISY_LIBRARIES:
        mock_get_logger.assert_any_call(lib_name)
        # Check setLevel was called on the logger returned for the lib_name
        logger_mock = mock_get_logger(lib_name)
        logger_mock.setLevel.assert_called_with(logging.WARNING)

    # Check the final confirmation log
    mock_get_logger.assert_any_call("luthien_control.core.logging")
    config_logger_mock = mock_get_logger("luthien_control.core.logging")
    config_logger_mock.info.assert_called_once_with(f"Logging configured with level {DEFAULT_LOG_LEVEL}.")


@patch("luthien_control.core.logging.Settings")
@patch("luthien_control.core.logging.logging.basicConfig")
@patch("luthien_control.core.logging.logging.getLogger")
def test_setup_logging_specific_level(
    mock_get_logger: MagicMock, mock_basic_config: MagicMock, MockSettings: MagicMock
):
    """Test setup_logging uses the level provided by settings."""
    # Arrange
    log_level_name = "DEBUG"
    mock_settings_instance = MockSettings.return_value
    mock_settings_instance.get_log_level.return_value = log_level_name
    mock_logger_instance = MagicMock()
    mock_get_logger.return_value = mock_logger_instance

    # Act
    setup_logging()

    # Assert
    mock_settings_instance.get_log_level.assert_called_once_with(default=DEFAULT_LOG_LEVEL)
    mock_basic_config.assert_called_once_with(level=logging.DEBUG, format=LOG_FORMAT, stream=sys.stderr)
    # Check the final confirmation log
    config_logger_mock = mock_get_logger("luthien_control.core.logging")
    config_logger_mock.info.assert_called_once_with(f"Logging configured with level {log_level_name}.")


@patch("luthien_control.core.logging.Settings")
@patch("luthien_control.core.logging.logging.basicConfig")
@patch("luthien_control.core.logging.logging.getLogger")
@patch("luthien_control.core.logging.print")  # Mock print to check warning
def test_setup_logging_invalid_level(
    mock_print: MagicMock, mock_get_logger: MagicMock, mock_basic_config: MagicMock, MockSettings: MagicMock
):
    """Test setup_logging defaults to INFO and warns on invalid level."""
    # Arrange
    invalid_level = "INVALID_LEVEL"
    mock_settings_instance = MockSettings.return_value
    mock_settings_instance.get_log_level.return_value = invalid_level
    mock_logger_instance = MagicMock()
    mock_get_logger.return_value = mock_logger_instance

    # Act
    setup_logging()

    # Assert
    mock_settings_instance.get_log_level.assert_called_once_with(default=DEFAULT_LOG_LEVEL)
    # Check that print was called with the warning message
    mock_print.assert_called_once()
    args, kwargs = mock_print.call_args
    assert f"WARNING: Invalid LOG_LEVEL '{invalid_level}'" in args[0]
    assert kwargs.get("file") == sys.stderr
    # Check that basicConfig was called with the default level (INFO)
    mock_basic_config.assert_called_once_with(level=logging.INFO, format=LOG_FORMAT, stream=sys.stderr)
    # Check the final confirmation log used the default level name
    config_logger_mock = mock_get_logger("luthien_control.core.logging")
    config_logger_mock.info.assert_called_once_with(f"Logging configured with level {DEFAULT_LOG_LEVEL}.")
