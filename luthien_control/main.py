import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from luthien_control.admin.auth import admin_auth_service
from luthien_control.admin.router import router as admin_router
from luthien_control.core.dependencies import get_db_session, initialize_app_dependencies
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.logging import setup_logging
from luthien_control.custom_openapi_schema import create_custom_openapi
from luthien_control.db.database_async import close_db_engine
from luthien_control.logs.router import router as logs_router
from luthien_control.proxy.server import router as proxy_router
from luthien_control.settings import Settings

setup_logging()


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the lifespan of the application resources.

    This asynchronous context manager handles the startup and shutdown events
    of the FastAPI application. It initializes dependencies on startup
    and ensures they are properly cleaned up on shutdown.

    Args:
        app: The FastAPI application instance.

    Yields:
        None: After startup procedures are complete, allowing the application to run.

    Raises:
        RuntimeError: If critical application dependencies fail to initialize during startup.
    """
    logger.info("Application startup sequence initiated.")

    # Startup: Load Settings
    app_settings = Settings()
    logger.info("Settings loaded.")

    # Startup: Initialize Application Dependencies via helper
    # This variable will hold the container if successfully created.
    initialized_dependencies: DependencyContainer | None = None
    try:
        initialized_dependencies = await initialize_app_dependencies(app_settings)
        app.state.dependencies = initialized_dependencies
        logger.info("Core application dependencies initialized and stored in app state.")

        # Ensure default admin user exists
        async for db in get_db_session(initialized_dependencies):
            await admin_auth_service.ensure_default_admin(db)
            break

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
    await initialized_dependencies.http_client.aclose()
    logger.info("HTTP Client from DependencyContainer closed.")

    logger.info("Application shutdown complete.")


app = FastAPI(
    title="Luthien Control",
    description="An intelligent proxy server for AI APIs.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins including vscode-file://
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["General"], status_code=200)
async def health_check():
    """Perform a basic health check.

    This endpoint can be used to verify that the application is running
    and responsive.

    Returns:
        A dictionary indicating the application status.
    """
    return {"status": "ok"}


app.include_router(proxy_router)
app.include_router(logs_router)
app.include_router(admin_router)


# --- Root Endpoint --- #


@app.get("/")
async def read_root():
    """Provide a simple root endpoint.

    Returns:
        A welcome message indicating the proxy is running.
    """
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
        log_level=dev_settings.get_log_level().lower(),
    )
