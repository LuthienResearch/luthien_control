from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from luthien_control.proxy.server import router as proxy_router  # Changed import name


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the lifespan of the application, including the HTTP client."""
    # Startup: Initialize the client and store it in app state
    # Use longer timeouts? Default is 5 seconds.
    # Consider making timeouts configurable via settings later.
    timeout = httpx.Timeout(5.0, connect=5.0, read=60.0, write=5.0)
    app.state.http_client = httpx.AsyncClient(timeout=timeout)
    print("HTTP Client Initialized in main app")
    yield
    # Shutdown: Close the client stored in app state
    print("Closing HTTP Client in main app")
    await app.state.http_client.aclose()


app = FastAPI(
    title="Luthien Control",
    description="An intelligent proxy server for AI APIs.",
    version="0.1.0",  # Consider deriving from pyproject.toml later
    lifespan=lifespan,
)
print(f"---> Main app ID during init: {id(app)} <---") # DEBUG PRINT


@app.get("/health", tags=["General"], status_code=200)
async def health_check():
    """Basic health check endpoint."""
    return {"status": "ok"}


# Mount the proxy application - REMOVED
# app.mount("/", proxy_app)

# Include the proxy router
app.include_router(proxy_router)

# Further endpoints (like the main proxy endpoint) will be added here.

# To run the server (from the project root directory):
# uvicorn luthien_control.main:app --reload
