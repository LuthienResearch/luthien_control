import logging
from unittest.mock import MagicMock, patch

import pytest
from luthien_control.core.logging import (
    DEFAULT_LOG_LEVEL,
    _get_loki_handler,
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


def test_get_loki_handler_success():
    """Test _get_loki_handler successfully creates handler when module is available."""
    mock_handler = MagicMock()
    with patch("logging_loki.LokiHandler", return_value=mock_handler) as MockLokiHandler:
        handler = _get_loki_handler("http://localhost:3100", "test_app")

        assert handler == mock_handler
        MockLokiHandler.assert_called_once_with(
            url="http://localhost:3100/loki/api/v1/push",
            tags={"application": "test_app", "environment": "development"},
            version="1",
        )
        # Verify setFormatter was called
        assert mock_handler.setFormatter.called
        assert mock_handler.setFormatter.call_count == 1


def test_get_loki_handler_import_error():
    """Test _get_loki_handler returns None when logging_loki is not available."""
    with patch("logging_loki.LokiHandler", side_effect=ImportError):
        handler = _get_loki_handler("http://localhost:3100")
        assert handler is None


def test_get_loki_handler_invalid_url():
    """Test _get_loki_handler returns None for invalid URLs."""
    with patch("logging_loki.LokiHandler"):
        # Invalid URL without scheme
        handler = _get_loki_handler("localhost:3100")
        assert handler is None

        # Empty URL
        handler = _get_loki_handler("")
        assert handler is None


def test_get_loki_handler_exception():
    """Test _get_loki_handler returns None on unexpected exceptions."""
    with patch("logging_loki.LokiHandler", side_effect=Exception("Test error")):
        handler = _get_loki_handler("http://localhost:3100")
        assert handler is None


@patch("luthien_control.core.logging.Settings")
@patch("os.getenv")
def test_setup_logging_with_loki(mock_getenv, MockSettings):
    """Test setup_logging configures Loki handler when LOKI_URL is set."""
    # Configure mocks
    mock_settings_instance = MockSettings.return_value
    mock_settings_instance.get_log_level.return_value = DEFAULT_LOG_LEVEL
    mock_getenv.side_effect = lambda key, default=None: "http://localhost:3100" if key == "LOKI_URL" else default

    mock_loki_handler = MagicMock()
    mock_loki_handler.level = logging.INFO  # Set a proper logging level
    with patch("luthien_control.core.logging._get_loki_handler", return_value=mock_loki_handler):
        setup_logging()

        # Verify Loki handler was added
        root_logger = logging.getLogger()
        assert mock_loki_handler in root_logger.handlers


def test_get_loki_handler_with_environment():
    """Test _get_loki_handler uses ENVIRONMENT env var for tags."""
    mock_handler = MagicMock()
    with patch("logging_loki.LokiHandler", return_value=mock_handler) as MockLokiHandler:

        def env_mock(k, d=None):
            return "production" if k == "ENVIRONMENT" else d

        with patch("os.getenv", side_effect=env_mock):
            handler = _get_loki_handler("http://localhost:3100", "test_app")

            assert handler == mock_handler
            MockLokiHandler.assert_called_once_with(
                url="http://localhost:3100/loki/api/v1/push",
                tags={"application": "test_app", "environment": "production"},
                version="1",
            )
