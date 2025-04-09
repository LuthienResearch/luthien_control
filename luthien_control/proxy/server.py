import logging
import uuid
from typing import Any, Dict, List, Sequence, Tuple, Union
from urllib.parse import urlparse  # Added for parsing URL

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response

# Import Settings class directly for dependency injection
from luthien_control.config.settings import Settings

# Import new policy framework components
from luthien_control.control_policy.initialize_context import InitializeContextPolicy
from luthien_control.control_policy.interface import ControlPolicy

# Import concrete policies
# Import concrete builder
from luthien_control.core.response_builder.interface import ResponseBuilder

# Import policy dependency and base class
# Importing utils for potential decompression in policy logic later
# Import NEW dependency providers from dependencies module
from luthien_control.dependencies import (
    get_control_policies,
    get_http_client,
    get_initial_context_policy,
    get_policy,
    get_response_builder,
)
from luthien_control.policies.base import Policy

# Import the orchestrator
from luthien_control.proxy.orchestration import run_policy_flow

logger = logging.getLogger(__name__)

router = APIRouter()

# --- Dependency Providers ---

# Existing provider for HTTP client
# ... (get_http_client defined in luthien_control.dependencies)


# === BETA ENDPOINT ===
# Must be defined *before* the catch-all `proxy_endpoint`
@router.api_route(
    "/beta/{full_path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
)
async def proxy_endpoint_beta(
    request: Request,
    full_path: str,
    # Common dependencies
    client: httpx.AsyncClient = Depends(get_http_client),
    settings: Settings = Depends(Settings),
    # New framework dependencies (using implemented providers)
    initial_context_policy: InitializeContextPolicy = Depends(get_initial_context_policy),
    policies: Sequence[ControlPolicy] = Depends(get_control_policies),
    builder: ResponseBuilder = Depends(get_response_builder),
):
    """
    Proxy endpoint using the new policy orchestration flow.
    This runs in parallel with the original `proxy_endpoint`.
    Handles requests starting with /beta/.
    """
    logger.info(f"Received request for /beta/{full_path}")

    # Orchestrate the policy flow
    response = await run_policy_flow(
        request=request,
        http_client=client,
        settings=settings,
        initial_context_policy=initial_context_policy,
        policies=policies,
        builder=builder,
    )

    logger.info(f"Returning response for /beta/{full_path}")
    return response


