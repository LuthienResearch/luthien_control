"""
Simple API request/response logger using JSON format.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union

class APILogger:
    """Simple logger for API requests and responses."""
    
    def __init__(self, log_file: str = "logs/api.log"):
        """Initialize logger with log file path."""
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
    
    def _parse_json(self, data: Union[str, bytes]) -> Any:
        """Parse data as JSON if possible, otherwise return as is."""
        if isinstance(data, bytes):
            try:
                data = data.decode()
            except UnicodeDecodeError:
                return "[BINARY_DATA]"
        
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return data
    
    def _write_log(self, data: Dict[str, Any]) -> None:
        """Write a log entry in JSON format."""
        data["timestamp"] = datetime.utcnow().isoformat()
        
        with self.log_file.open("a") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
    
    def log_request(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        body: Optional[Union[str, bytes]] = None,
        query_params: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log an API request."""
        # Redact sensitive headers
        safe_headers = {
            k: "[REDACTED]" if k.lower() in {"authorization", "cookie", "api-key"} else v
            for k, v in headers.items()
        }
        
        log_data = {
            "type": "request",
            "method": method,
            "url": url,
            "headers": safe_headers,
        }
        
        if query_params:
            log_data["query_params"] = query_params
            
        if body:
            log_data["body"] = self._parse_json(body)
                
        self._write_log(log_data)
    
    def log_response(
        self,
        status_code: int,
        headers: Dict[str, str],
        body: Optional[Union[str, bytes]] = None
    ) -> None:
        """Log an API response."""
        # Redact sensitive headers
        safe_headers = {
            k: "[REDACTED]" if k.lower() in {"authorization", "cookie", "api-key"} else v
            for k, v in headers.items()
        }
        
        log_data = {
            "type": "response",
            "status_code": status_code,
            "headers": safe_headers,
        }
        
        if body:
            log_data["body"] = self._parse_json(body)
                
        self._write_log(log_data) 