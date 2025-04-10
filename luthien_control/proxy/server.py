import logging

# import uuid # Removed: No longer used
from typing import Any, Dict, List, Sequence, Tuple  # Removed Union
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
    get_current_active_api_key,
    get_http_client,
    get_initial_context_policy,
    # get_policy, # Already removed
    get_response_builder,
)
# from luthien_control.policies.base import Policy # Already removed

# Import the orchestrator
from luthien_control.proxy.orchestration import run_policy_flow

# Import the ApiKey model for type hinting
from luthien_control.db.models import ApiKey

logger = logging.getLogger(__name__)

router = APIRouter()

# --- Dependency Providers ---

# Existing provider for HTTP client
# ... (get_http_client defined in luthien_control.dependencies)


# === NEW API PROXY ENDPOINT ===
# Replaces the previous /beta and catch-all endpoints
@router.api_route(
    "/api/{full_path:path}",  # Changed path from /beta/...
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
    dependencies=[Depends(get_current_active_api_key)],
)
async def api_proxy_endpoint(  # Renamed from proxy_endpoint_beta
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
    logger.info(f"Authenticated request received for /api/{full_path}")  # Updated log

    # Orchestrate the policy flow
    response = await run_policy_flow(
        request=request,
        http_client=client,
        settings=settings,
        initial_context_policy=initial_context_policy,
        policies=policies,
        builder=builder,
    )

    logger.info(f"Returning response for /api/{full_path}")  # Updated log
    return response


# --- Helper Functions / Original v1 Logic Helpers ---
# (Removed original proxy endpoint)
