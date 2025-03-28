"""Test the main module."""
import os
from unittest.mock import patch, MagicMock

def test_main_default_config():
    """Test main function with default configuration."""
    mock_logger = MagicMock()
    with patch('uvicorn.run') as mock_run, \
         patch('luthien_control.logging.api_logger.APILogger', return_value=mock_logger) as mock_api_logger:
        from luthien_control.__main__ import main
        main()
        mock_run.assert_called_once_with(
            mock_run.call_args[0][0],  # app
            host="0.0.0.0",
            port=8000,
            log_level="info"
        )

def test_main_custom_config():
    """Test main function with custom configuration."""
    env_vars = {
        "HOST": "localhost",
        "PORT": "9000"
    }
    mock_logger = MagicMock()
    with patch.dict(os.environ, env_vars), \
         patch('uvicorn.run') as mock_run, \
         patch('luthien_control.logging.api_logger.APILogger', return_value=mock_logger) as mock_api_logger:
        from luthien_control.__main__ import main
        main()
        mock_run.assert_called_once_with(
            mock_run.call_args[0][0],  # app
            host="localhost",
            port=9000,
            log_level="info"
        ) 