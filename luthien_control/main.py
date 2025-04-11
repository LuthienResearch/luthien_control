import asyncio
import logging
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

# --- BEGIN ADDED LOGGING CONFIG ---
# Configure basic logging to ensure output is captured
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s:%(lineno)d] - %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z",
)
# --- END ADDED LOGGING CONFIG ---

from luthien_control.config.settings import Settings

# Import the specific exception
from luthien_control.db.database import (
    _get_main_db_dsn,  # Import the new helper
    close_log_db_pool,
    close_main_db_pool,
    create_log_db_pool,
    create_main_db_pool,
)

# --- Local Imports --- #
from luthien_control.proxy.server import router as proxy_router

logger = logging.getLogger(__name__)

settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the lifespan of the application resources."""
    logger.info("Application starting up...")

    # Startup: Initialize HTTP client
    timeout = httpx.Timeout(5.0, connect=5.0, read=60.0, write=5.0)
    app.state.http_client = httpx.AsyncClient(timeout=timeout)
    logger.info("HTTP Client initialized.")

    # Startup: Initialize Database Pools
    # Check if the log DB is configured (using old method for now)
    log_db_configured = all(os.getenv(var) for var in ["LOG_DB_USER", "LOG_DB_PASSWORD", "LOG_DB_HOST", "LOG_DB_NAME"])
    # Check if the main DB is configured by seeing if we can get a DSN
    main_db_dsn = _get_main_db_dsn()
    main_db_configured = bool(main_db_dsn)

    if log_db_configured:
        logger.info("Log DB seems configured, attempting to create pool...")
        await create_log_db_pool()
    else:
        logger.warning("Log DB environment variables not fully set. Log DB pool will not be created.")

    if main_db_configured:
        # We already logged the DSN source inside _get_main_db_dsn
        logger.info("Main DB seems configured (DSN determined), attempting to create pool with retries...")
        # --- BEGIN RETRY LOGIC --- #
        max_retries = 3
        retry_delay_seconds = 2
        pool_created = False
        for attempt in range(1, max_retries + 1):
            logger.info(f"Attempting to create main DB pool (Attempt {attempt}/{max_retries})...")
            try:
                await create_main_db_pool()
                # Check if pool was actually created (global variable check)
                # Import locally to avoid potential circular dependency issues at module level
                from luthien_control.db.database import _main_db_pool

                if _main_db_pool:
                    logger.info(f"Main DB pool successfully created on attempt {attempt}.")
                    pool_created = True
                    break  # Exit loop on success
                else:
                    # This case means create_main_db_pool returned without error but pool is still None
                    # (e.g., internal DSN check failed, error logged within create_main_db_pool)
                    logger.warning(f"create_main_db_pool completed on attempt {attempt} but pool is still None.")
                    # No need to retry immediately if create_main_db_pool itself logged an error
            except Exception as pool_exc:
                # Catch broader exceptions during the await itself
                logger.warning(f"Attempt {attempt} failed to create main DB pool: {pool_exc}")

            if not pool_created and attempt < max_retries:
                logger.info(f"Waiting {retry_delay_seconds} seconds before next attempt...")
                await asyncio.sleep(retry_delay_seconds)
            elif not pool_created:
                logger.error(f"Failed to create main DB pool after {max_retries} attempts.")
        # --- END RETRY LOGIC --- #
        if not pool_created:
            logger.error("Continuing startup without a functional main DB pool!")
            # Depending on requirements, you might want to raise an exception here to halt startup
            # raise RuntimeError("Failed to initialize main database connection pool after retries.")
    else:
        logger.warning(
            "Main DB could not be configured (DSN could not be determined). Main DB pool will not be created."
        )

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


# --- Root Endpoint --- #


@app.get("/")
async def read_root():
    return {"message": "Luthien Control Proxy is running."}


# --- Run with Uvicorn (for local development) --- #

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "luthien_control.main:app",
        host=settings.get_app_host(),
        port=settings.get_app_port(),
        reload=settings.get_app_reload(),
        log_level=settings.get_app_log_level().lower(),
    )
