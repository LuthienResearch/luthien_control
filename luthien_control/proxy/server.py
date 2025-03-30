from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, APIRouter, HTTPException, Request, Response
from starlette.background import BackgroundTask
from starlette.responses import StreamingResponse

from luthien_control.config.settings import Settings
from luthien_control.dependencies import get_http_client
from luthien_control.proxy.utils import get_decompressed_request_body, get_decompressed_response_body


router = APIRouter()


@router.api_route(
    "/{full_path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
)
async def proxy_endpoint(
    request: Request,
    full_path: str,
    current_settings: Settings = Depends(Settings),
    client: httpx.AsyncClient = Depends(get_http_client)
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
        # Get the raw request body for forwarding
        # If needed for logging/policy checks, decompress here:
        # decompressed_body = await get_decompressed_request_body(request)
        # For now, just forward the raw body
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

        # Explicitly check for backend errors *before* streaming the body back
        # This raises an HTTPStatusError if the backend returned 4xx or 5xx
        backend_response.raise_for_status()

        # Stream the backend response back to the client
        # If logging/inspection were needed, we'd have to read the whole body,
        # decompress it, and then potentially re-stream/re-compress:
        # raw_body = await backend_response.aread()
        # encoding = backend_response.headers.get("content-encoding")
        # decompressed_response_body = decompress_content(raw_body, encoding)
        # -- Log decompressed_response_body --
        # Then, create a new Response/StreamingResponse with raw_body
        # For now, stream directly to preserve encoding and efficiency
        return StreamingResponse(
            backend_response.aiter_raw(),
            status_code=backend_response.status_code,
            headers=backend_response.headers,
            background=BackgroundTask(backend_response.aclose),
        )

    except httpx.HTTPStatusError as exc: # Catch 4xx/5xx errors from backend FIRST
        # Log the error details from the backend response before closing it
        # If logging/inspection were needed for error bodies, decompress here:
        error_body = await exc.response.aread() # Read raw body for now
        await exc.response.aclose() # Ensure connection is closed
        print(f"Backend returned error status {exc.response.status_code}: Body: {error_body.decode() if error_body else '[empty body]'}")
        raise HTTPException(
            status_code=502, # Bad Gateway is more appropriate
            detail=f"Backend server returned status code {exc.response.status_code}"
        ) from exc

    except httpx.RequestError as exc:
        # Handle connection errors, timeouts, etc.
        print(f"HTTPX RequestError connecting to backend: {exc}") # Log details
        # Ensure response is closed if one exists (might not in RequestError)
        if hasattr(exc, 'response') and exc.response:
            await exc.response.aclose()
        raise HTTPException(
            status_code=502, detail=f"Error connecting to backend: {exc}"
        ) from exc

    except Exception as exc: # Catch any other unexpected exceptions
        # Log the unexpected error with traceback
        print(f"!!! Unexpected error during proxy request: {exc}", flush=True)
        import traceback
        traceback.print_exc()
        # Ensure response is closed if one was received before the error
        if 'backend_response' in locals() and backend_response:
            await backend_response.aclose()
        # Return a generic 500 error
        raise HTTPException(
            status_code=500, detail="Internal server error during proxy processing."
        ) from exc


