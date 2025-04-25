import logging
from typing import Optional

from fastapi import APIRouter, Depends, Request, Security
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.dependencies import (
    get_db_session,
    get_dependencies,
    get_main_control_policy,
)
from luthien_control.dependency_container import DependencyContainer
from luthien_control.proxy.orchestration import run_policy_flow

logger = logging.getLogger(__name__)

router = APIRouter()

# Define the security scheme using HTTPBearer for 'Authorization: Bearer <token>'
# auto_error=False because our ClientApiKeyAuthPolicy handles the missing/invalid key error
http_bearer_auth = HTTPBearer(auto_error=False)


@router.api_route(
    "/api/{full_path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
)
async def api_proxy_endpoint(
    request: Request,
    full_path: str,
    # Use the HTTPBearer scheme. The variable 'token' isn't used directly here,
    # but FastAPI uses this to enable the 'Authorize' button (expecting Bearer token) in Swagger UI.
    # The actual token is extracted from the request header within the policy.
    token: Optional[str] = Security(http_bearer_auth),
    # Core dependencies via Container
    dependencies: DependencyContainer = Depends(get_dependencies),
    main_policy: ControlPolicy = Depends(get_main_control_policy),
    session: AsyncSession = Depends(get_db_session),
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
    logger.info(f"Authenticated request received for /api/{full_path}")

    # Orchestrate the policy flow
    response = await run_policy_flow(
        request=request,
        main_policy=main_policy,
        dependencies=dependencies,
        session=session,
    )

    logger.info(f"Returning response for {request.url.path}")
    return response
