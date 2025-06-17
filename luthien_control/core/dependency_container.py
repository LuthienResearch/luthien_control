# Dependency Injection Container.

from typing import AsyncContextManager, Callable

import httpx
import openai
from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.settings import Settings


class DependencyContainer:
    """Holds shared dependencies for the application."""

    def __init__(
        self,
        settings: Settings,
        http_client: httpx.AsyncClient,
        db_session_factory: Callable[[], AsyncContextManager[AsyncSession]],
    ) -> None:
        """
        Initializes the container.

        Args:
            settings: Application settings.
            http_client: Shared asynchronous HTTP client.
            db_session_factory: A factory function that returns an async context manager
                                yielding an SQLAlchemy AsyncSession.
        """
        self.settings = settings
        self.http_client = http_client
        self.db_session_factory = db_session_factory

    def create_openai_client(self, base_url: str, api_key: str) -> openai.AsyncOpenAI:
        """
        Creates an OpenAI client for the specified backend URL and API key.

        Args:
            base_url: The base URL for the OpenAI-compatible API endpoint.
            api_key: The API key for authentication.

        Returns:
            An configured OpenAI AsyncClient instance.
        """
        return openai.AsyncOpenAI(api_key=api_key, base_url=base_url)
