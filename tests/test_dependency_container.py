from typing import AsyncContextManager, Callable
from unittest.mock import AsyncMock, MagicMock

import httpx
import openai
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.settings import Settings
from sqlalchemy.ext.asyncio import AsyncSession


def test_dependency_container_initialization():
    """Verify that DependencyContainer correctly stores provided dependencies."""
    # Create mock dependencies
    mock_settings = MagicMock(spec=Settings)
    mock_http_client = MagicMock(spec=httpx.AsyncClient)
    # Mock the session factory callable and its async context manager behavior
    mock_session = MagicMock(spec=AsyncSession)
    mock_session_cm = AsyncMock(spec=AsyncContextManager)
    # Set the return_value of the AsyncMock itself for __aenter__
    mock_session_cm.return_value = mock_session
    mock_session_factory = MagicMock(spec=Callable[[], AsyncContextManager[AsyncSession]])
    mock_session_factory.return_value = mock_session_cm

    # Instantiate the container
    container = DependencyContainer(
        settings=mock_settings,
        http_client=mock_http_client,
        db_session_factory=mock_session_factory,
    )

    # Assert that the dependencies are stored correctly
    assert container.settings is mock_settings
    assert container.http_client is mock_http_client
    assert container.db_session_factory is mock_session_factory

    # Test the OpenAI client factory
    mock_openai_client = container.create_openai_client("https://api.openai.com/v1", "test-key")
    assert isinstance(mock_openai_client, openai.AsyncOpenAI)
