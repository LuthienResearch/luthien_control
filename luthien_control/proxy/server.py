import logging

import httpx
from fastapi import APIRouter, Depends, Request

# Import Settings class directly for dependency injection
from luthien_control.config.settings import Settings

# Import new policy framework components
from luthien_control.control_policy.control_policy import ControlPolicy

# Import concrete builder
from luthien_control.core.response_builder.interface import ResponseBuilder

# Import the specific builder class we will instantiate
from luthien_control.core.response_builder.default_builder import DefaultResponseBuilder

# Import dependency providers from dependencies module
from luthien_control.dependencies import (
    get_http_client,
    get_main_control_policy,
    # Removed get_response_builder as it's no longer used
    # get_response_builder,
)

# Import the orchestrator
from luthien_control.proxy.orchestration import run_policy_flow

logger = logging.getLogger(__name__)

router = APIRouter()


@router.api_route(
    "/api/{full_path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
)
async def api_proxy_endpoint(
    request: Request,
    full_path: str,
    # Common dependencies
    client: httpx.AsyncClient = Depends(get_http_client),
    settings: Settings = Depends(Settings),
    main_policy: ControlPolicy = Depends(get_main_control_policy),
    # Removed ResponseBuilder dependency
    # builder: ResponseBuilder = Depends(get_response_builder),
):
    """
    Main API proxy endpoint using the policy orchestration flow.
    Handles requests starting with /api/.
    Requires valid API key authentication.
    """
    logger.info(f"Authenticated request received for /api/{full_path}")

    # Instantiate the builder directly
    builder = DefaultResponseBuilder()

    # Orchestrate the policy flow
    response = await run_policy_flow(
        request=request,
        main_policy=main_policy,
        builder=builder,
    )

    logger.info(f"Returning response for {request.url.path}")
    return response
