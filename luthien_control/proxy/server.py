import uuid
from typing import Any, Dict, List, Tuple, Union

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from luthien_control.config.settings import Settings

# Import policy dependency and base class
from luthien_control.dependencies import get_http_client, get_policy
from luthien_control.policies.base import Policy

# Importing utils for potential decompression in policy logic later

router = APIRouter()


@router.api_route(
    "/{full_path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
)
async def proxy_endpoint(
    request: Request,
    full_path: str,
    client: httpx.AsyncClient = Depends(get_http_client),
    policy: Policy = Depends(get_policy),
):
    """
    Core proxy endpoint to forward requests to the configured backend.
    Intercepts requests/responses for policy application.
    """
    request_id = str(uuid.uuid4())

    # Get settings from app state BEFORE first use
    current_settings: Settings | None = getattr(request.app.state, 'test_settings', None)
    if current_settings is None:
        print("CRITICAL ERROR: Settings not found in request.app.state")
        raise HTTPException(status_code=500, detail="Internal server error: App settings not configured.")

    # --- Request Preparation ---
    raw_request_body = await request.body()

    # --- Apply Request Policy ---
    try:
        policy_outcome: Union[Dict[str, Any], Response] = await policy.apply_request_policy(
            request=request,
            original_body=raw_request_body,
            request_id=request_id
        )
    except Exception as e:
        print(f"[{request_id}] Error applying request policy: {e}", flush=True)
        raise HTTPException(status_code=500, detail="Error applying request policy.") from e

    if isinstance(policy_outcome, Response):
        return policy_outcome

    # --- Process Policy Outcome ---
    modified_request_body = policy_outcome.get("content", raw_request_body)
    if not isinstance(modified_request_body, bytes):
        try:
            modified_request_body = str(modified_request_body).encode('utf-8')
        except Exception as e:
             print(f"[{request_id}] Error encoding policy request content: {e}")
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
             print(f"[{request_id}] Warning: Policy returned unexpected header type: {type(policy_headers)}. Ignoring.")
             items = request.headers.items() # Fallback to original request headers

        for key, value in items:
            key_bytes = key.encode('latin-1') if isinstance(key, str) else key
            value_bytes = value.encode('latin-1') if isinstance(value, str) else value
            if isinstance(key_bytes, bytes) and isinstance(value_bytes, bytes) and key_bytes.lower() not in excluded_headers:
                 backend_headers_list.append((key_bytes, value_bytes))
    else:
        for key, value in request.headers.raw:
            if key.lower() not in excluded_headers:
                backend_headers_list.append((key, value))

    # Use current_settings fetched earlier
    backend_headers_list = [(k, v) for k, v in backend_headers_list if k.lower() != b'host']
    backend_headers_list.append(
        (b"host", current_settings.BACKEND_URL.host.encode("latin-1"))
    )
    backend_headers_list = [(k, v) for k, v in backend_headers_list if k.lower() != b'content-length']
    backend_headers_list.append((b"content-length", str(len(modified_request_body)).encode('latin-1')))

    # --- Backend Request Construction ---
    backend_url = httpx.URL(
        path=f"/{full_path.lstrip('/')}",
        query=request.url.query.encode("utf-8"),
        scheme=current_settings.BACKEND_URL.scheme,
        host=current_settings.BACKEND_URL.host,
        port=current_settings.BACKEND_URL.port,
    )

    backend_request = client.build_request(
        method=request.method,
        url=backend_url,
        headers=backend_headers_list,
        content=modified_request_body,
    )

    # --- Sending Request & Receiving Response ---
    try:
        backend_response: httpx.Response = await client.send(backend_request)
        raw_response_body = backend_response.content
        backend_headers = backend_response.headers.copy()
        status_code = backend_response.status_code
        await backend_response.aclose()
        backend_response.raise_for_status()

        # --- Apply Response Policy ---
        try:
            policy_outcome: Union[Dict[str, Any], Response] = await policy.apply_response_policy(
                backend_response=backend_response,
                original_response_body=raw_response_body,
                request_id=request_id
            )
        except Exception as e:
            print(f"[{request_id}] Error applying response policy: {e}", flush=True)
            raise HTTPException(status_code=500, detail="Error applying response policy.") from e

        if isinstance(policy_outcome, Response):
            return policy_outcome

        # --- Process Response Policy Outcome ---
        final_status_code = policy_outcome.get("status_code", status_code)
        final_raw_body = policy_outcome.get("content", raw_response_body)
        policy_resp_headers = policy_outcome.get("headers")

        # Ensure final body is bytes
        if not isinstance(final_raw_body, bytes):
            try:
                 final_raw_body = str(final_raw_body).encode('utf-8')
            except Exception as e:
                 print(f"[{request_id}] Error encoding policy response content: {e}")
                 raise HTTPException(status_code=500, detail="Policy returned invalid response content type.")

        # --- Prepare Final Headers ---
        final_headers_dict: Dict[str, str] = {}
        headers_to_remove = {"content-encoding", "transfer-encoding", "connection"}
        if policy_resp_headers is not None:
            if isinstance(policy_resp_headers, dict):
                items = policy_resp_headers.items()
            elif isinstance(policy_resp_headers, list):
                items = policy_resp_headers
            else:
                 print(f"[{request_id}] Warning: Policy returned unexpected header type: {type(policy_resp_headers)}. Ignoring.")
                 items = backend_headers.items()
            for key, value in items:
                key_str = key.decode('latin-1') if isinstance(key, bytes) else str(key)
                value_str = value.decode('latin-1') if isinstance(value, bytes) else str(value)
                if key_str.lower() not in headers_to_remove:
                    final_headers_dict[key_str] = value_str
        else:
            for key, value in backend_headers.items():
                if key.lower() not in headers_to_remove:
                    final_headers_dict[key] = value

        final_headers_dict["Content-Length"] = str(len(final_raw_body))

        # --- Return Final Response to Client ---
        return Response(
            content=final_raw_body,
            status_code=final_status_code,
            headers=final_headers_dict,
        )

    except httpx.HTTPStatusError as exc:
        error_body = exc.response.content
        error_headers = exc.response.headers.copy()
        error_status_code = exc.response.status_code
        await exc.response.aclose()
        print(f"[{request_id}] Backend returned error status {error_status_code}: Body: {error_body.decode(errors='ignore') if error_body else '[empty body]'}")
        raise HTTPException(
            status_code=502,
            detail=f"Backend server returned status code {error_status_code}"
        ) from exc
    except httpx.RequestError as exc:
        print(f"[{request_id}] HTTPX RequestError connecting to backend: {exc}")
        if hasattr(exc, 'response') and exc.response and not exc.response.is_closed:
            try: await exc.response.aclose()
            except Exception: pass
        raise HTTPException(
            status_code=502, detail=f"Error connecting to backend: {exc}"
        ) from exc
    except Exception as exc: # Catch any other unexpected exceptions
        # If it's an HTTPException that we raised intentionally, re-raise it
        if isinstance(exc, HTTPException):
            raise exc

        # Otherwise, log it as truly unexpected and return a generic 500
        print(f"[{request_id}] Unexpected error during proxy request: {exc}", flush=True)
        # Ensure response is closed if one exists and wasn't closed
        if 'backend_response' in locals() and backend_response and not backend_response.is_closed:
            try: await backend_response.aclose()
            except Exception: pass
        raise HTTPException(
            status_code=500, detail="Internal server error during proxy processing."
        ) from exc


