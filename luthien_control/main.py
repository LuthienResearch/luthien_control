import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.logging import setup_logging
from luthien_control.custom_openapi_schema import create_custom_openapi
from luthien_control.db.database_async import (
    close_db_engine,
    create_db_engine,
    get_db_session,
)
from luthien_control.proxy.server import router as proxy_router
from luthien_control.settings import Settings

setup_logging()


logger = logging.getLogger(__name__)


async def _initialize_app_dependencies(app_settings: Settings) -> DependencyContainer:
    """Helper function to initialize and configure core application dependencies."""
    logger.info("Initializing core application dependencies...")

    # Initialize HTTP client
    timeout = httpx.Timeout(5.0, connect=5.0, read=60.0, write=5.0)
    http_client = httpx.AsyncClient(timeout=timeout)
    logger.info("HTTP Client initialized for DependencyContainer.")

    # Initialize Database Engine and Session Factory
    db_engine = None
    try:
        logger.info("Attempting to create main DB engine and session factory for DependencyContainer...")
        db_engine = await create_db_engine()  # Uses app_settings implicitly via global settings instance
        if not db_engine:
            # This path indicates a failure in create_db_engine itself, not an exception.
            logger.critical("create_db_engine() returned None during dependency initialization.")
            await http_client.aclose()  # Clean up already created client
            logger.info("HTTP Client closed due to DB engine returning None.")
            raise RuntimeError("Failed to initialize database connection engine for DependencyContainer.")
        logger.info("Main DB engine successfully created for DependencyContainer.")
        # get_db_session itself uses the factory initialized by create_db_engine
        db_session_factory = get_db_session
        logger.info("DB Session Factory reference obtained for DependencyContainer.")

    except Exception as engine_exc:
        logger.critical(
            f"Failed to initialize database for DependencyContainer due to exception: {engine_exc}", exc_info=True
        )
        await http_client.aclose()  # Clean up client
        logger.info("HTTP Client closed due to DB initialization failure.")
        # No need to call close_db_engine here, as db_engine might not be valid or fully initialized.
        # The caller (lifespan) will handle global engine cleanup if needed.
        raise RuntimeError(f"Failed to initialize database for DependencyContainer: {engine_exc}") from engine_exc

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
        logger.info("HTTP Client closed due to Dependency Container instantiation failure.")
        # If db_engine was successfully created, it's now managed by the global close_db_engine,
        # which will be called by the lifespan's shutdown phase.
        # We don't call close_db_engine(db_engine_instance_if_any) here because the global one handles it.
        raise RuntimeError(f"Failed to create Dependency Container instance: {container_exc}") from container_exc


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the lifespan of the application resources."""
    logger.info("Application startup sequence initiated.")

    # Startup: Load Settings
    app_settings = Settings()
    logger.info("Settings loaded.")

    # Startup: Initialize Application Dependencies via helper
    # This variable will hold the container if successfully created.
    initialized_dependencies: DependencyContainer | None = None
    try:
        initialized_dependencies = await _initialize_app_dependencies(app_settings)
        app.state.dependencies = initialized_dependencies
        logger.info("Core application dependencies initialized and stored in app state.")

    except Exception as init_exc:
        # _initialize_app_dependencies is responsible for cleaning up resources it
        # attempted to create (like its own http_client) if it fails internally.
        # The main concern here is logging and ensuring the app doesn't start.
        logger.critical(f"Fatal error during application dependency initialization: {init_exc}", exc_info=True)
        # If _initialize_app_dependencies failed before creating db_engine, close_db_engine is safe.
        # If it failed *after* db_engine creation but before container, db_engine might be open.
        # The helper itself doesn't call close_db_engine(); it expects lifespan to do so.
        # Global close_db_engine handles if engine was never set or already closed.
        await close_db_engine()
        logger.info("DB Engine closed due to dependency initialization failure during startup.")
        # Re-raise to prevent application from starting up in a bad state.
        raise RuntimeError(
            f"Application startup failed due to dependency initialization error: {init_exc}"
        ) from init_exc

    yield  # Application runs here

    # Shutdown: Clean up resources
    logger.info("Application shutdown sequence initiated.")

    # Close main DB engine (handles its own check if already closed or never initialized)
    await close_db_engine()
    logger.info("Main DB Engine closed.")

    # Shutdown: Close the HTTP client via the container if available
    if initialized_dependencies and initialized_dependencies.http_client:
        await initialized_dependencies.http_client.aclose()
        logger.info("HTTP Client from DependencyContainer closed.")
    # Fallback for http_client if it was somehow created outside the container and put in app.state
    # This specific fallback might become less relevant if _initialize_app_dependencies is the sole provider.
    elif hasattr(app.state, "http_client") and app.state.http_client is not None:
        logger.warning("Closing HTTP Client via direct app.state access (fallback). This may indicate an issue.")
        try:
            await app.state.http_client.aclose()
            logger.info("HTTP Client (fallback) closed.")
        except Exception as e:
            logger.error(f"Error closing fallback HTTP client: {e}", exc_info=True)
    else:
        logger.info("HTTP Client not found or already handled during shutdown.")

    logger.info("Application shutdown complete.")


app = FastAPI(
    title="Luthien Control",
    description="An intelligent proxy server for AI APIs.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["General"], status_code=200)
async def health_check():
    """Basic health check endpoint."""
    return {"status": "ok"}


app.include_router(proxy_router)


# --- Root Endpoint --- #


@app.get("/")
async def read_root():
    return {"message": "Luthien Control Proxy is running."}


# --- OpenAPI Customization --- #

# Assign the custom OpenAPI function generator
# Use a lambda to pass the app instance when the schema is requested
app.openapi = lambda: create_custom_openapi(app)

# --- Run with Uvicorn (for local development) --- #

if __name__ == "__main__":
    import uvicorn

    # Load settings here specifically for running uvicorn if needed,
    # otherwise rely on the lifespan settings
    dev_settings = Settings()
    uvicorn.run(
        "luthien_control.main:app",
        host=dev_settings.get_app_host(),
        port=dev_settings.get_app_port(),
        reload=dev_settings.get_app_reload(),
        log_level=dev_settings.get_app_log_level().lower(),
    )
