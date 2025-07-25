import logging
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, Path, Request, Response, Security
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.core.dependencies import (
    get_db_session,
    get_dependencies,
    get_main_control_policy,
)
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.proxy.orchestration import run_policy_flow

logger = logging.getLogger(__name__)

router = APIRouter()

# Define the security scheme using HTTPBearer for 'Authorization: Bearer <token>'
# auto_error=False because our ClientApiKeyAuthPolicy handles the missing/invalid key error
# We do this because we want to enable (but not require)
# token authentication, depending on the control policy.
http_bearer_auth = HTTPBearer(auto_error=False)

default_path: str = Path(
    ...,
    description="The full path to the backend API endpoint (e.g., 'v1/chat/completions')",
    openapi_examples={
        "v1/chat/completions": {
            "value": "v1/chat/completions",
        }
    },
)

default_payload: dict[str, Any] = Body(
    None,
    openapi_examples={
        "sqrt(64)": {
            "value": {
                "model": "gpt-3.5-turbo",
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "What is the square root of 64?"},
                ],
                "max_tokens": 30,
            },
        },
    },
)

default_token: Optional[str] = Security(http_bearer_auth)


async def _handle_api_request(
    request: Request,
    main_policy: ControlPolicy,
    dependencies: DependencyContainer,
    session: AsyncSession,
) -> Response:
    """
    Common handler for API proxy requests.
    Orchestrates the policy flow for both GET and POST requests.
    """
    # Log detailed proxy request information
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    auth_header = request.headers.get("authorization", "")
    has_auth = bool(auth_header)

    logger.info(
        "Proxy request received",
        extra={
            "method": request.method,
            "path": request.url.path,
            "client_ip": client_ip,
            "user_agent": user_agent,
            "has_auth": has_auth,
            "query_params": dict(request.query_params),
            "headers_count": len(request.headers),
        },
    )

    # Orchestrate the policy flow
    response = await run_policy_flow(
        request=request,
        main_policy=main_policy,
        dependencies=dependencies,
        session=session,
    )

    # Log response details
    logger.info(
        "Proxy response sent",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "client_ip": client_ip,
        },
    )
    return response


# note that /api/{path} GET and POST are the ~same endpoint


@router.post(
    "/api/{full_path:path}",
)
async def api_proxy_endpoint(
    request: Request,
    full_path: str = default_path,
    # --- Core Dependencies ---
    dependencies: DependencyContainer = Depends(get_dependencies),
    main_policy: ControlPolicy = Depends(get_main_control_policy),
    session: AsyncSession = Depends(get_db_session),
    # --- Swagger UI Enhancements ---
    # The 'payload' and 'token' parameters enhance the Swagger UI:
    # - 'payload' (dict[str, Any], optional): Provides a schema for the request body.
    #   Actual body content is read directly from the 'request' object.
    # - 'token' (Optional[str]): Enables the 'Authorize' button (Bearer token).
    #   Actual token validation is handled by the policy flow.
    payload: dict[str, Any] = default_payload,
    token: Optional[str] = Security(http_bearer_auth),
):
    """
    Main API proxy endpoint using the policy orchestration flow.
    Handles requests starting with /api/.
    Uses Dependency Injection Container and provides a DB session.

    **Authentication Note:** This endpoint uses Bearer Token authentication
    (Authorization: Bearer <token>). However, the requirement for a valid token
    depends on whether the currently configured control policy includes client
    authentication (e.g., ClientApiKeyAuthPolicy). If the policy does not require
    authentication, the token field can be left blank.
    """
    return await _handle_api_request(request, main_policy, dependencies, session)


@router.get(
    "/api/{full_path:path}",
)
async def api_proxy_get_endpoint(
    request: Request,
    full_path: str = default_path,
    # --- Core Dependencies ---
    dependencies: DependencyContainer = Depends(get_dependencies),
    main_policy: ControlPolicy = Depends(get_main_control_policy),
    session: AsyncSession = Depends(get_db_session),
    # --- Swagger UI Enhancements ---
    # - 'token' (Optional[str]): Enables the 'Authorize' button (Bearer token).
    #   Actual token validation is handled by the policy flow.
    token: Optional[str] = Security(http_bearer_auth),
):
    """
    Main API proxy endpoint for GET requests using the policy orchestration flow.
    Handles GET requests starting with /api/.
    Uses Dependency Injection Container and provides a DB session.

    **Authentication Note:** This endpoint uses Bearer Token authentication
    (Authorization: Bearer <token>). However, the requirement for a valid token
    depends on whether the currently configured control policy includes client
    authentication (e.g., ClientApiKeyAuthPolicy). If the policy does not require
    authentication, the token field can be left blank.
    """
    return await _handle_api_request(request, main_policy, dependencies, session)


@router.options("/api/{full_path:path}")
async def api_proxy_options_handler(
    full_path: str = default_path,  # Keep for path consistency, though not used in this simple handler
):
    """
    Handles OPTIONS requests for the API proxy endpoint, indicating allowed methods.
    """
    logger.info(f"Explicit OPTIONS request received for /api/{full_path}")
    headers = {
        "Allow": "GET, POST, OPTIONS",
        "Access-Control-Allow-Origin": "*",  # Allow any origin
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",  # Allowed methods
        "Access-Control-Allow-Headers": "Authorization, Content-Type",  # Allowed headers
    }
    return Response(status_code=200, headers=headers)