# === ORIGINAL PROXY ENDPOINT ===
@router.api_route(
    "/{full_path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
)
async def proxy_endpoint(
    request: Request,
    full_path: str,
    client: httpx.AsyncClient = Depends(get_http_client),
    policy: Policy = Depends(get_policy),
    settings: Settings = Depends(Settings),
):
    """
    Core proxy endpoint to forward requests to the configured backend.
    Intercepts requests/responses for policy application.
    """
    request_id = str(uuid.uuid4())

    # --- Request Preparation ---
    raw_request_body = await request.body()

    # --- Apply Request Policy ---
    try:
        policy_outcome: Union[Dict[str, Any], Response] = await policy.apply_request_policy(
            request=request, original_body=raw_request_body, request_id=request_id
        )
    except Exception as e:
        logger.exception(f"[{request_id}] Error applying request policy", extra={"request_id": request_id})
        raise HTTPException(status_code=500, detail="Error applying request policy.") from e

    if isinstance(policy_outcome, Response):
        return policy_outcome

    # --- Process Policy Outcome ---
    modified_request_body = policy_outcome.get("content", raw_request_body)
    if not isinstance(modified_request_body, bytes):
        try:
            modified_request_body = str(modified_request_body).encode("utf-8")
        except Exception:
            logger.exception(
                f"[{request_id}] Error encoding policy request content",
                extra={"request_id": request_id},
            )
            raise HTTPException(status_code=500, detail="Policy returned invalid request content type.")

    # --- Prepare Backend Headers ---
    policy_headers = policy_outcome.get("headers")
    backend_headers_list: List[Tuple[bytes, bytes]] = []
    excluded_headers = {b"host", b"content-length", b"transfer-encoding"}

    if policy_headers is not None:
        if isinstance(policy_headers, dict):
            items = policy_headers.items()
        elif isinstance(policy_headers, list):
            items = policy_headers
        else:
            logger.warning(
                f"[{request_id}] Policy returned unexpected header type: {type(policy_headers)}. Ignoring.",
                extra={"request_id": request_id},
            )
            items = request.headers.items()  # Fallback to original request headers

        for key, value in items:
            key_bytes = key.encode("latin-1") if isinstance(key, str) else key
            value_bytes = value.encode("latin-1") if isinstance(value, str) else value
            if (
                isinstance(key_bytes, bytes)
                and isinstance(value_bytes, bytes)
                and key_bytes.lower() not in excluded_headers
            ):
                backend_headers_list.append((key_bytes, value_bytes))
    else:
        for key, value in request.headers.raw:
            if key.lower() not in excluded_headers:
                backend_headers_list.append((key, value))

    # Use current_settings fetched earlier
    # Remove original host header if present (should be excluded by check above, but belt-and-suspenders)
    backend_headers_list = [(k, v) for k, v in backend_headers_list if k.lower() != b"host"]
    # Add the correct host header for the backend
    try:
        backend_url_str = settings.get_backend_url()
        parsed_backend_url = urlparse(backend_url_str)
        backend_host = parsed_backend_url.hostname
        if not backend_host:
            raise ValueError("Could not parse hostname from BACKEND_URL")
        backend_headers_list.append((b"host", backend_host.encode("latin-1")))

        # Explicitly ask the backend not to compress the response
        # Remove any existing Accept-Encoding headers first
        # WORKAROUND: httpx (used by TestClient and potentially deployed client)
        # was failing Brotli decompression on valid responses from api.openai.com.
        # Forcing 'identity' (no compression) avoids this decoding error.
        # This might slightly increase bandwidth usage but ensures correct test/proxy function.
        # See: https://github.com/LuthienResearch/luthien_control/issues/1
        backend_headers_list = [(k, v) for k, v in backend_headers_list if k.lower() != b"accept-encoding"]
        backend_headers_list.append((b"accept-encoding", b"identity"))
    except ValueError as e:
        logger.error(
            f"[{request_id}] Invalid backend_url configuration in settings: {e}",
            extra={"request_id": request_id},
        )
        raise HTTPException(status_code=500, detail="Internal server error: Invalid backend configuration.")

    # --- Build Backend Request ---
    # Construct target URL correctly using parsed backend URL and full_path
    # parsed_backend_url.netloc includes host and potentially port
    # full_path comes from the route parameter and does not include the leading slash.
    backend_url = f"{parsed_backend_url.scheme}://{parsed_backend_url.netloc}/{full_path}"
    backend_request = client.build_request(
        method=request.method,
        url=backend_url,
        content=modified_request_body,
        headers=backend_headers_list,
        params=request.query_params,
    )

    # --- Send Request to Backend ---
    try:
        logger.debug(
            f"[{request_id}] Forwarding request: {backend_request.method} {backend_request.url}",
            extra={"request_id": request_id},
        )
        # Tell httpx *not* to automatically decode based on Content-Encoding
        # We will handle forwarding the raw bytes
        backend_response = await client.send(backend_request, stream=True)
        # Must read the response body to enable reuse/policy application
        raw_backend_response_body = await backend_response.aread()

    except httpx.TimeoutException as e:
        logger.error(
            f"[{request_id}] Timeout connecting to backend '{backend_url}': {e}",
            extra={"request_id": request_id},
        )
        raise HTTPException(status_code=504, detail="Proxy timeout connecting to backend.")
    except httpx.RequestError as e:
        # Includes ConnectError, ReadError, etc.
        logger.error(
            f"[{request_id}] Error connecting to backend '{backend_url}': {e}",
            extra={"request_id": request_id},
        )
        raise HTTPException(status_code=502, detail="Proxy error connecting to backend.")

    # --- Apply Response Policy ---
    try:
        response_policy_outcome: Union[Dict[str, Any], Response] = await policy.apply_response_policy(
            backend_response=backend_response,
            original_response_body=raw_backend_response_body,
            request_id=request_id,
        )
    except Exception as e:
        # Make sure to close the stream if an error occurs before returning
        await backend_response.aclose()
        logger.exception(f"[{request_id}] Error applying response policy", extra={"request_id": request_id})
        raise HTTPException(status_code=500, detail="Error applying response policy.") from e

    if isinstance(response_policy_outcome, Response):
        await backend_response.aclose()  # Close original response stream
        return response_policy_outcome

    # --- Process Response Policy Outcome ---
    final_response_body = response_policy_outcome.get("content", raw_backend_response_body)
    if not isinstance(final_response_body, bytes):
        try:
            final_response_body = str(final_response_body).encode("utf-8")
        except Exception:
            logger.exception(
                f"[{request_id}] Error encoding policy response content",
                extra={"request_id": request_id},
            )
            await backend_response.aclose()  # Close stream before raising
            raise HTTPException(status_code=500, detail="Policy returned invalid response content type.")

    final_status_code = response_policy_outcome.get("status_code", backend_response.status_code)
    final_headers = response_policy_outcome.get("headers", backend_response.headers)

    # Filter hop-by-hop headers from final response headers
    hop_by_hop_headers = {
        # Note: httpx headers are lowercase bytes, FastAPI Response headers are case-insensitive strings
        b"connection",
        b"keep-alive",
        b"proxy-authenticate",
        b"proxy-authorization",
        b"te",
        b"trailers",
        b"transfer-encoding",
        b"upgrade",
    }

    response_headers: Dict[str, str] = {}
    for k, v in final_headers.items():
        # Ensure key is bytes and lowercase for checking against hop_by_hop_headers
        key_bytes = k.encode("latin-1") if isinstance(k, str) else k
        key_lower_bytes = key_bytes.lower() if isinstance(key_bytes, bytes) else key_bytes

        if isinstance(key_lower_bytes, bytes) and key_lower_bytes in hop_by_hop_headers:
            continue  # Skip hop-by-hop header

        # Decode key and value to strings for the final Response object
        key_str = key_bytes.decode("latin-1") if isinstance(key_bytes, bytes) else str(k)
        value_str = v.decode("latin-1") if isinstance(v, bytes) else str(v)
        response_headers[key_str] = value_str

    # Return the final response using StreamingResponse to handle potentially large bodies
    # Update: Using Response directly since we read the body for policy application
    return Response(
        content=final_response_body,
        status_code=final_status_code,
        headers=response_headers,
        media_type=backend_response.headers.get("content-type"),
    )


# --- Helper Functions / Original v1 Logic Helpers ---
