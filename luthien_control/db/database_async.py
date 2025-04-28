import contextlib
import logging
from typing import Any, AsyncGenerator, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlparse, urlunparse

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from luthien_control.config.settings import Settings

logger = logging.getLogger(__name__)

# Global variables for async engines and session factories
_db_engine: Optional[AsyncEngine] = None

_db_session_factory = None

settings = Settings()


def _get_db_url() -> Optional[Tuple[Optional[str], Dict[str, Any]]]:
    """Determines the database URL, prioritizing database url."""
    database_url = settings.get_database_url()
    connect_args = {}

    if database_url:
        logger.info("Using DATABASE_URL for database connection.")

        # Parse the URL to extract sslmode and other query parameters
        parsed_url = urlparse(database_url)
        query_params = parse_qs(parsed_url.query)

        # If sslmode is in the query params, remove it from URL and add to connect_args
        if 'sslmode' in query_params:
            sslmode = query_params.pop('sslmode')[0]
            logger.info(f"Extracted sslmode={sslmode} from DATABASE_URL")
            connect_args['ssl'] = sslmode == 'require'

            # Rebuild URL without sslmode
            clean_query = '&'.join([f"{k}={'='.join(v)}" for k, v in query_params.items()])
            parsed_url = parsed_url._replace(query=clean_query)
            database_url = urlunparse(parsed_url)

        # Convert to async URL if needed
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)

        return database_url, connect_args

    logger.warning("DATABASE_URL not found. Falling back to individual DB_* variables.")
    db_user = settings.get_postgres_user()
    db_password = settings.get_postgres_password()
    db_host = settings.get_postgres_host()
    db_port = settings.get_postgres_port() # Returns int or None
    db_name = settings.get_postgres_db() # Returns str or None

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

    # Ensure db_port is an integer if it was retrieved successfully
    if db_port is None: # Should not happen if settings validation is robust, but check anyway
        logger.error("DB_PORT setting could not be determined.")
        return None

    async_url = f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    logger.info(
        f"Constructed database URL from individual variables: "
        f"postgresql+asyncpg://{db_user}:***@{db_host}:{db_port}/{db_name}"
    )
    return async_url, {}

async def create_db_engine() -> Optional[AsyncEngine]:
    """Creates the asyncpg engine for the application DB."""
    global _db_engine, _db_session_factory
    if _db_engine:
        logger.warning("Database engine already initialized.")
        return _db_engine

    logger.info("Attempting to create database engine...")
    db_url_result = _get_db_url()
    if not db_url_result:
        logger.error("Failed to determine database URL.")
        return None

    db_url, connect_args = db_url_result

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
            connect_args=connect_args,
        )

        _db_session_factory = async_sessionmaker(
            _db_engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )

        logger.info("Database engine created successfully.")
        return _db_engine
    except Exception as e:
        masked_url = db_url
        if db_url:
            parsed = urlparse(db_url)
            if parsed.password:
                masked_url = urlunparse(
                    parsed._replace(netloc=f"{parsed.username}:***@{parsed.hostname}:{parsed.port}")
                )
        logger.exception(f"Failed to create database engine using URL ({masked_url}): {e}")
        return None

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
