"""Dependencies for admin authentication."""

from typing import Annotated, Optional

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.admin.auth import admin_auth_service
from luthien_control.core.dependencies import get_db_session
from luthien_control.db.sqlmodel_models import AdminUser


async def get_current_admin(
    session_token: Annotated[Optional[str], Cookie()] = None,
    db: AsyncSession = Depends(get_db_session),
) -> AdminUser:
    """Get current authenticated admin user from session cookie."""
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    user = await admin_auth_service.get_user_from_session(db, session_token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    return user


class CSRFProtection:
    """CSRF protection for forms."""

    def __init__(self):
        self.token_name = "csrf_token"

    async def generate_token(self) -> str:
        """Generate CSRF token."""
        import secrets

        return secrets.token_urlsafe(32)


csrf_protection = CSRFProtection()
