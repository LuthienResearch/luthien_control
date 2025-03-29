"""
FastAPI proxy server implementation for AI model API control.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.datastructures import Headers
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field, ValidationError

from ..logging.file_logging import FileLogManager
from ..policies.manager import PolicyManager

# Load environment variables from .env file
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

# Set up logging
log_manager = FileLogManager(Path("logs"))
api_logger = log_manager.create_logger("api.log")

# Create policy manager
policy_manager = PolicyManager()

# Create FastAPI app
app = FastAPI(title="Luthien Control Framework")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProxyConfig(BaseModel):
    """Configuration for the proxy server."""

    target_api_url: str = Field(..., alias="TARGET_URL")
    # Optional key for the proxy itself, if needed for incoming requests (not implemented yet)
    proxy_api_key: Optional[str] = Field(None, alias="PROXY_API_KEY")
    # Optional key FOR THE TARGET API. Added if no Authorization header is present.
    target_api_key: Optional[str] = Field(None, alias="OPENAI_API_KEY")


# Load configuration from environment variables
try:
    config = ProxyConfig(
        TARGET_URL=os.getenv("TARGET_URL"),
        PROXY_API_KEY=os.getenv("PROXY_API_KEY"),
        OPENAI_API_KEY=os.getenv("OPENAI_API_KEY"),
    )
except ValidationError as e:
    print(f"ERROR: Missing or invalid environment variables for ProxyConfig: {e}")
    # Provide defaults or raise an error if critical config is missing
    # For now, let's try to provide a default for target_url if missing,
    # but ideally, this should halt startup if TARGET_URL is missing.
    if "TARGET_URL" not in os.environ:
        print("CRITICAL: TARGET_URL environment variable is not set.")
        # In a real app, you might exit here:
        # sys.exit("TARGET_URL must be set.")
        # For development, we might allow a default (though risky):
        # config = ProxyConfig(target_api_url="http://localhost:8001", ...) # Example default
        # Raising error is safer:
        raise ValueError("TARGET_URL environment variable is not set.") from e
    else:
        # Re-raise if validation failed for other reasons
        raise e

if not config.target_api_url:
    raise ValueError("TARGET_URL environment variable is not set or empty.")


def _prepare_request_headers(request_headers: Headers, target_api_key: Optional[str]) -> Dict[str, str]:
    """
    Prepares headers for forwarding, removing unnecessary ones and adding
    target API key if necessary and not already present.
    """
    header_dict = dict(request_headers)

    # Remove headers not suitable for forwarding
    header_dict.pop("host", None)
    header_dict.pop("content-length", None)  # httpx handles this

    # Add target API key if provided in config and no authorization header exists
    if target_api_key and "authorization" not in {k.lower() for k in header_dict}:
        header_dict["Authorization"] = f"Bearer {target_api_key}"

    # Ensure all header values are strings (FastAPI/Starlette might pass other types)
    return {k: str(v) for k, v in header_dict.items()}


async def _forward_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    headers: Dict[str, str],
    content: Optional[bytes],
    params: Dict[str, Any],
) -> Tuple[int, Dict[str, str], bytes]:
    """Forwards the request to the target URL using httpx."""
    try:
        response = await client.request(method=method, url=url, headers=headers, content=content, params=params)
        response_content = await response.aread()
        return response.status_code, dict(response.headers), response_content
    except httpx.RequestError as e:
        # Log the error details
        logging.error(f"HTTPX Request Error: {e.__class__.__name__} - {e}")
        raise HTTPException(status_code=502, detail=f"Error forwarding request to target API: {e}") from e


def _process_response_headers(headers_dict: Dict[str, str]) -> Dict[str, str]:
    """Processes response headers, e.g., handling content encoding."""
    processed_headers = headers_dict.copy()

    # Handle content-encoding header safely, removing 'br' if present.
    # Reason: httpx automatically decompresses 'br' (Brotli) encoded responses.
    # If we forward the 'content-encoding: br' header to the final client,
    # the client might attempt to decompress the already-decompressed body,
    # leading to errors. We remove 'br' to prevent this.
    content_encoding = processed_headers.get("content-encoding")
    if content_encoding:
        encodings = [enc.strip() for enc in content_encoding.split(",") if enc.strip().lower() != "br"]
        if encodings:
            processed_headers["content-encoding"] = ", ".join(encodings)
        else:
            # If 'br' was the only encoding, remove the header entirely.
            processed_headers.pop("content-encoding", None)

    # Remove other headers that might cause issues if forwarded
    processed_headers.pop("transfer-encoding", None)  # Let FastAPI/client handle this

    return processed_headers


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_request(request: Request, path: str):
    """
    Proxies requests to the configured target API, applying policies and logging.
    """
    # 1. Prepare Initial Request Data
    target_url = f"{config.target_api_url.rstrip('/')}/{path.lstrip('/')}"
    initial_headers = _prepare_request_headers(request.headers, config.target_api_key)
    body = await request.body() if request.method in ["POST", "PUT"] else None
    query_params = dict(request.query_params)

    # 2. Log Initial Request
    api_logger.log_request(
        method=request.method, url=target_url, headers=initial_headers, body=body, query_params=query_params
    )

    try:
        # 3. Apply Request Policies
        # Policies can modify target_url, headers, body
        processed_request = await policy_manager.apply_request_policies(request, target_url, initial_headers, body)
        final_target_url = processed_request["target_url"]
        final_headers = processed_request["headers"]
        final_body = processed_request["body"]

        # 4. Forward Request
        async with httpx.AsyncClient() as client:
            status_code, response_headers, response_content = await _forward_request(
                client, request.method, final_target_url, final_headers, final_body, query_params
            )

        # 5. Log Raw Response
        api_logger.log_response(status_code=status_code, headers=response_headers, body=response_content)

        # 6. Apply Response Policies
        # Policies can modify status_code, headers, content
        processed_response = await policy_manager.apply_response_policies(
            request,  # Pass original request context
            # Simulate httpx.Response structure or pass necessary parts
            {"status_code": status_code, "headers": response_headers, "content": response_content},
            response_content,
        )
        final_status_code = processed_response["status_code"]
        final_response_headers_raw = processed_response["headers"]
        final_response_content = processed_response["content"]

        # 7. Process Response Headers for Forwarding
        final_response_headers = _process_response_headers(final_response_headers_raw)

        # 8. Return Final Response
        return Response(
            content=final_response_content,
            status_code=final_status_code,
            headers=final_response_headers,
        )

    except HTTPException as e:
        # Re-raise HTTPExceptions (e.g., from _forward_request or policies)
        raise e
    except Exception as e:
        # Catch-all for unexpected errors during policy application or processing
        logging.error(f"Unexpected proxy error: {e.__class__.__name__} - {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Unexpected proxy error: {str(e)}")


# Note: The route path changed from /v1/{path:path} to /{path:path}
#       to be more general. Adjust TARGET_URL accordingly
#       (e.g., set TARGET_URL=https://api.openai.com/v1).
