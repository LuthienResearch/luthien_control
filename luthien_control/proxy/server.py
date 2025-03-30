from fastapi import FastAPI, Request, Response
import httpx
from starlette.responses import StreamingResponse
from starlette.background import BackgroundTask

from luthien_control.config.settings import settings

app = FastAPI(title="Luthien Control Proxy")

http_client = httpx.AsyncClient()


async def _close_http_client():
    """Close the httpx client gracefully."""
    await http_client.aclose()


@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def proxy_endpoint(request: Request, full_path: str):
    """
    Core proxy endpoint to forward requests to the configured backend.
    Handles various HTTP methods and streams the response back.
    """
    backend_url = httpx.URL(
        path=f"/{full_path.lstrip('/')}",
        query=request.url.query.encode("utf-8"),
        # Use settings.BACKEND_URL as the base
        scheme=settings.BACKEND_URL.scheme,
        host=settings.BACKEND_URL.host,
        port=settings.BACKEND_URL.port,
    )

    # Prepare the request for the backend
    backend_request = http_client.build_request(
        method=request.method,
        url=backend_url,
        headers=request.headers.raw,  # Pass raw headers
        content=await request.body(),
    )

    # Send the request to the backend and stream the response
    try:
        backend_response = await http_client.send(backend_request, stream=True)
    except httpx.RequestError as exc:
        # Handle connection errors, timeouts, etc.
        return Response(f"Error connecting to backend: {exc}", status_code=502) # Bad Gateway

    # Stream the backend response back to the client
    return StreamingResponse(
        backend_response.aiter_raw(),
        status_code=backend_response.status_code,
        headers=backend_response.headers,
        background=BackgroundTask(backend_response.aclose),
    )

# Add lifespan event handler for client cleanup
app.add_event_handler("shutdown", _close_http_client)
