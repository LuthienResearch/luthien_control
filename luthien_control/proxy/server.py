from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response, HTTPException
import httpx
from starlette.responses import StreamingResponse
from starlette.background import BackgroundTask

from luthien_control.config.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the lifespan of the application, including the HTTP client."""
    # Startup: Initialize the client and store it in app state
    app.state.http_client = httpx.AsyncClient()
    print("HTTP Client Initialized") # Added for debugging test runs
    yield
    # Shutdown: Close the client stored in app state
    print("Closing HTTP Client") # Added for debugging test runs
    await app.state.http_client.aclose()


app = FastAPI(title="Luthien Control Proxy", lifespan=lifespan)

# Remove the global client instance
# http_client = httpx.AsyncClient()

# Remove the old shutdown handler function and registration
# async def _close_http_client():
#     """Close the httpx client gracefully."""
#     await http_client.aclose()
# app.add_event_handler("shutdown", _close_http_client)


@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def proxy_endpoint(request: Request, full_path: str):
    """
    Core proxy endpoint to forward requests to the configured backend.
    Handles various HTTP methods and streams the response back.
    """
    backend_url = httpx.URL(
        path=f"/{full_path.lstrip('/')}",
        query=request.url.query.encode("utf-8"),
        scheme=settings.BACKEND_URL.scheme,
        host=settings.BACKEND_URL.host,
        port=settings.BACKEND_URL.port,
    )

    # Get the client from app state
    client = request.app.state.http_client

    # Prepare the request for the backend
    backend_request = client.build_request(
        method=request.method,
        url=backend_url,
        headers=request.headers.raw,  # Pass raw headers
        content=await request.body(),
    )

    # Send the request to the backend and stream the response
    try:
        backend_response = await client.send(backend_request, stream=True)
    except httpx.RequestError as exc:
        # Handle connection errors, timeouts, etc.
        # Use HTTPException for standard FastAPI error handling
        raise HTTPException(status_code=502, detail=f"Error connecting to backend: {exc}")

    # Stream the backend response back to the client
    return StreamingResponse(
        backend_response.aiter_raw(),
        status_code=backend_response.status_code,
        headers=backend_response.headers,
        background=BackgroundTask(backend_response.aclose),
    )

# No need for the explicit event handler registration anymore
