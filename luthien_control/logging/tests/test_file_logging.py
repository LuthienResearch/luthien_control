"""Test file-based logging configuration."""
import json
from pathlib import Path

import pytest

from luthien_control.logging.file_logging import FileLogManager

@pytest.fixture
def tmp_log_dir(tmp_path):
    """Create a temporary directory for logs."""
    return tmp_path / "logs"

@pytest.fixture
def log_manager(tmp_log_dir):
    """Create a FileLogManager with a temporary directory."""
    return FileLogManager(tmp_log_dir)

def test_ensure_log_dir(log_manager, tmp_log_dir):
    """Test log directory creation."""
    # Test base directory
    log_dir = log_manager.ensure_log_dir()
    assert log_dir == tmp_log_dir
    assert log_dir.exists()
    
    # Test subdirectory
    subdir = log_manager.ensure_log_dir("api")
    assert subdir == tmp_log_dir / "api"
    assert subdir.exists()

def test_open_log_file(log_manager):
    """Test log file creation and writing."""
    test_data = {"test": "data"}
    
    with log_manager.open_log_file("test.log") as f:
        json.dump(test_data, f)
        f.write("\n")
    
    log_file = log_manager.base_dir / "test.log"
    assert log_file.exists()
    
    with open(log_file) as f:
        loaded = json.load(f)
        assert loaded == test_data

def test_create_logger(log_manager):
    """Test logger creation and usage."""
    logger = log_manager.create_logger("api.log")
    
    # Test logging
    logger.log_request(
        method="GET",
        url="https://api.example.com/test",
        headers={"Content-Type": "application/json"}
    )
    
    log_file = log_manager.base_dir / "api.log"
    assert log_file.exists()
    
    with open(log_file) as f:
        log_entry = json.loads(f.readline())
        assert log_entry["type"] == "request"
        assert log_entry["method"] == "GET"
        assert log_entry["url"] == "https://api.example.com/test"

def test_nested_log_files(log_manager):
    """Test creating log files in nested directories."""
    nested_path = "api/requests/test.log"
    
    with log_manager.open_log_file(nested_path) as f:
        f.write("test\n")
    
    log_file = log_manager.base_dir / nested_path
    assert log_file.exists()
    assert log_file.parent.name == "requests"
    assert log_file.parent.parent.name == "api" 