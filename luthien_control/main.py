import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.logging import setup_logging
from luthien_control.db.database_async import (
    close_db_engine,
    create_db_engine,
    get_db_session,
)
from luthien_control.proxy.server import router as proxy_router
from luthien_control.settings import Settings
from luthien_control.utils import create_custom_openapi

setup_logging()


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the lifespan of the application resources."""
    logger.info("Application startup sequence initiated.")

    # Startup: Load Settings
    app_settings = Settings()
    logger.info("Settings loaded.")

    # Startup: Initialize HTTP client
    timeout = httpx.Timeout(5.0, connect=5.0, read=60.0, write=5.0)
    http_client = httpx.AsyncClient(timeout=timeout)
    logger.info("HTTP Client initialized.")

    # Startup: Initialize Database Engine and Session Factory
    logger.info("Attempting to create main DB engine and session factory...")
    try:
        db_engine = await create_db_engine()
        if not db_engine:
            logger.critical("create_db_engine() failed. Halting startup.")
            raise RuntimeError("Failed to initialize database connection engine.")
        logger.info("Main DB engine successfully created.")
        # get_db_session itself uses the factory initialized by create_db_engine
        db_session_factory = get_db_session
        logger.info("DB Session Factory reference obtained.")

    except Exception as engine_exc:
        logger.critical(f"Failed to initialize database due to exception: {engine_exc}", exc_info=True)
        # Ensure client is closed if DB setup fails mid-startup
        await http_client.aclose()
        logger.info("HTTP Client closed due to startup failure.")
        raise RuntimeError(f"Failed to initialize database: {engine_exc}") from engine_exc

    # Startup: Create and store Dependency Container
    try:
        dependencies = DependencyContainer(
            settings=app_settings,
            http_client=http_client,
            db_session_factory=db_session_factory,
        )
        app.state.dependencies = dependencies
        logger.info("Dependency Container created and stored in app state.")
    except Exception as dependencies_exc:
        logger.critical(f"Failed to create Dependency Container: {dependencies_exc}", exc_info=True)
        # Clean up already created resources
        await http_client.aclose()
        logger.info("HTTP Client closed due to dependencies container creation failure.")
        await close_db_engine()  # Close DB engine as well
        logger.info("DB Engine closed due to dependencies container creation failure.")
        raise RuntimeError(f"Failed to create Dependency Container: {dependencies_exc}") from dependencies_exc

    yield  # Application runs here

    # Shutdown: Clean up resources
    logger.info("Application shutdown sequence initiated.")

    # Retrieve container and client from app state for cleanup
    container_to_close = app.state.container if hasattr(app.state, "container") else None
    http_client_to_close = container_to_close.http_client if container_to_close else None

    # Close main DB engine (handles its own check if already closed)
    await close_db_engine()

    # Shutdown: Close the HTTP client via the container if available
    if http_client_to_close:
        await http_client_to_close.aclose()
        logger.info("HTTP Client closed via container.")
    elif hasattr(app.state, "http_client"):  # Fallback if container wasn't created/stored properly
        # This fallback might be removable if container creation is robust
        logger.warning("Closing HTTP Client via direct app.state access (fallback).")
        await app.state.http_client.aclose()
        logger.info("HTTP Client closed (fallback).")
    else:
        logger.warning("HTTP Client not found in app state or container during shutdown.")

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
