import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from luthien_control.config.settings import Settings
from luthien_control.db.database import (
    _get_main_db_dsn,
    close_main_db_pool,
    create_main_db_pool,
)
from luthien_control.db.database_async import (
    create_main_db_engine,
)
from luthien_control.logging_config import setup_logging
from luthien_control.proxy.server import router as proxy_router

setup_logging()


logger = logging.getLogger(__name__)

settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the lifespan of the application resources."""
    logger.info("Application startup sequence initiated.")

    # Startup: Initialize HTTP client
    timeout = httpx.Timeout(5.0, connect=5.0, read=60.0, write=5.0)
    app.state.http_client = httpx.AsyncClient(timeout=timeout)
    logger.info("HTTP Client initialized.")

    # Startup: Initialize Database Pools
    # Check if the main DB is configured by seeing if we can get a DSN
    main_db_dsn = _get_main_db_dsn()
    main_db_configured = bool(main_db_dsn)

    if main_db_configured:
        logger.info("Main DB seems configured (DSN/URL determined), attempting to create engine...")
        try:
            # Create the engine
            main_db_engine = await create_main_db_engine()
            # Check if engine was successfully created
            if not main_db_engine:
                # Errors during creation are logged within create_main_db_engine
                logger.critical("create_main_db_engine() failed (returned None). Halting startup.")
                raise RuntimeError("Failed to initialize main database connection engine.")
            else:
                logger.info("Main DB engine successfully created.")
                # Optionally check via module namespace if needed, though direct check is better
                # assert luthien_control.db.database_async._main_db_engine is not None
        except Exception as engine_exc:
            # Catch exceptions during the await itself
            logger.critical(f"Failed to create main DB engine due to exception: {engine_exc}", exc_info=True)
            raise RuntimeError(f"Failed to initialize main database connection engine: {engine_exc}") from engine_exc
    else:
        logger.warning(
            "Main DB could not be configured (URL could not be determined). Main DB engine will not be created."
        )

    # Initialize main DB pool
    await create_main_db_pool()

    yield

    # Shutdown: Clean up resources
    logger.info("Application shutdown sequence initiated.")
    # Close main DB pool
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
