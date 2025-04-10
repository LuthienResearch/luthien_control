import logging
from typing import Sequence

import httpx
from fastapi import APIRouter, Depends, Request

# Import Settings class directly for dependency injection
from luthien_control.config.settings import Settings

# Import new policy framework components
from luthien_control.control_policy.initialize_context import InitializeContextPolicy
from luthien_control.control_policy.interface import ControlPolicy

# Import concrete builder
from luthien_control.core.response_builder.interface import ResponseBuilder

# Import dependency providers from dependencies module
from luthien_control.dependencies import (
    get_control_policies,
    get_http_client,
    get_initial_context_policy,
    get_response_builder,
)

# Import the orchestrator
from luthien_control.proxy.orchestration import run_policy_flow

logger = logging.getLogger(__name__)

router = APIRouter()


# === NEW API PROXY ENDPOINT ===
# Replaces the previous /beta and catch-all endpoints
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
    # New framework dependencies (using implemented providers)
    initial_context_policy: InitializeContextPolicy = Depends(get_initial_context_policy),
    policies: Sequence[ControlPolicy] = Depends(get_control_policies),
    builder: ResponseBuilder = Depends(get_response_builder),
):
    """
    Main API proxy endpoint using the policy orchestration flow.
    Handles requests starting with /api/.
    Requires valid API key authentication.
    """
    logger.info(f"Authenticated request received for /api/{full_path}")

    # Orchestrate the policy flow
    response = await run_policy_flow(
        request=request,
        http_client=client,
        settings=settings,
        initial_context_policy=initial_context_policy,
        policies=policies,
        builder=builder,
    )

    logger.info(f"Returning response for /api/{full_path}")
    return response
