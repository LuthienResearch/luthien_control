"""
Main entry point for running the Luthien Control Framework proxy server.
"""
import os
from dotenv import load_dotenv

import uvicorn
from luthien_control.proxy.server import app

def main():
    """Run the proxy server."""
    # Load environment variables from .env file
    load_dotenv()
    
    # Get server configuration from environment or use defaults
    host = os.getenv("HOST", "0.0.0.0")  # nosec B104
    port_str = os.getenv("PORT", "8000")
    log_level = os.getenv("LOG_LEVEL", "info").lower() # Get log level
    try:
        port = int(port_str)
    except ValueError:
        # Raise a more specific error message
        raise ValueError(f"Invalid PORT value: {port_str}")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=log_level # Use validated log level
    )

if __name__ == "__main__":
    main() 