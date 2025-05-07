"""Dependency Injection Container."""

from typing import AsyncContextManager, Callable

import httpx
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
