from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from luthien_control.db.sqlmodel_crud import create_policy, get_policy_by_name
from luthien_control.db.sqlmodel_models import Policy
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

# Test database URL - using in-memory SQLite for tests
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# Setup and teardown fixtures for the database
@pytest_asyncio.fixture(scope="function")
async def async_engine():
    """Create a new async engine for each test."""
    engine = create_async_engine(
        TEST_DB_URL,
        echo=False,
        future=True,
    )

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def async_session_factory(async_engine):
    """Create a session factory for the tests."""
    return sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )


@pytest_asyncio.fixture(scope="function")
async def async_session(async_session_factory) -> AsyncGenerator[AsyncSession, None]:
    """Get a session for each test."""
    async with async_session_factory() as session:
        yield session


# FastAPI test fixtures
@pytest.fixture(scope="function")
def test_app(async_session_factory) -> Generator[FastAPI, None, None]:
    """Create a test FastAPI app with dependencies and routes."""
    app = FastAPI()

    # Define a dependency to get a database session
    async def get_test_db() -> AsyncGenerator[AsyncSession, None]:
        async with async_session_factory() as session:
            yield session

    # Define some test routes
    @app.post("/policies/", response_model=Policy)
    async def create_policy_route(policy: Policy, db: AsyncSession = Depends(get_test_db)):
        """Create a new policy."""
        created = await create_policy(db, policy)
        if not created:
            raise HTTPException(status_code=500, detail="Failed to create policy")
        return created

    @app.get("/policies/{name}", response_model=Policy)
    async def get_policy_route(name: str, db: AsyncSession = Depends(get_test_db)):
        """Get a policy by name."""
        policy = await get_policy_by_name(db, name)
        if not policy:
            raise HTTPException(status_code=404, detail="Policy not found")
        return policy

    yield app


@pytest.fixture(scope="function")
def test_client(test_app) -> Generator[TestClient, None, None]:
    """Create a test client for the FastAPI app."""
    with TestClient(test_app) as client:
        yield client


# Tests
def test_create_and_get_policy(test_client: TestClient):
    """Test creating and getting a policy through the API."""
    # Create a policy
    policy_data = {
        "name": "test-policy",
        "policy_class_path": "test.path",
        "is_active": True,
        "description": "Test policy"
    }

    # Create the policy
    response = test_client.post("/policies/", json=policy_data)
    assert response.status_code == 200
    created_policy = response.json()
    assert created_policy["name"] == "test-policy"
    assert created_policy["id"] is not None

    # Get the policy
    response = test_client.get(f"/policies/{policy_data['name']}")
    assert response.status_code == 200
    retrieved_policy = response.json()
    assert retrieved_policy["id"] == created_policy["id"]
    assert retrieved_policy["policy_class_path"] == "test.path"


def test_get_nonexistent_policy(test_client: TestClient):
    """Test getting a policy that doesn't exist."""
    response = test_client.get("/policies/nonexistent")
    assert response.status_code == 404
    assert response.json()["detail"] == "Policy not found"
