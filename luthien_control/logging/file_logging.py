"""
File-based logging configuration and utilities.
"""
import contextlib
import json
from pathlib import Path
from typing import ContextManager, TextIO, Optional, Dict, Any

from .api_logger import APILogger

class FileLogManager:
    """Manages file-based logging configuration."""
    
    def __init__(self, base_dir: Path):
        """Initialize with base directory for logs."""
        self.base_dir = base_dir
        self._open_files = []
    
    def ensure_log_dir(self, subdir: Optional[str] = None) -> Path:
        """Ensure log directory exists and return its path."""
        log_dir = self.base_dir
        if subdir:
            log_dir = log_dir / subdir
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir
    
    @contextlib.contextmanager
    def open_log_file(self, filename: str, mode: str = 'a') -> ContextManager[TextIO]:
        """Open a log file, ensuring its directory exists."""
        path = self.base_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, mode) as f:
            yield f
    
    def create_logger(self, filename: str) -> APILogger:
        """Create an APILogger that writes to the specified file."""
        path = self.base_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        file_obj = open(path, 'a')
        self._open_files.append(file_obj)
        
        def write_json_line(data: Dict[str, Any]) -> None:
            """Write a JSON line to the file."""
            json.dump(data, file_obj)
            file_obj.write('\n')
            file_obj.flush()
        
        return APILogger(write_json_line)
    
    def __del__(self):
        """Clean up any open files when the manager is destroyed."""
        for file_obj in self._open_files:
            try:
                file_obj.close()
            except:
                pass  # Best effort cleanup 