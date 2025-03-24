"""
Main entry point for running the Luthien Control Framework proxy server.
"""
import uvicorn
from luthien_control.proxy.server import app

def main():
    """Run the proxy server."""
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )

if __name__ == "__main__":
    main() 