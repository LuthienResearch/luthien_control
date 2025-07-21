"""Dependencies for admin authentication."""

from typing import Annotated, Optional

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.admin.auth import admin_auth_service
from luthien_control.core.dependencies import get_db_session
from luthien_control.models.admin_user import AdminUser


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


async def get_current_superuser(
    current_admin: Annotated[AdminUser, Depends(get_current_admin)],
) -> AdminUser:
    """Get current admin user and verify superuser status."""
    if not current_admin.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser access required",
        )
    return current_admin


class CSRFProtection:
    """CSRF protection for forms."""

    def __init__(self):
        self.token_name = "csrf_token"

    async def generate_token(self) -> str:
        """Generate CSRF token."""
        import secrets

        return secrets.token_urlsafe(32)

    async def validate_token(
        self,
        form_token: str,
        cookie_token: Annotated[Optional[str], Cookie(alias="csrf_token")] = None,
    ) -> bool:
        """Validate CSRF token."""
        if not cookie_token or not form_token:
            return False
        return cookie_token == form_token


csrf_protection = CSRFProtection()
