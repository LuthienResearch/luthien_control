from typing import AsyncGenerator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

# Test database URL - using in-memory SQLite for tests
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def async_engine():
    """Create a new async engine for each test function."""
    # Ensure SQLModel knows about our models
    # Import models within the fixture if necessary to ensure they are registered
    # before create_all is called.
    # from luthien_control.db.sqlmodel_models import ClientApiKey, Policy # Example

    engine = create_async_engine(
        TEST_DB_URL,
        echo=False,  # Typically set echo=False for cleaner test output
        future=True,
    )

    # Create tables
    async with engine.begin() as conn:
        # Ensure all models are imported before calling create_all
        # This might require importing them here or ensuring they are imported
        # somewhere before the fixture runs.
        await conn.run_sync(SQLModel.metadata.create_all)

    yield engine

    # Drop tables - No need to drop for in-memory DB as it disappears
    # async with engine.begin() as conn:
    #     await conn.run_sync(SQLModel.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def async_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Get a session for each test function."""
    async_session_factory = async_sessionmaker(async_engine, expire_on_commit=False)

    async with async_session_factory() as session:
        yield session
