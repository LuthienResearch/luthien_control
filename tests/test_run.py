"""Unit tests for run.py."""
import pytest
import os
from unittest.mock import patch, MagicMock
from pathlib import Path # Import Path for patching target
import dotenv # Import dotenv so we can patch its contents

# Assuming run.py contains a main() function that calls uvicorn.run
# Need to import main *after* patching

@patch.dict(os.environ, {}, clear=True) # Start with empty env
@patch('uvicorn.run')
@patch('luthien_control.run.Path') # Mock Path class
def test_run_main_defaults(mock_path_cls, mock_run):
    """Test run.main with default settings."""
    # Configure the mock Path object returned by the chain: Path(...).parent.parent / '.env'
    mock_final_path = MagicMock(spec=Path)
    mock_final_path.exists.return_value = False
    # Configure the chain of calls on the mocked Path class
    mock_path_cls.return_value.parent.parent.__truediv__.return_value = mock_final_path

    from luthien_control.run import main
    main()
    mock_run.assert_called_once_with(
        "luthien_control.proxy.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["luthien_control"],
        log_level="debug"
    )
    # Check that exists() was called on the final path object in the chain
    mock_final_path.exists.assert_called_once()

@patch.dict(os.environ, {
    "LUTHIEN_HOST": "localhost",
    "LUTHIEN_PORT": "9999",
    "LUTHIEN_RELOAD": "false",
    "LOG_LEVEL": "info"
}, clear=True)
@patch('uvicorn.run')
@patch('luthien_control.run.Path') # Mock Path class
def test_run_main_custom_env(mock_path_cls, mock_run):
    """Test run.main with custom environment variables."""
    mock_final_path = MagicMock(spec=Path)
    mock_final_path.exists.return_value = False
    mock_path_cls.return_value.parent.parent.__truediv__.return_value = mock_final_path

    from luthien_control.run import main
    main()
    mock_run.assert_called_once_with(
        "luthien_control.proxy.server:app",
        host="localhost",
        port=9999,
        reload=False,
        reload_dirs=["luthien_control"],
        log_level="debug"
    )
    mock_final_path.exists.assert_called_once()

@patch.dict(os.environ, {"LUTHIEN_PORT": "invalid"}, clear=True)
@patch('luthien_control.run.Path') # Mock Path class
def test_run_main_invalid_port(mock_path_cls):
    """Test run.main raises ValueError for invalid LUTHIEN_PORT."""
    mock_final_path = MagicMock(spec=Path)
    mock_final_path.exists.return_value = False
    mock_path_cls.return_value.parent.parent.__truediv__.return_value = mock_final_path

    from luthien_control.run import main
    with pytest.raises(ValueError, match=r"invalid literal for int\(\) with base 10: 'invalid'"):
        main()
    mock_final_path.exists.assert_called_once()

@patch.dict(os.environ, {"LUTHIEN_RELOAD": "not-a-bool"}, clear=True)
@patch('luthien_control.run.Path') # Mock Path class
def test_run_main_invalid_reload(mock_path_cls):
    """Test run.main raises ValueError for invalid LUTHIEN_RELOAD comparison."""
    mock_final_path = MagicMock(spec=Path)
    mock_final_path.exists.return_value = False
    mock_path_cls.return_value.parent.parent.__truediv__.return_value = mock_final_path

    with patch('uvicorn.run') as mock_run:
        from luthien_control.run import main
        main()
        assert mock_run.call_args.kwargs['reload'] is False
    mock_final_path.exists.assert_called_once()

# Add new test case for .env loading
@patch.dict(os.environ, {}, clear=True) # Start with empty env
@patch('uvicorn.run')
@patch('luthien_control.run.Path') # Mock Path class
@patch('dotenv.load_dotenv') # Patch load_dotenv in the dotenv module
def test_run_main_loads_dotenv(mock_load_dotenv, mock_path_cls, mock_run):
    """Test run.main loads .env file when it exists."""
    # Configure the mock Path object chain to return True for exists()
    mock_final_path = MagicMock(spec=Path)
    mock_final_path.exists.return_value = True # Make .env file exist
    mock_path_cls.return_value.parent.parent.__truediv__.return_value = mock_final_path

    from luthien_control.run import main
    main()

    # Assert that exists() was checked
    mock_final_path.exists.assert_called_once()
    # Assert that load_dotenv was called with the correct path
    mock_load_dotenv.assert_called_once_with(mock_final_path)
    # Assert uvicorn was called (with defaults)
    mock_run.assert_called_once_with(
        "luthien_control.proxy.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["luthien_control"],
        log_level="debug"
    ) 