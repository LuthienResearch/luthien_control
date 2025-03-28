"""Test the run module."""
import os
from unittest.mock import patch
from luthien_control.run import main

def test_main_default_config():
    """Test main function with default configuration."""
    with patch('uvicorn.run') as mock_run:
        main()
        mock_run.assert_called_once_with(
            "luthien_control.proxy.server:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            reload_dirs=["luthien_control"],
            log_level="debug"
        )

def test_main_custom_config():
    """Test main function with custom configuration."""
    env_vars = {
        "LUTHIEN_HOST": "localhost",
        "LUTHIEN_PORT": "9000",
        "LUTHIEN_RELOAD": "false"
    }
    with patch.dict(os.environ, env_vars), patch('uvicorn.run') as mock_run:
        main()
        mock_run.assert_called_once_with(
            "luthien_control.proxy.server:app",
            host="localhost",
            port=9000,
            reload=False,
            reload_dirs=["luthien_control"],
            log_level="debug"
        ) 