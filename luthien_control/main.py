import logging
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from luthien_control.db.database import close_log_db_pool, close_main_db_pool, create_log_db_pool, create_main_db_pool

# --- Local Imports --- #
from luthien_control.proxy.server import router as proxy_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the lifespan of the application resources."""
    logger.info("Application starting up...")

    # Startup: Initialize HTTP client
    timeout = httpx.Timeout(5.0, connect=5.0, read=60.0, write=5.0)
    app.state.http_client = httpx.AsyncClient(timeout=timeout)
    logger.info("HTTP Client initialized.")

    # Startup: Initialize Database Pools
    # Check if the necessary DB configs are present before attempting to create pools
    log_db_configured = all(os.getenv(var) for var in ["LOG_DB_USER", "LOG_DB_PASSWORD", "LOG_DB_HOST", "LOG_DB_NAME"])
    main_db_configured = all(
        os.getenv(var) for var in ["POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_HOST", "POSTGRES_DB"]
    )

    if log_db_configured:
        logger.info("Log DB seems configured, attempting to create pool...")
        await create_log_db_pool()
    else:
        logger.warning("Log DB environment variables not fully set. Log DB pool will not be created.")

    if main_db_configured:
        logger.info("Main DB seems configured, attempting to create pool...")
        await create_main_db_pool()
    else:
        logger.warning("Main DB environment variables not fully set. Main DB pool will not be created.")

    yield

    # Shutdown: Close Database Pools
    logger.info("Application shutting down...")
    await close_log_db_pool()
    await close_main_db_pool()

    # Shutdown: Close the HTTP client
    if hasattr(app.state, "http_client") and app.state.http_client:
        await app.state.http_client.aclose()
        logger.info("HTTP Client closed.")
    else:
        logger.warning("HTTP Client not found in app state during shutdown.")

    logger.info("Application shutdown complete.")


# Instantiate settings once if needed elsewhere, though lifespan uses os.getenv directly
# settings = Settings()

app = FastAPI(
    title="Luthien Control",
    description="An intelligent proxy server for AI APIs.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["General"], status_code=200)
async def health_check():
    """Basic health check endpoint."""
    # Could potentially add checks for DB connections here in the future
    return {"status": "ok"}


# Include the proxy router
app.include_router(proxy_router)

# Further endpoints (like the main proxy endpoint) will be added here.

# To run the server (from the project root directory):
# uvicorn luthien_control.main:app --reload
