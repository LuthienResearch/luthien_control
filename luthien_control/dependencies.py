import logging
from typing import TYPE_CHECKING, AsyncGenerator

import httpx
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

# Import Settings and the policy loader
from luthien_control.config.settings import Settings
from luthien_control.control_policy.control_policy import ControlPolicy

# Import Policies
# Import Response Builder
from luthien_control.db.control_policy_crud import PolicyLoadError, load_policy_from_db

# Import SQLModel database session providers
from luthien_control.dependency_container import DependencyContainer

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# --- Dependency Providers --- #


def get_dependencies(request: Request) -> DependencyContainer:
    """Dependency to retrieve the DependencyContainer from application state."""
    dependencies: DependencyContainer | None = getattr(request.app.state, "dependencies", None)
    if dependencies is None:
        logger.critical(
            "DependencyContainer not found in application state. "
            "This indicates a critical setup error in the application lifespan."
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error: Application dependencies not initialized.",
        )
    return dependencies


# TODO: Remove these, consolidate into container
def get_settings(dependencies: DependencyContainer = Depends(get_dependencies)) -> Settings:
    """Dependency to get the Settings instance from the container."""
    return dependencies.settings


def get_http_client(dependencies: DependencyContainer = Depends(get_dependencies)) -> httpx.AsyncClient:
    """Dependency to get the shared httpx.AsyncClient from the container."""
    return dependencies.http_client


# --- Async Database Session Dependency using Container ---


async def get_db_session(
    dependencies: DependencyContainer = Depends(get_dependencies),
) -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency to get an async database session using the container's factory."""
    session_factory = dependencies.db_session_factory
    if session_factory is None:
        # This shouldn't happen if the container is initialized correctly
        logger.critical("DB Session Factory not found in DependencyContainer.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error: Database session factory not available.",
        )

    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            # The session context manager should handle commit/close,
            # but rollback is explicit on exception.
            pass


# --- Main Control Policy Dependency using Container ---


async def get_main_control_policy(
    dependencies: DependencyContainer = Depends(get_dependencies),
) -> ControlPolicy:
    """
    Dependency to load and provide the main ControlPolicy instance.

    Uses the DependencyContainer to access settings, http_client, and a database session.
    """
    settings = dependencies.settings

    top_level_policy_name = settings.get_top_level_policy_name()
    if not top_level_policy_name:
        logger.error("TOP_LEVEL_POLICY_NAME is not configured in settings.")
        raise HTTPException(status_code=500, detail="Internal server error: Control policy name not configured.")

    try:
        # Get a session using the container's factory - No longer needed here, load_policy_from_db handles it
        # async with session_factory() as session:
        # Pass the container directly to load_policy_from_db
        main_policy = await load_policy_from_db(
            name=top_level_policy_name,
            container=dependencies,  # Pass the whole container
            # settings=settings,  # Removed
            # http_client=http_client,  # Removed
            # session=session,  # Removed
        )

        if not main_policy:
            logger.error(f"Main control policy '{top_level_policy_name}' could not be loaded (not found or inactive).")
            raise HTTPException(
                status_code=500,
                detail=f"Internal server error: Main control policy '{top_level_policy_name}' not found or inactive.",
            )

        return main_policy

    except PolicyLoadError as e:
        logger.exception(f"Failed to load main control policy '{top_level_policy_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: Could not load main control policy. {e}")
    except HTTPException:  # Re-raise HTTPExceptions from session creation
        raise
    except Exception as e:
        logger.exception(f"Unexpected error loading main control policy '{top_level_policy_name}': {e}")
        raise HTTPException(
            status_code=500, detail="Internal server error: Unexpected issue loading main control policy."
        )
