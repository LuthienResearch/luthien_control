from typing import TYPE_CHECKING, Awaitable, Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    # Import ClientApiKey model for type checking only
    from luthien_control.db.sqlmodel_models import ClientApiKey


# Define the common type alias for the API key lookup function
ApiKeyLookupFunc = Callable[[AsyncSession, str], Awaitable[Optional["ClientApiKey"]]]
