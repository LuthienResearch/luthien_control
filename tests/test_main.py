"""Unit tests for __main__.py."""

import os
from unittest.mock import patch

import pytest

# We need to import main *after* patching


@patch.dict(os.environ, {"OPENAI_API_KEY": "test_key", "LUTHIEN_DB_URL": "test_db", "LOG_LEVEL": "info"}, clear=True)
@patch("uvicorn.run")
@patch("luthien_control.logging.db_logger.DBLogger")  # Mock DBLogger to avoid actual DB connection
@patch("luthien_control.logging.file_logging.FileLogManager")  # Mock FileLogManager
@patch("luthien_control.policies.manager.PolicyManager")  # Mock PolicyManager
@patch("luthien_control.__main__.app")  # Patch app where it is used in __main__
@patch("luthien_control.proxy.server.config")  # Mock the config object
def test_main_default_config(mock_config, mock_app, mock_policy_mgr, mock_file_mgr, mock_db_logger, mock_run):
    """Test main function with default configuration from environment."""
    # Set necessary config values that are accessed during import/setup
    mock_config.target_url = "default_target"
    mock_config.api_key = "default_key"

    from luthien_control.__main__ import main

    main()

    # Check if DBLogger was initialized with LUTHIEN_DB_URL
    # mock_db_logger.assert_called_once_with("test_db") # Incorrect: main() doesn't init DBLogger
    # Check uvicorn.run was called with default host/port
    mock_run.assert_called_once_with(
        mock_app,  # Check it uses the imported app
        host="0.0.0.0",
        port=8000,
        log_level="info",  # Default log level
    )


@patch.dict(os.environ, {"HOST": "localhost", "PORT": "9000", "LOG_LEVEL": "debug"}, clear=True)
@patch("uvicorn.run")
@patch("luthien_control.logging.db_logger.DBLogger")
@patch("luthien_control.logging.file_logging.FileLogManager")
@patch("luthien_control.policies.manager.PolicyManager")
@patch("luthien_control.__main__.app")  # Patch app where it is used in __main__
@patch("luthien_control.proxy.server.config")
def test_main_custom_config(mock_config, mock_app, mock_policy_mgr, mock_file_mgr, mock_db_logger, mock_run):
    """Test main function with custom configuration from environment."""
    mock_config.target_url = "custom_target"
    mock_config.api_key = "custom_key"

    # Set LUTHIEN_DB_URL if needed, otherwise db logger won't be mocked correctly
    os.environ["LUTHIEN_DB_URL"] = "custom_db"  # Need this for DBLogger mock call check

    from luthien_control.__main__ import main

    main()

    # mock_db_logger.assert_called_once_with("custom_db") # Incorrect: main() doesn't init DBLogger
    mock_run.assert_called_once_with(
        mock_app,
        host="localhost",
        port=9000,
        log_level="debug",  # Check custom log level
    )


@patch.dict(os.environ, {"PORT": "invalid"}, clear=True)
@patch("luthien_control.logging.db_logger.DBLogger")
@patch("luthien_control.logging.file_logging.FileLogManager")
@patch("luthien_control.policies.manager.PolicyManager")
@patch("luthien_control.proxy.server.config")
def test_main_invalid_port(mock_config, mock_policy_mgr, mock_file_mgr, mock_db_logger):
    """Test main function raises ValueError for invalid PORT."""
    mock_config.target_url = "any"
    mock_config.api_key = "any"
    os.environ["LUTHIEN_DB_URL"] = "any_db"

    from luthien_control.__main__ import main

    with pytest.raises(ValueError, match="Invalid PORT value: invalid"):
        main()
