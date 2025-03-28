"""
API request/response log data structuring.
"""
import json
from datetime import datetime
from typing import Any, Dict, Optional, Union, Callable

class APILogger:
    """Formats API requests and responses into structured log data."""
    
    def __init__(self, log_handler: Callable[[Dict[str, Any]], None]):
        """Initialize with a function that handles the structured log data."""
        self.log_handler = log_handler
    
    def _parse_json(self, data: Union[str, bytes]) -> Any:
        """Parse data as JSON if possible, otherwise return as string."""
        if isinstance(data, bytes):
            # Try common encodings
            encodings = ['utf-8', 'utf-16', 'utf-32', 'ascii']
            for encoding in encodings:
                try:
                    data = data.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                # If all decodings fail, return raw bytes as string
                return str(data)
        
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return data
    
    def _prepare_log_entry(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare a log entry with common fields."""
        data["timestamp"] = datetime.utcnow().isoformat()
        return data
    
    def log_request(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        body: Optional[Union[str, bytes]] = None,
        query_params: Optional[Dict[str, Any]] = None
    ) -> None:
        """Format and log an API request."""
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
                
        self.log_handler(self._prepare_log_entry(log_data))
    
    def log_response(
        self,
        status_code: int,
        headers: Dict[str, str],
        body: Optional[Union[str, bytes]] = None
    ) -> None:
        """Format and log an API response."""
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
                
        self.log_handler(self._prepare_log_entry(log_data)) 