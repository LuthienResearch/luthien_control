from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from starlette.background import BackgroundTask
from starlette.responses import StreamingResponse

from luthien_control.config.settings import Settings, get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the lifespan of the application, including the HTTP client."""
    # Startup: Initialize the client and store it in app state
    app.state.http_client = httpx.AsyncClient()
    print("HTTP Client Initialized")  # Added for debugging test runs
    yield
    # Shutdown: Close the client stored in app state
    print("Closing HTTP Client")  # Added for debugging test runs
    await app.state.http_client.aclose()


app = FastAPI(title="Luthien Control Proxy", lifespan=lifespan)

# Remove the global client instance
# http_client = httpx.AsyncClient()

# Remove the old shutdown handler function and registration
# async def _close_http_client():
#     """Close the httpx client gracefully."""
#     await http_client.aclose()
# app.add_event_handler("shutdown", _close_http_client)


@app.api_route(
    "/{full_path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
)
async def proxy_endpoint(
    request: Request, full_path: str, current_settings: Settings = Depends(get_settings)
):
    """
    Core proxy endpoint to forward requests to the configured backend.
    Handles various HTTP methods and streams the response back.
    """
    backend_url = httpx.URL(
        path=f"/{full_path.lstrip('/')}",
        query=request.url.query.encode("utf-8"),
        scheme=current_settings.BACKEND_URL.scheme,
        host=current_settings.BACKEND_URL.host,
        port=current_settings.BACKEND_URL.port,
    )

    # Get the client from app state
    client = request.app.state.http_client

    # Prepare headers for the backend, preserving case and explicitly setting Host
    # Start with raw headers (list of tuples)
    raw_headers = request.headers.raw
    backend_headers_list = []
    excluded_headers = {
        b"host",
        b"transfer-encoding",
    }  # Headers to exclude (lowercase bytes)

    for key, value in raw_headers:
        if key.lower() not in excluded_headers:
            backend_headers_list.append((key, value))

    # Add the correct Host header (as bytes)
    backend_headers_list.append(
        (b"host", current_settings.BACKEND_URL.host.encode("latin-1"))
    )

    # Prepare the request for the backend
    backend_request = client.build_request(
        method=request.method,
        url=backend_url,
        # Use the carefully constructed list of header tuples
        headers=backend_headers_list,
        content=await request.body(),
    )

    # Send the request to the backend and stream the response
    try:
        # Ensure backend_request headers are bytes if necessary, although httpx often handles this
        print(f"Forwarding request to: {backend_request.url}")  # Debug print
        # Debug: Print headers as key-value pairs for readability
        print("Forwarding headers:")
        for k, v in backend_request.headers.items():
            print(f"  {k}: {v}")
        backend_response = await client.send(backend_request, stream=True)
    except httpx.RequestError as exc:
        # Handle connection errors, timeouts, etc.
        # Use HTTPException for standard FastAPI error handling
        raise HTTPException(
            status_code=502, detail=f"Error connecting to backend: {exc}"
        )

    # Stream the backend response back to the client
    return StreamingResponse(
        backend_response.aiter_raw(),
        status_code=backend_response.status_code,
        headers=backend_response.headers,
        background=BackgroundTask(backend_response.aclose),
    )


# No need for the explicit event handler registration anymore
