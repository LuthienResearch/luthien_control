"""Test file-based logging configuration."""

import json
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest

from luthien_control.logging.api_logger import (
    APILogger,  # Needed for type checking logger
)
from luthien_control.logging.file_logging import FileLogManager


@pytest.fixture
def tmp_log_dir(tmp_path):
    """Create a temporary directory for logs."""
    return tmp_path / "logs"


@pytest.fixture
def log_manager_real(tmp_log_dir):
    """Create a FileLogManager with a temporary directory for integration-like tests."""
    return FileLogManager(tmp_log_dir)


@pytest.fixture
def mock_path():
    """Fixture for a mocked Path object."""
    path_instance = Mock(spec=Path)
    path_instance.mkdir = Mock()
    path_instance.__truediv__ = Mock(return_value=path_instance)  # Mock path / 'filename'
    # Mock parent attribute for path.parent.mkdir calls
    mock_parent = Mock(spec=Path)
    mock_parent.mkdir = Mock()
    path_instance.parent = mock_parent
    return path_instance


@pytest.fixture
def log_manager_mocked(mock_path):
    """Fixture for FileLogManager with mocked Path."""
    # Pass the mock_path object directly to the constructor
    with patch("builtins.open", mock_open()) as mocked_file:
        manager = FileLogManager(mock_path)  # Use mock_path here
        # Store mock_open instance for assertions if needed
        manager.mocked_file = mocked_file
        yield manager


def test_log_manager_init(mock_path):
    """Test FileLogManager initialization with mocked Path."""
    # __init__ takes a Path object, doesn't create one.
    # It also doesn't call mkdir.
    manager = FileLogManager(mock_path)
    # Check base_dir is set correctly
    assert manager.base_dir == mock_path
    # Check _open_files is initialized
    assert manager._open_files == []


def test_ensure_log_dir(log_manager_real, tmp_log_dir):
    """Test log directory creation using real paths."""
    log_dir = log_manager_real.ensure_log_dir()
    assert log_dir == tmp_log_dir
    assert log_dir.exists()

    subdir = log_manager_real.ensure_log_dir("api")
    assert subdir == tmp_log_dir / "api"
    assert subdir.exists()


@patch("builtins.open", new_callable=mock_open)
def test_open_log_file(mock_open_func, log_manager_mocked, mock_path):
    """Test log file opening context manager with mocked Path and open."""
    file_path = "test.log"
    # Ensure the context manager yields a file-like object
    with log_manager_mocked.open_log_file(file_path) as f:
        f.write("test data")

    # Check Path / filename was called
    mock_path.__truediv__.assert_called_with(file_path)
    # Check parent directory was created
    mock_path.parent.mkdir.assert_called_once_with(parents=True, exist_ok=True)
    # Check file was opened with mocked open
    mock_open_func.assert_called_once_with(mock_path, "a")
    # Check data was written
    mock_open_func().write.assert_called_once_with("test data")


@patch("builtins.open", new_callable=mock_open)
@patch("luthien_control.logging.file_logging.APILogger")
def test_create_logger(mock_api_logger_cls, mock_open_func, log_manager_mocked, mock_path):
    """Test logger creation, mocking Path, open and APILogger."""
    logger_name = "api.log"
    mock_logger_instance = Mock(spec=APILogger)
    mock_api_logger_cls.return_value = mock_logger_instance

    logger = log_manager_mocked.create_logger(logger_name)

    # Check Path / filename was called
    mock_path.__truediv__.assert_called_with(logger_name)
    # Check parent directory was created
    mock_path.parent.mkdir.assert_called_once_with(parents=True, exist_ok=True)
    # Check file was opened
    mock_open_func.assert_called_once_with(mock_path, "a")
    # Check APILogger was instantiated with the write function
    mock_api_logger_cls.assert_called_once()
    assert callable(mock_api_logger_cls.call_args[0][0])  # Check first arg is callable (the write func)
    # Check the returned logger is the mocked instance
    assert logger == mock_logger_instance
    # Check the opened file handle was stored for later cleanup
    assert mock_open_func() in log_manager_mocked._open_files


# Test the actual file writing part of create_logger using the real FileLogManager
def test_create_logger_writes_json(log_manager_real, tmp_log_dir):
    """Test that the logger created by FileLogManager writes JSON lines."""
    logger = log_manager_real.create_logger("real_api.log")
    assert isinstance(logger, APILogger)

    log_entry_data = {"method": "GET", "url": "/test", "headers": {"Accept": "*/*"}}
    # Call a public logging method which will use the configured handler (write_json_line)
    logger.log_request(**log_entry_data)

    log_file = tmp_log_dir / "real_api.log"
    assert log_file.exists()
    with open(log_file, "r") as f:
        line = f.readline()
        # The logger adds type and timestamp
        logged_data = json.loads(line)
        assert logged_data["type"] == "request"
        assert logged_data["method"] == log_entry_data["method"]
        assert logged_data["url"] == log_entry_data["url"]
        assert "timestamp" in logged_data


# Test __del__ for cleanup - tricky to test reliably,
# but we can check if close is called on mocked file handles
@patch("builtins.open", new_callable=mock_open)
def test_manager_del_closes_files(mock_open_func, mock_path):
    """Test that the manager closes opened files on deletion."""
    mock_file_handle = mock_open_func()

    with patch("luthien_control.logging.file_logging.Path", return_value=mock_path):
        manager = FileLogManager("dummy")
        # Manually add a mock file handle like create_logger would
        manager._open_files.append(mock_file_handle)

        # Trigger __del__
        del manager

        # Check if close was called
        mock_file_handle.close.assert_called_once()


# Add the new test case after the existing __del__ test
@patch("builtins.open", new_callable=mock_open)
def test_manager_del_handles_close_error(mock_open_func, mock_path):
    """Test that __del__ handles errors when closing files."""
    mock_file_handle = mock_open_func()
    mock_file_handle.close.side_effect = IOError("Disk full")  # Simulate close error

    with patch("luthien_control.logging.file_logging.Path", return_value=mock_path):
        manager = FileLogManager("dummy")
        manager._open_files.append(mock_file_handle)

        # Trigger __del__ - assert it doesn't raise an exception
        try:
            del manager
        except Exception as e:
            pytest.fail(f"__del__ raised an unexpected exception: {e}")

        # Verify close was still attempted
        mock_file_handle.close.assert_called_once()
