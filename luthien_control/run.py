"""
Script to run the Luthien Control Framework server with hot reload.
"""
import os
import uvicorn
from pathlib import Path

def main():
    """Run the server with hot reload enabled."""
    # Load environment variables from .env file
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        from dotenv import load_dotenv
        load_dotenv(env_path)
    
    # Get configuration from environment variables
    host = os.getenv("LUTHIEN_HOST", "0.0.0.0")
    port = int(os.getenv("LUTHIEN_PORT", "8000"))
    reload = os.getenv("LUTHIEN_RELOAD", "true").lower() == "true"
    
    # Run the server
    uvicorn.run(
        "luthien_control.proxy.server:app",
        host=host,
        port=port,
        reload=reload,
        reload_dirs=["luthien_control"],  # Only watch our package directory
        log_level="debug"
    )

if __name__ == "__main__":
    main() 