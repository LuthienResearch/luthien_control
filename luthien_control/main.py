import logging
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

import luthien_control.db.database
from luthien_control.config.settings import Settings
from luthien_control.db.database import (
    _get_main_db_dsn,
    close_log_db_pool,
    close_main_db_pool,
    create_log_db_pool,
    create_main_db_pool,
)
from luthien_control.logging_config import setup_logging
from luthien_control.proxy.server import router as proxy_router

setup_logging()


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
        logger.info("Main DB seems configured (DSN determined), attempting to create pool...")
        try:
            await create_main_db_pool()
            # Check if pool was actually created via the module namespace
            if not luthien_control.db.database._main_db_pool:
                # This case means create_main_db_pool returned without error but pool is still None
                # (e.g., internal DSN check failed, error logged within create_main_db_pool)
                logger.critical("create_main_db_pool completed but pool is None (checked via module). Halting startup.")
                raise RuntimeError("Failed to initialize main database connection pool.")
            else:
                logger.info("Main DB pool successfully created (checked via module).")
        except Exception as pool_exc:
            # Catch exceptions during the await itself
            logger.critical(f"Failed to create main DB pool due to exception: {pool_exc}", exc_info=True)
            raise RuntimeError(f"Failed to initialize main database connection pool: {pool_exc}") from pool_exc
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
