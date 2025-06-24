import logging
from typing import AsyncGenerator

import httpx
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.loader import load_policy_from_file
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.db.control_policy_crud import PolicyLoadError, load_policy_from_db
from luthien_control.db.database_async import create_db_engine
from luthien_control.db.database_async import get_db_session as db_get_session
from luthien_control.settings import Settings

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
    policy_filepath = settings.get_policy_filepath()
    if policy_filepath:
        logger.info(f"Loading main control policy from file: {policy_filepath}")
        return load_policy_from_file(policy_filepath)

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


async def initialize_app_dependencies(app_settings: Settings) -> DependencyContainer:
    """Initialize and configure core application dependencies.

    This function sets up essential services required by the application,
    including an HTTP client and a database connection pool. It encapsulates
    the creation and configuration of these dependencies into a
    DependencyContainer instance.

    Args:
        app_settings: The application settings instance.

    Returns:
        A DependencyContainer instance populated with initialized dependencies.

    Raises:
        RuntimeError: If initialization of the HTTP client or database engine fails.
    """
    logger.info("Initializing core application dependencies...")

    # Initialize HTTP client
    timeout = httpx.Timeout(5.0, connect=5.0, read=60.0, write=5.0)
    http_client = httpx.AsyncClient(timeout=timeout)
    logger.info("HTTP Client initialized for DependencyContainer.")

    # Initialize Database Engine and Session Factory
    try:
        logger.info("Attempting to create main DB engine and session factory for DependencyContainer...")
        _db_engine = await create_db_engine()  # Uses app_settings implicitly via global settings instance
        logger.info("Main DB engine successfully created for DependencyContainer.")
        # Use the actual session factory from database_async module
        db_session_factory = db_get_session
        logger.info("DB Session Factory reference obtained for DependencyContainer.")

    except Exception as db_exc:
        logger.critical(f"Failed to initialize database for DependencyContainer due to exception: {db_exc}")
        await http_client.aclose()  # Clean up HTTP client
        logger.info("HTTP client closed due to DB initialization failure.")
        # No need to call close_db_engine here, as db_engine might not be valid or fully initialized.
        # The caller (lifespan) will handle global engine cleanup if needed.
        raise RuntimeError(f"Failed to initialize database for DependencyContainer: {db_exc}") from db_exc

    # Create and return Dependency Container
    try:
        dependencies = DependencyContainer(
            settings=app_settings,
            http_client=http_client,
            db_session_factory=db_session_factory,
        )
        logger.info("Dependency Container created successfully.")
        return dependencies
    except Exception as container_exc:
        logger.critical(f"Failed to create Dependency Container instance: {container_exc}", exc_info=True)
        # Clean up resources created within this helper function
        await http_client.aclose()
        logger.info("HTTP client closed due to Dependency Container instantiation failure.")
        # If db_engine was successfully created, it's now managed by the global close_db_engine,
        # which will be called by the lifespan's shutdown phase.
        # We don't call close_db_engine(db_engine_instance_if_any) here because the global one handles it.
        raise RuntimeError(f"Failed to create Dependency Container instance: {container_exc}") from container_exc
