import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

# Import Settings class directly for dependency injection
# Import new policy framework components
from luthien_control.control_policy.control_policy import ControlPolicy

# Import the specific builder class we will instantiate
from luthien_control.core.response_builder.default_builder import DefaultResponseBuilder
from luthien_control.dependencies import (
    get_db_session,
    get_dependencies,
    get_main_control_policy,
)
from luthien_control.dependency_container import DependencyContainer

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
    # Core dependencies via Container
    dependencies: DependencyContainer = Depends(get_dependencies),
    main_policy: ControlPolicy = Depends(get_main_control_policy),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Main API proxy endpoint using the policy orchestration flow.
    Handles requests starting with /api/.
    Uses Dependency Injection Container and provides a DB session.
    """
    logger.info(f"Authenticated request received for /api/{full_path}")

    # Instantiate the builder directly
    DefaultResponseBuilder()

    # Orchestrate the policy flow
    response = await run_policy_flow(
        request=request,
        main_policy=main_policy,
        dependencies=dependencies,
        session=session,
    )

    logger.info(f"Returning response for {request.url.path}")
    return response
