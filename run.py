"""
Script to run the Luthien Control Framework server with hot reload.
"""

import os
from pathlib import Path

import uvicorn


def main():
    """Run the server with hot reload enabled."""
    # Load environment variables from .env file
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        from dotenv import load_dotenv

        load_dotenv(env_path)

    # Get configuration from environment variables
    host = os.getenv("LUTHIEN_HOST", "0.0.0.0")
    port = int(os.getenv("LUTHIEN_PORT", "8000"))
    reload = os.getenv("LUTHIEN_RELOAD", "true").lower() == "true"

    # Only use SSL in development (when not in production)
    is_production = os.getenv("ENVIRONMENT", "development") == "production"
    ssl_args = {}

    if not is_production:
        cert_dir = Path(__file__).parent.parent / "certs"
        ssl_keyfile = cert_dir / "localhost.key"
        ssl_certfile = cert_dir / "fullchain.crt"
        if ssl_keyfile.exists() and ssl_certfile.exists():
            ssl_args.update({"ssl_keyfile": str(ssl_keyfile), "ssl_certfile": str(ssl_certfile)})

    # Run the server
    uvicorn.run(
        "luthien_control.proxy.server:app",
        host=host,
        port=port,
        reload=reload,
        reload_dirs=["luthien_control"],  # Only watch our package directory
        log_level="debug",
        **ssl_args,
    )


if __name__ == "__main__":
    main()
