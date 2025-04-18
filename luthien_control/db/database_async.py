import logging
import os
from typing import AsyncGenerator, Optional
from urllib.parse import urlparse, urlunparse

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

logger = logging.getLogger(__name__)

# Global variables for async engines and session factories
_log_db_engine: Optional[AsyncEngine] = None
_main_db_engine: Optional[AsyncEngine] = None

_log_db_session_factory = None
_main_db_session_factory = None


def _get_main_db_url() -> Optional[str]:
    """Determines the main database URL, prioritizing DATABASE_URL."""
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        logger.info("Using DATABASE_URL for main database connection.")
        # Convert to async URL if needed
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return database_url

    logger.warning("DATABASE_URL not found. Falling back to individual DB_* variables.")
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT", "5432")  # Default port

    # Use DB_NAME_NEW for the database name
    db_name = os.getenv("DB_NAME_NEW")

    # Log which database name variable was used
    if db_name:
        logger.debug("Using DB_NAME_NEW for SQLModel connection")
    # Removed fallback logging for DB_NAME_NEW

    if not all([db_user, db_password, db_host, db_name]):
        logger.error(
            "Missing one or more required DB_* environment variables "
            "(DB_USER, DB_PASSWORD, DB_HOST, DB_NAME_NEW) " # Updated error message
            "when DATABASE_URL is not set."
        )
        return None

    async_url = f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    logger.info(
        f"Constructed main database URL from individual variables: "
        f"postgresql+asyncpg://{db_user}:***@{db_host}:{db_port}/{db_name}"
    )
    return async_url


def _get_log_db_url() -> Optional[str]:
    """Determines the logging database URL."""
    # For logging DB we still use individual vars
    log_db_user = os.getenv("LOG_DB_USER")
    log_db_password = os.getenv("LOG_DB_PASSWORD")
    log_db_host = os.getenv("LOG_DB_HOST")
    log_db_port = os.getenv("LOG_DB_PORT", "5432")
    log_db_name = os.getenv("LOG_DB_NAME")

    if all([log_db_user, log_db_password, log_db_host, log_db_name]):
        async_url = f"postgresql+asyncpg://{log_db_user}:{log_db_password}@{log_db_host}:{log_db_port}/{log_db_name}"
        logger.info(
            f"Constructed logging database URL: "
            f"postgresql+asyncpg://{log_db_user}:***@{log_db_host}:{log_db_port}/{log_db_name}"
        )
        return async_url
    else:
        logger.error("Missing essential logging database connection environment variables")
        return None


async def create_main_db_engine() -> Optional[AsyncEngine]:
    """Creates the asyncpg engine for the main application DB."""
    global _main_db_engine, _main_db_session_factory
    if _main_db_engine:
        logger.warning("Main database engine already initialized.")
        return _main_db_engine

    logger.info("Attempting to create main database engine...")
    db_url = _get_main_db_url()
    if not db_url:
        logger.error("Failed to determine main database URL.")
        return None

    try:
        # Get and validate pool sizes
        pool_min_size = int(os.getenv("MAIN_DB_POOL_MIN_SIZE", "1"))
        pool_max_size = int(os.getenv("MAIN_DB_POOL_MAX_SIZE", "10"))

        _main_db_engine = create_async_engine(
            db_url,
            echo=False,  # Set to True for debugging SQL queries
            pool_pre_ping=True,
            pool_size=pool_min_size,
            max_overflow=pool_max_size - pool_min_size,
        )

        _main_db_session_factory = async_sessionmaker(
            _main_db_engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )

        logger.info("Main database engine created successfully.")
        return _main_db_engine
    except Exception as e:
        masked_url = db_url
        if db_url:
            parsed = urlparse(db_url)
            if parsed.password:
                masked_url = urlunparse(
                    parsed._replace(netloc=f"{parsed.username}:***@{parsed.hostname}:{parsed.port}")
                )
        logger.exception(f"Failed to create main database engine using URL ({masked_url}): {e}")
        return None


async def create_log_db_engine() -> Optional[AsyncEngine]:
    """Creates the asyncpg engine for the logging DB."""
    global _log_db_engine, _log_db_session_factory
    if _log_db_engine:
        logger.warning("Logging database engine already initialized.")
        return _log_db_engine

    logger.info("Attempting to create logging database engine...")
    db_url = _get_log_db_url()
    if not db_url:
        logger.error("Failed to determine logging database URL.")
        return None

    try:
        # Get and validate pool sizes
        pool_min_size = int(os.getenv("LOG_DB_POOL_MIN_SIZE", "1"))
        pool_max_size = int(os.getenv("LOG_DB_POOL_MAX_SIZE", "10"))

        _log_db_engine = create_async_engine(
            db_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=pool_min_size,
            max_overflow=pool_max_size - pool_min_size,
        )

        _log_db_session_factory = async_sessionmaker(
            _log_db_engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )

        logger.info("Logging database engine created successfully.")
        return _log_db_engine
    except Exception as e:
        masked_url = db_url
        if db_url:
            parsed = urlparse(db_url)
            if parsed.password:
                masked_url = urlunparse(
                    parsed._replace(netloc=f"{parsed.username}:***@{parsed.hostname}:{parsed.port}")
                )
        logger.exception(f"Failed to create logging database engine using URL ({masked_url}): {e}")
        return None


async def close_main_db_engine() -> None:
    """Closes the main database engine."""
    global _main_db_engine
    if _main_db_engine:
        try:
            await _main_db_engine.dispose()
            logger.info("Main database engine closed successfully.")
        except Exception as e:
            logger.error(f"Error closing main database engine: {e}", exc_info=True)
        finally:
            _main_db_engine = None
    else:
        logger.info("Main database engine was already None or not initialized during shutdown.")


async def close_log_db_engine() -> None:
    """Closes the logging database engine."""
    global _log_db_engine
    if _log_db_engine:
        try:
            await _log_db_engine.dispose()
            logger.info("Logging database engine closed successfully.")
        except Exception as e:
            logger.error(f"Error closing logging database engine: {e}", exc_info=True)
        finally:
            _log_db_engine = None
    else:
        logger.info("Logging database engine was already None or not initialized during shutdown.")


async def get_main_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a SQLAlchemy async session for the main database."""
    if _main_db_session_factory is None:
        raise RuntimeError("Main database session factory has not been initialized")

    async with _main_db_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def get_log_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a SQLAlchemy async session for the logging database."""
    if _log_db_session_factory is None:
        raise RuntimeError("Logging database session factory has not been initialized")

    async with _log_db_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def create_db_and_tables():
    """Create all tables defined in SQLModel models if they don't exist."""
    if _main_db_engine:
        async with _main_db_engine.begin() as conn:
            # Import all model classes here to ensure they're included in metadata

            await conn.run_sync(SQLModel.metadata.create_all)
