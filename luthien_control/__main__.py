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
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )

if __name__ == "__main__":
    main() 