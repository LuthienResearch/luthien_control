import contextlib
import logging
from typing import AsyncGenerator, Optional
from urllib.parse import urlparse, urlunparse

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from luthien_control.exceptions import LuthienDBConfigurationError, LuthienDBConnectionError
from luthien_control.settings import Settings

logger = logging.getLogger(__name__)

# Global variables for async engines and session factories
_db_engine: Optional[AsyncEngine] = None

_db_session_factory = None

settings = Settings()


def _mask_password(url: str) -> str:
    """Masks the password in the database URL."""
    parsed = urlparse(url)
    if parsed.password:
        return urlunparse(parsed._replace(netloc=f"{parsed.username}:***@{parsed.hostname}:{parsed.port}"))
    return url


def _get_db_url() -> str:
    """Determines the database URL, converting to asyncpg URL if needed

    Returns:
        The database URL as a string.

    Raises:
        LuthienDBConfigurationError: If missing required variables.
    """
    database_url = settings.get_database_url()

    if database_url:
        logger.info("Using DATABASE_URL for database connection.")

        # Convert to async URL if needed
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)

        return database_url

    logger.info("DATABASE_URL not found. Falling back to individual DB_* variables.")

    db_vars = dict(
        user=settings.get_postgres_user(),
        password=settings.get_postgres_password(),
        host=settings.get_postgres_host(),
        port=settings.get_postgres_port(),
        dbname=settings.get_postgres_db(),
    )

    if not all(db_vars.values()):
        missing_vars = [k.upper() for k, v in db_vars.items() if v is None]
        raise LuthienDBConfigurationError(
            f"DATABASE_URL not set, and missing required DB_* variables to construct URL: {missing_vars}"
        )

    async_url = f"postgresql+asyncpg://{db_vars['user']}:{db_vars['password']}@{db_vars['host']}:{db_vars['port']}/{db_vars['dbname']}"
    logger.debug(f"Constructed database URL from individual variables: {_mask_password(async_url)}")
    return async_url


async def create_db_engine() -> AsyncEngine:
    """Creates the asyncpg engine for the application DB.
    Returns:
        The asyncpg engine for the application DB.

    Raises:
        LuthienDBConfigurationError: If the database configuration is invalid.
        LuthienDBConnectionError: If the database connection fails.
    """
    global _db_engine, _db_session_factory
    if _db_engine:
        logger.debug("Database engine already initialized.")
        return _db_engine

    logger.info("Attempting to create database engine...")

    db_url = _get_db_url()

    try:
        # Get and validate pool sizes
        pool_min_size = settings.get_main_db_pool_min_size()
        pool_max_size = settings.get_main_db_pool_max_size()

        _db_engine = create_async_engine(
            db_url,
            echo=False,  # Set to True for debugging SQL queries
            pool_pre_ping=True,
            pool_size=pool_min_size,
            max_overflow=pool_max_size - pool_min_size,
        )

        _db_session_factory = async_sessionmaker(
            _db_engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )

        logger.info("Database engine created successfully.")
        return _db_engine
    except Exception as e:
        masked_url = _mask_password(db_url)
        raise LuthienDBConnectionError(f"Failed to create database engine using URL ({masked_url}): {e}")


async def close_db_engine() -> None:
    """Closes the database engine."""
    global _db_engine
    if _db_engine:
        try:
            await _db_engine.dispose()
            logger.info("Database engine closed successfully.")
        except Exception as e:
            logger.error(f"Error closing database engine: {e}", exc_info=True)
        finally:
            _db_engine = None
    else:
        logger.info("Database engine was already None or not initialized during shutdown.")


@contextlib.asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a SQLAlchemy async session for the database as a context manager."""
    if _db_session_factory is None:
        raise RuntimeError("Database session factory has not been initialized")

    async with _db_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
