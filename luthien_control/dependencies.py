import logging
from typing import AsyncGenerator

import httpx
from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

# Import Settings and the policy loader
from luthien_control.config.settings import Settings

# Import Policies
from luthien_control.control_policy.initialize_context import InitializeContextPolicy
from luthien_control.control_policy.interface import ControlPolicy

# Import Response Builder
from luthien_control.core.response_builder.default_builder import DefaultResponseBuilder
from luthien_control.core.response_builder.interface import ResponseBuilder

# Import SQLModel database session providers
from luthien_control.db.database_async import get_db_session
from luthien_control.db.sqlmodel_crud import (
    ApiKeyLookupFunc,
    PolicyLoadError,
    get_api_key_by_value,
    load_policy_from_db,
)

logger = logging.getLogger(__name__)


# --- Dependency Providers --- #


def get_http_client(request: Request) -> httpx.AsyncClient:
    """
    Dependency function to get the shared httpx.AsyncClient from application state.

    Raises:
        HTTPException: If the client is not found in the application state.
    """
    client: httpx.AsyncClient | None = getattr(request.app.state, "http_client", None)
    if client is None:
        # This indicates a critical setup error if the lifespan manager didn't run
        # or didn't set the state correctly.
        logger.critical("!!! CRITICAL ERROR: httpx.AsyncClient not found in request.app.state")
        raise HTTPException(status_code=500, detail="Internal server error: HTTP client not available.")
    return client


# --- Async Database Session Dependency ---

async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency to get an async database session."""
    try:
        async with get_db_session() as session:
            yield session
    except RuntimeError as e:
        # Handle case where session factory isn't initialized (e.g., during startup)
        logger.error(f"Database session could not be created: {e}")
        # Depending on the desired behavior, you might:
        # 1. Re-raise the exception:
        #    raise HTTPException(status_code=503, detail="Database not available")
        # 2. Yield None (callers must handle None session):
        yield None # Be cautious with this, ensure callers check!
        # 3. Log and continue (if a session isn't strictly required? Risky):
        #    pass
    except Exception as e:
        logger.exception(f"An unexpected error occurred getting DB session: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


def get_initial_context_policy() -> InitializeContextPolicy:
    """Provides an instance of the InitializeContextPolicy."""
    return InitializeContextPolicy()


# --- Main Control Policy Dependency ---


async def get_main_control_policy(
    settings: Settings = Depends(Settings),
    http_client: httpx.AsyncClient = Depends(get_http_client),  # Inject http_client correctly
    session: AsyncSession = Depends(get_async_db),  # Inject AsyncSession via get_async_db
) -> ControlPolicy:  # Return a single policy instance
    """
    Dependency to load and provide the main, top-level ControlPolicy instance
    based on the configuration name specified in settings.

    Injects necessary dependencies (settings, http_client, api_key_lookup, session)
    into the policy loading mechanism.
    """
    # First, check if the policy name is configured
    top_level_policy_name = settings.get_top_level_policy_name()
    if not top_level_policy_name:
        logger.error("TOP_LEVEL_POLICY_NAME is not configured in settings.")
        # Raise the specific error here, outside the main try/except for loading
        raise HTTPException(status_code=500, detail="Internal server error: Control policy name not configured.")

    # If the name exists, proceed with loading attempt
    try:
        # Pass the injected dependencies and the function reference for lookup
        api_key_lookup: ApiKeyLookupFunc = get_api_key_by_value  # Use correct type hint

        # Use the injected session directly
        main_policy = await load_policy_from_db(
            name=top_level_policy_name,
            settings=settings,
            http_client=http_client,  # Pass the client obtained via Depends
            api_key_lookup=api_key_lookup,  # Pass the lookup function reference
            session=session,  # Use the injected session
        )
        if not main_policy:  # load_policy_from_db might return None if not found
            logger.error(f"Main control policy '{top_level_policy_name}' could not be loaded (not found or inactive).")
            raise HTTPException(
                status_code=500,
                detail=f"Internal server error: Main control policy '{top_level_policy_name}' not found or inactive.",
            )

        return main_policy
    except PolicyLoadError as e:  # Catch specific loading errors from crud.load_policy_from_db
        logger.exception(f"Failed to load main control policy '{top_level_policy_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: Could not load main control policy. {e}")
    except Exception as e:
        logger.exception(f"Unexpected error loading main control policy '{top_level_policy_name}': {e}")
        raise HTTPException(
            status_code=500, detail="Internal server error: Unexpected issue loading main control policy."
        )


def get_response_builder() -> ResponseBuilder:
    """Provides an instance of the DefaultResponseBuilder."""
    return DefaultResponseBuilder()
